import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import getDb
from app.core.deps import getVerifiedCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue, IssueStatus
from app.models.participation import Participation, ParticipationType
from app.schemas.participation import SupportRequest, OpposeRequest, ParticipationStatusResponse

router = APIRouter(prefix="/issues", tags=["Participation"])


async def checkGeographicEligibility(citizen: Citizen, issue: Issue) -> None:
    """Enforce that citizen is in the same district as the issue."""
    eligibleIds = list(filter(None, [citizen.homeDistrictId, citizen.livingInDistrictId]))
    if issue.districtId not in eligibleIds:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only participate in issues within your home or living-in district",
        )


async def checkIssueParticipable(issue: Issue | None, issueId: uuid.UUID) -> None:
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status not in (IssueStatus.published, IssueStatus.active):
        raise HTTPException(status_code=400, detail="This issue is not open for participation")


@router.post("/{issueId}/support", summary="Permanently support an issue")
async def supportIssue(
    issueId: uuid.UUID,
    body: SupportRequest,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    await checkIssueParticipable(issue, issueId)
    await checkGeographicEligibility(citizen, issue)

    # Check if already participated
    existing = await db.execute(
        select(Participation).where(
            Participation.citizenId == citizen.id,
            Participation.issueId == issueId,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already participated in this issue")

    try:
        participation = Participation(
            citizenId=citizen.id,
            issueId=issueId,
            type=ParticipationType.support,
        )
        db.add(participation)
        await db.execute(
            update(Issue)
            .where(Issue.id == issueId)
            .values(supportCount=Issue.supportCount + 1)
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You have already participated in this issue")

    return {"message": "Support recorded permanently", "issueId": str(issueId)}


@router.post("/{issueId}/oppose", summary="Permanently oppose an issue with explanation")
async def opposeIssue(
    issueId: uuid.UUID,
    body: OpposeRequest,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    await checkIssueParticipable(issue, issueId)
    await checkGeographicEligibility(citizen, issue)

    existing = await db.execute(
        select(Participation).where(
            Participation.citizenId == citizen.id,
            Participation.issueId == issueId,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You have already participated in this issue")

    try:
        participation = Participation(
            citizenId=citizen.id,
            issueId=issueId,
            type=ParticipationType.oppose,
            opposeExplanation=body.explanation,
        )
        db.add(participation)
        await db.execute(
            update(Issue)
            .where(Issue.id == issueId)
            .values(opposeCount=Issue.opposeCount + 1)
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You have already participated in this issue")

    return {"message": "Opposition recorded permanently", "issueId": str(issueId)}


@router.get("/{issueId}/participation/status", response_model=ParticipationStatusResponse, summary="Check citizen's participation status on an issue")
async def getParticipationStatus(
    issueId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(
        select(Participation).where(
            Participation.citizenId == citizen.id,
            Participation.issueId == issueId,
        )
    )
    participation = result.scalar_one_or_none()

    return ParticipationStatusResponse(
        issueId=issueId,
        hasParticipated=participation is not None,
        participationType=participation.type.value if participation else None,
    )
