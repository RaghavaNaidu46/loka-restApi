from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import REGCONFIG

from app.core.database import getDb
from app.models.issue import Issue, IssueCategory, IssueStatus
from app.models.district import District
from app.schemas.district import DistrictResponse
import uuid

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/issues", summary="Search issues by keyword, district, category, and status")
async def searchIssues(
    db: Annotated[AsyncSession, Depends(getDb)],
    query: str | None = Query(default=None, description="Keyword search"),
    districtId: uuid.UUID | None = Query(default=None),
    category: IssueCategory | None = Query(default=None),
    issueStatus: IssueStatus | None = Query(default=None),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    from sqlalchemy.orm import joinedload
    stmt = select(Issue).options(joinedload(Issue.district), joinedload(Issue.creator)).where(
        Issue.status.in_([IssueStatus.published, IssueStatus.active, IssueStatus.resolved])
    )

    if query and query.strip():
        # PostgreSQL full-text search using tsvector GIN index
        from sqlalchemy import func
        stmt = stmt.where(
            Issue.searchVector.op("@@")(func.plainto_tsquery("english", query.strip()))
        )

    if districtId:
        stmt = stmt.where(Issue.districtId == districtId)

    if category:
        stmt = stmt.where(Issue.category == category)

    if issueStatus:
        stmt = stmt.where(Issue.status == issueStatus)

    stmt = stmt.order_by(Issue.createdAt.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    issues = result.scalars().all()

    items = []
    for issue in issues:
        items.append({
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
            } if issue.district else None,
            "status": issue.status,
            "supportCount": issue.supportCount,
            "opposeCount": issue.opposeCount,
            "evidenceCount": issue.evidenceCount,
            "creatorDisplayName": issue.creator.displayName if issue.creator else None,
            "createdAt": issue.createdAt.isoformat(),
            "updatedAt": issue.updatedAt.isoformat(),
        })

    return {"items": items, "count": len(items), "query": query}


@router.get("/districts", summary="List all available districts")
async def listDistricts(
    db: Annotated[AsyncSession, Depends(getDb)],
    state: str | None = Query(default=None, description="Filter by state"),
):
    stmt = select(District)
    if state:
        stmt = stmt.where(District.state == state)
    stmt = stmt.order_by(District.state, District.name)

    result = await db.execute(stmt)
    districts = result.scalars().all()

    return {
        "items": [DistrictResponse.model_validate(d).model_dump() for d in districts],
        "count": len(districts),
    }
