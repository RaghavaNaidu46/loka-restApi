from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.database import getDb
from app.core.deps import getOptionalCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue, IssueStatus, IssueCategory

router = APIRouter(prefix="/feed", tags=["Feed"])


def serializeIssue(issue: Issue) -> dict:
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
        } if issue.district else None,
        "status": issue.status,
        "supportCount": issue.supportCount,
        "opposeCount": issue.opposeCount,
        "evidenceCount": issue.evidenceCount,
        "creatorDisplayName": issue.creator.displayName if issue.creator else None,
        "createdAt": issue.createdAt.isoformat(),
        "updatedAt": issue.updatedAt.isoformat(),
    }


ACTIVE_STATUSES = [IssueStatus.published, IssueStatus.active]

# Base query options: eager-load district and creator in a single JOIN
_EAGER = [joinedload(Issue.district), joinedload(Issue.creator)]


def _priorityScore(issue: Issue) -> float:
    """
    Recency-weighted community score.
    Balances total participation with freshness so old popular issues
    don't permanently dominate the priority feed.
    """
    now = datetime.now(timezone.utc)
    # Ensure createdAt is timezone-aware for comparison
    created = issue.createdAt
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    ageHours = max((now - created).total_seconds() / 3600, 0)
    participation = issue.supportCount + issue.opposeCount + issue.evidenceCount
    return participation / ((ageHours + 2) ** 0.8)


@router.get("/nearby", summary="Issues in citizen's home or living-in district")
async def feedNearby(
    db: Annotated[AsyncSession, Depends(getDb)],
    citizen: Annotated[Citizen | None, Depends(getOptionalCitizen)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    category: Optional[IssueCategory] = Query(default=None),
):
    query = (
        select(Issue)
        .options(*_EAGER)
        .where(Issue.status.in_(ACTIVE_STATUSES))
    )

    if citizen and (citizen.homeDistrictId or citizen.livingInDistrictId):
        districtIds = list(filter(None, [citizen.homeDistrictId, citizen.livingInDistrictId]))
        query = query.where(Issue.districtId.in_(districtIds))

    if category:
        query = query.where(Issue.category == category)

    query = query.order_by(Issue.updatedAt.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    issues = result.scalars().unique().all()

    items = [serializeIssue(issue) for issue in issues]
    return {"items": items, "count": len(items), "hasMore": len(items) == limit}


@router.get("/new", summary="Recently submitted issues (chronological)")
async def feedNew(
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    category: Optional[IssueCategory] = Query(default=None),
):
    query = (
        select(Issue)
        .options(*_EAGER)
        .where(Issue.status.in_(ACTIVE_STATUSES))
    )
    if category:
        query = query.where(Issue.category == category)

    query = query.order_by(Issue.createdAt.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    issues = result.scalars().unique().all()

    items = [serializeIssue(issue) for issue in issues]
    return {"items": items, "count": len(items), "hasMore": len(items) == limit}


@router.get("/priority", summary="Issues sorted by recency-weighted community participation")
async def feedPriority(
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    # Fetch 2× limit candidates sorted by raw participation first,
    # then re-rank with recency decay in Python
    fetchLimit = min(limit * 2, 100)
    result = await db.execute(
        select(Issue)
        .options(*_EAGER)
        .where(Issue.status.in_(ACTIVE_STATUSES))
        .order_by((Issue.supportCount + Issue.opposeCount + Issue.evidenceCount).desc())
        .offset(offset)
        .limit(fetchLimit)
    )
    candidates = result.scalars().unique().all()

    # Re-rank by recency-weighted score
    ranked = sorted(candidates, key=_priorityScore, reverse=True)[:limit]
    items = [serializeIssue(issue) for issue in ranked]
    return {"items": items, "count": len(items), "hasMore": len(candidates) == fetchLimit}


@router.get("/resolved", summary="Resolved issues (civic outcomes)")
async def feedResolved(
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    result = await db.execute(
        select(Issue)
        .options(*_EAGER)
        .where(Issue.status == IssueStatus.resolved)
        .order_by(Issue.updatedAt.desc())
        .offset(offset)
        .limit(limit)
    )
    issues = result.scalars().unique().all()

    items = [serializeIssue(issue) for issue in issues]
    return {"items": items, "count": len(items), "hasMore": len(items) == limit}
