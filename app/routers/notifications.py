import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.core.database import getDb
from app.core.deps import getCurrentCitizen
from app.models.citizen import Citizen
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse, summary="Get paginated notifications")
async def getNotifications(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
):
    unreadCount = await db.execute(
        select(func.count()).where(
            Notification.citizenId == citizen.id,
            Notification.isRead == False,
        )
    )

    result = await db.execute(
        select(Notification)
        .where(Notification.citizenId == citizen.id)
        .order_by(Notification.createdAt.desc())
        .offset(offset)
        .limit(limit)
    )
    notifications = result.scalars().all()

    items = [
        NotificationResponse(
            id=n.id,
            kind=n.kind,
            title=n.title,
            body=n.body,
            referenceId=n.referenceId,
            isRead=n.isRead,
            createdAt=n.createdAt.isoformat(),
        )
        for n in notifications
    ]

    return NotificationListResponse(items=items, unreadCount=unreadCount.scalar_one())


@router.patch("/{notificationId}/read", summary="Mark a notification as read")
async def markNotificationRead(
    notificationId: uuid.UUID,
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    await db.execute(
        update(Notification)
        .where(Notification.id == notificationId, Notification.citizenId == citizen.id)
        .values(isRead=True)
    )
    return {"message": "Notification marked as read"}


@router.patch("/read-all", summary="Mark all notifications as read")
async def markAllNotificationsRead(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
    db: Annotated[AsyncSession, Depends(getDb)],
):
    await db.execute(
        update(Notification)
        .where(Notification.citizenId == citizen.id, Notification.isRead == False)
        .values(isRead=True)
    )
    return {"message": "All notifications marked as read"}
