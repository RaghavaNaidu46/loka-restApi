import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.core.database import getDb
from app.core.deps import getCurrentCitizen, getVerifiedCitizen, getOptionalCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue, IssueStatus
from app.models.district import District
from app.models.participation import Participation
from app.schemas.issue import CreateIssueRequest, UpdateIssueRequest, IssueResponse, IssueListResponse

router = APIRouter(prefix="/issues", tags=["Issues"])


def serializeIssue(issue: Issue, participationStatus: str | None = None) -> dict:
    return {
        "id": str(issue.id),
        "title": issue.title,
        "description": issue.description,
        "desiredOutcome": issue.desiredOutcome,
        "category": issue.category,
        "area": issue.area,
        "city": issue.city,
        "district": {
            "id": str(issue.district.id),
            "name": issue.district.name,
            "state": issue.district.state,
            "country": issue.district.country,
        } if issue.district else None,
        "status": issue.status,
        "supportCount": issue.supportCount,
        "opposeCount": issue.opposeCount,
        "evidenceCount": issue.evidenceCount,
        "creatorDisplayName": issue.creator.displayName if issue.creator else None,
        "createdAt": issue.createdAt.isoformat(),
        "updatedAt": issue.updatedAt.isoformat(),
        "participationStatus": participationStatus,
    }


@router.post("", summary="Create a new issue (saved as draft)")
async def createIssue(
    body: CreateIssueRequest,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    districtResult = await db.execute(select(District).where(District.id == body.location.districtId))
    district = districtResult.scalar_one_or_none()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    issue = Issue(
        creatorId=citizen.id,
        title=body.title,
        description=body.description,
        desiredOutcome=body.desiredOutcome,
        category=body.category,
        area=body.location.area,
        city=body.location.city,
        districtId=body.location.districtId,
        status=IssueStatus.draft,
        searchVector=func.to_tsvector('english', body.title + ' ' + body.description),
    )
    db.add(issue)
    await db.flush()

    await db.refresh(issue, ["district", "creator", "createdAt", "updatedAt"])
    return serializeIssue(issue)


@router.get("/{issueId}", summary="Get issue details")
async def getIssue(
    issueId: uuid.UUID,
    db: Annotated[AsyncSession, Depends(getDb)],
    citizen: Annotated[Citizen | None, Depends(getOptionalCitizen)],
):
    result = await db.execute(
        select(Issue).where(Issue.id == issueId)
    )
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await db.refresh(issue, ["district", "creator"])

    participationStatus = None
    if citizen:
        pResult = await db.execute(
            select(Participation).where(
                Participation.citizenId == citizen.id,
                Participation.issueId == issueId,
            )
        )
        p = pResult.scalar_one_or_none()
        if p:
            participationStatus = p.type.value

    return serializeIssue(issue, participationStatus)


@router.patch("/{issueId}", summary="Update a draft issue")
async def updateIssue(
    issueId: uuid.UUID,
    body: UpdateIssueRequest,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId, Issue.creatorId == citizen.id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.status != IssueStatus.draft:
        raise HTTPException(status_code=403, detail="Only draft issues can be edited")

    updateData = body.model_dump(exclude_none=True)
    if "location" in updateData:
        loc = updateData.pop("location")
        updateData["area"] = loc.get("area")
        updateData["city"] = loc.get("city")
        updateData["districtId"] = loc.get("districtId")

    for field, value in updateData.items():
        setattr(issue, field, value)

    if "title" in updateData or "description" in updateData:
        issue.searchVector = func.to_tsvector('english', issue.title + ' ' + issue.description)

    await db.flush()
    await db.refresh(issue, ["district", "creator", "createdAt", "updatedAt"])
    return serializeIssue(issue)


@router.post("/{issueId}/submit", summary="Submit a draft issue for moderation review")
async def submitIssue(
    issueId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId, Issue.creatorId == citizen.id))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.status != IssueStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft issues can be submitted")

    from app.core.config import settings
    if settings.mockVerification:
        issue.status = IssueStatus.active
        msg = "Issue approved and active"
    else:
        issue.status = IssueStatus.submitted
        msg = "Issue submitted for review"

    await db.flush()
    return {"message": msg, "issueId": str(issueId)}


@router.get("/{issueId}/related", summary="Get related issues by category and district")
async def getRelatedIssues(
    issueId: uuid.UUID,
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    related = await db.execute(
        select(Issue)
        .where(
            Issue.id != issueId,
            Issue.category == issue.category,
            Issue.districtId == issue.districtId,
            Issue.status.in_([IssueStatus.active, IssueStatus.published]),
        )
        .limit(5)
    )
    issues = related.scalars().all()

    items = []
    for i in issues:
        await db.refresh(i, ["district", "creator"])
        items.append(serializeIssue(i))

    return {"items": items}
