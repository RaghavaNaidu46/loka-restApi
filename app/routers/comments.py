import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import joinedload

from app.core.database import getDb
from app.core.deps import getVerifiedCitizen, getOptionalCitizen
from app.models.citizen import Citizen
from app.models.issue import Issue, IssueStatus
from app.models.comment import Comment, CommentStatus
from app.models.comment_like import CommentLike
from app.models.comment_report import CommentReport
from app.models.participation import Participation, ParticipationType
from app.schemas.comment import AddCommentRequest, CommentResponse, CommentListResponse

router = APIRouter(prefix="/issues", tags=["Comments"])


@router.get("/{issueId}/comments", response_model=CommentListResponse, summary="List comments on an issue")
async def listComments(
    issueId: uuid.UUID,
    db: Annotated[AsyncSession, Depends(getDb)],
    citizen: Annotated[Citizen | None, Depends(getOptionalCitizen)],
    sortBy: str = Query(default="top"),
    stance: str = Query(default="all"),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    issueResult = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = issueResult.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    issueCreatorId = issue.creatorId

    # Calculate total count based on active filters
    countStmt = select(func.count(Comment.id)).where(
        Comment.issueId == issueId,
        Comment.modStatus == CommentStatus.visible
    )
    if stance in ("support", "oppose"):
        targetType = ParticipationType.support if stance == "support" else ParticipationType.oppose
        countStmt = countStmt.join(
            Participation,
            (Participation.citizenId == Comment.citizenId) & (Participation.issueId == Comment.issueId)
        ).where(Participation.type == targetType)
    elif stance == "neutral":
        countStmt = countStmt.outerjoin(
            Participation,
            (Participation.citizenId == Comment.citizenId) & (Participation.issueId == Comment.issueId)
        ).where(Participation.id == None)

    countResult = await db.execute(countStmt)
    total = countResult.scalar_one()

    # Query comments with standard filters
    stmt = select(Comment).options(joinedload(Comment.citizen)).where(
        Comment.issueId == issueId,
        Comment.modStatus == CommentStatus.visible
    )

    if stance in ("support", "oppose"):
        targetType = ParticipationType.support if stance == "support" else ParticipationType.oppose
        stmt = stmt.join(
            Participation,
            (Participation.citizenId == Comment.citizenId) & (Participation.issueId == Comment.issueId)
        ).where(Participation.type == targetType)
    elif stance == "neutral":
        stmt = stmt.outerjoin(
            Participation,
            (Participation.citizenId == Comment.citizenId) & (Participation.issueId == Comment.issueId)
        ).where(Participation.id == None)

    # Sort comments
    if sortBy == "top":
        likesSub = (
            select(CommentLike.commentId, func.count(CommentLike.id).label("like_count"))
            .group_by(CommentLike.commentId)
            .subquery()
        )
        stmt = (
            stmt.outerjoin(likesSub, likesSub.c.commentId == Comment.id)
            .order_by(func.coalesce(likesSub.c.like_count, 0).desc(), Comment.createdAt.desc())
        )
    else:
        stmt = stmt.order_by(Comment.createdAt.desc())

    # Paginate
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    comments = result.scalars().all()

    # Batch retrieve likes and stance
    commentIds = [c.id for c in comments]
    commenterIds = list(set([c.citizenId for c in comments]))

    likesCountMap = {}
    if commentIds:
        likesCountResult = await db.execute(
            select(CommentLike.commentId, func.count(CommentLike.id))
            .where(CommentLike.commentId.in_(commentIds))
            .group_by(CommentLike.commentId)
        )
        likesCountMap = dict(likesCountResult.all())

    hasLikedSet = set()
    if citizen and commentIds:
        hasLikedResult = await db.execute(
            select(CommentLike.commentId)
            .where(
                CommentLike.citizenId == citizen.id,
                CommentLike.commentId.in_(commentIds)
            )
        )
        hasLikedSet = set(hasLikedResult.scalars().all())

    stanceMap = {}
    if commenterIds:
        stanceResult = await db.execute(
            select(Participation.citizenId, Participation.type)
            .where(
                Participation.issueId == issueId,
                Participation.citizenId.in_(commenterIds)
            )
        )
        stanceMap = dict(stanceResult.all())

    items = []
    for c in comments:
        items.append(CommentResponse(
            id=c.id,
            citizenId=c.citizenId,
            citizenDisplayName=c.citizen.displayName if c.citizen else None,
            issueId=c.issueId,
            text=c.text,
            createdAt=c.createdAt.isoformat(),
            parentId=c.parentId,
            likesCount=likesCountMap.get(c.id, 0),
            hasLiked=c.id in hasLikedSet,
            stance=stanceMap.get(c.citizenId).value if stanceMap.get(c.citizenId) else None,
            authorRole=c.citizen.role if c.citizen else "citizen",
            isAuthor=(c.citizenId == issueCreatorId),
        ))

    return CommentListResponse(items=items, total=total)


@router.post("/{issueId}/comments", summary="Add a comment to an issue")
async def addComment(
    issueId: uuid.UUID,
    body: AddCommentRequest,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    result = await db.execute(select(Issue).where(Issue.id == issueId))
    issue = result.scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.status not in (IssueStatus.published, IssueStatus.active):
        raise HTTPException(status_code=400, detail="Comments are only allowed on active issues")

    if body.parentId:
        parentResult = await db.execute(
            select(Comment).where(Comment.id == body.parentId, Comment.issueId == issueId)
        )
        parentComment = parentResult.scalar_one_or_none()
        if not parentComment:
            raise HTTPException(status_code=400, detail="Parent comment not found")
        if parentComment.parentId is not None:
            raise HTTPException(status_code=400, detail="Nested replies are limited to 1 level")

    comment = Comment(
        citizenId=citizen.id,
        issueId=issueId,
        text=body.text,
        parentId=body.parentId
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    # Fetch participation type to return stance
    participationResult = await db.execute(
        select(Participation.type).where(
            Participation.issueId == issueId,
            Participation.citizenId == citizen.id
        )
    )
    participationType = participationResult.scalar_one_or_none()
    stanceStr = participationType.value if participationType else None

    return {
        "id": str(comment.id),
        "citizenDisplayName": citizen.displayName,
        "issueId": str(issueId),
        "text": comment.text,
        "createdAt": comment.createdAt.isoformat(),
        "parentId": str(comment.parentId) if comment.parentId else None,
        "likesCount": 0,
        "hasLiked": False,
        "stance": stanceStr,
        "authorRole": citizen.role,
        "isAuthor": (citizen.id == issue.creatorId),
    }


@router.post("/{issueId}/comments/{commentId}/like", summary="Like a comment")
async def likeComment(
    issueId: uuid.UUID,
    commentId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    commentResult = await db.execute(
        select(Comment).where(Comment.id == commentId, Comment.issueId == issueId)
    )
    comment = commentResult.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existingLike = await db.execute(
        select(CommentLike).where(
            CommentLike.citizenId == citizen.id,
            CommentLike.commentId == commentId
        )
    )
    if existingLike.scalar_one_or_none():
        return {"message": "Comment already liked"}

    like = CommentLike(
        citizenId=citizen.id,
        commentId=commentId
    )
    db.add(like)
    await db.flush()
    return {"message": "Comment liked successfully"}


@router.delete("/{issueId}/comments/{commentId}/like", summary="Unlike a comment")
async def unlikeComment(
    issueId: uuid.UUID,
    commentId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    likeResult = await db.execute(
        select(CommentLike).where(
            CommentLike.citizenId == citizen.id,
            CommentLike.commentId == commentId
        )
    )
    like = likeResult.scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=404, detail="Like not found")

    await db.delete(like)
    await db.flush()
    return {"message": "Comment unliked successfully"}


@router.post("/{issueId}/comments/{commentId}/report", summary="Report a comment for moderation")
async def reportComment(
    issueId: uuid.UUID,
    commentId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getVerifiedCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    commentResult = await db.execute(
        select(Comment).where(Comment.id == commentId, Comment.issueId == issueId)
    )
    comment = commentResult.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    existingReport = await db.execute(
        select(CommentReport).where(
            CommentReport.citizenId == citizen.id,
            CommentReport.commentId == commentId
        )
    )
    if existingReport.scalar_one_or_none():
        return {"message": "Comment already reported"}

    report = CommentReport(
        citizenId=citizen.id,
        commentId=commentId,
        reason="Reported for moderation review"
    )
    db.add(report)
    await db.flush()

    countResult = await db.execute(
        select(func.count()).where(CommentReport.commentId == commentId)
    )
    reportCount = countResult.scalar_one()
    if reportCount >= 3:
        comment.modStatus = CommentStatus.hidden

    return {"message": "Comment reported for review"}
