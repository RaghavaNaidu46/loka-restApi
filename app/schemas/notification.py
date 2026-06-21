import uuid
from pydantic import BaseModel
from app.models.notification import NotificationKind


class NotificationResponse(BaseModel):
    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str
    referenceId: uuid.UUID | None
    isRead: bool
    createdAt: str

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unreadCount: int
