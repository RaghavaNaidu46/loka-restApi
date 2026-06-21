import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import getDb
from app.core.deps import getModeratorCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue, IssueStatus
from app.models.moderation import ModerationAction, ModerationTargetType, ModerationActionType
from app.models.notification import Notification, NotificationKind

router = APIRouter(prefix="/moderation", tags=["Moderation"])


async def logAction(
    db: AsyncSession,
    moderatorId: uuid.UUID,
    targetId: uuid.UUID,
    targetType: ModerationTargetType,
    actionType: ModerationActionType,
    reason: str,
    notes: str | None = None,
):
    action = ModerationAction(
        moderatorId=moderatorId,
        targetType=targetType,
        targetId=targetId,
        actionType=actionType,
        reason=reason,
        notes=notes,
    )
    db.add(action)
    return action


@router.get("/pending", summary="List issues pending moderation review")
async def listPendingIssues(
    moderator: Annotated[Citizen, Depends(getModeratorCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(
        select(Issue)
        .where(Issue.status.in_([IssueStatus.submitted, IssueStatus.underReview]))
        .order_by(Issue.createdAt.asc())
    )
    issues = result.scalars().all()

    items = []
    for issue in issues:
        await db.refresh(issue, ["district", "creator"])
        items.append({
            "id": str(issue.id),
            "title": issue.title,
            "category": issue.category,
            "status": issue.status,
            "city": issue.city,
            "district": issue.district.name if issue.district else None,
            "creatorDisplayName": issue.creator.displayName if issue.creator else None,
            "createdAt": issue.createdAt.isoformat(),
        })

    return {"items": items, "count": len(items)}


@router.post("/issues/{issueId}/approve", summary="Approve an issue → set status to active")
async def approveIssue(
    issueId: uuid.UUID,
    reason: str = Body(...),
    moderator: Annotated[Citizen, Depends(getModeratorCitizen)] = None,
    db: Annotated[AsyncSession, Depends(getDb)] = None,
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await db.execute(update(Issue).where(Issue.id == issueId).values(status=IssueStatus.active))
    await logAction(db, moderator.id, issueId, ModerationTargetType.issue, ModerationActionType.approve, reason)

    # Notify creator
    notification = Notification(
        citizenId=issue.creatorId,
        kind=NotificationKind.issueApproved,
        title="Issue Approved",
        body=f"Your issue '{issue.title}' has been approved and is now active.",
        referenceId=issueId,
    )
    db.add(notification)
    await db.flush()

    return {"message": "Issue approved and set to active"}


@router.post("/issues/{issueId}/reject", summary="Reject an issue with reason")
async def rejectIssue(
    issueId: uuid.UUID,
    reason: str = Body(...),
    moderator: Annotated[Citizen, Depends(getModeratorCitizen)] = None,
    db: Annotated[AsyncSession, Depends(getDb)] = None,
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await db.execute(update(Issue).where(Issue.id == issueId).values(status=IssueStatus.rejected))
    await logAction(db, moderator.id, issueId, ModerationTargetType.issue, ModerationActionType.reject, reason)

    notification = Notification(
        citizenId=issue.creatorId,
        kind=NotificationKind.issueRejected,
        title="Issue Rejected",
        body=f"Your issue '{issue.title}' was rejected. Reason: {reason}",
        referenceId=issueId,
    )
    db.add(notification)
    await db.flush()

    return {"message": "Issue rejected"}


@router.post("/issues/{issueId}/clarify", summary="Request clarification from the issue creator")
async def requestClarification(
    issueId: uuid.UUID,
    reason: str = Body(...),
    moderator: Annotated[Citizen, Depends(getModeratorCitizen)] = None,
    db: Annotated[AsyncSession, Depends(getDb)] = None,
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await logAction(db, moderator.id, issueId, ModerationTargetType.issue, ModerationActionType.clarify, reason)

    notification = Notification(
        citizenId=issue.creatorId,
        kind=NotificationKind.clarificationRequested,
        title="Clarification Requested",
        body=f"A moderator has requested clarification on your issue '{issue.title}'. Details: {reason}",
        referenceId=issueId,
    )
    db.add(notification)
    await db.flush()

    return {"message": "Clarification requested and creator notified"}


@router.post("/issues/{issueId}/merge", summary="Merge an issue into another")
async def mergeIssue(
    issueId: uuid.UUID,
    targetIssueId: uuid.UUID = Body(...),
    reason: str = Body(...),
    moderator: Annotated[Citizen, Depends(getModeratorCitizen)] = None,
    db: Annotated[AsyncSession, Depends(getDb)] = None,
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await db.execute(
        update(Issue)
        .where(Issue.id == issueId)
        .values(status=IssueStatus.merged, mergedIntoId=targetIssueId)
    )
    await logAction(db, moderator.id, issueId, ModerationTargetType.issue, ModerationActionType.merge, reason)
    await db.flush()

    return {"message": "Issue merged", "mergedIntoId": str(targetIssueId)}
