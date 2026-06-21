import uuid
import enum
from sqlalchemy import String, Text, Boolean, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class NotificationKind(str, enum.Enum):
    issueApproved = "issue_approved"
    issueRejected = "issue_rejected"
    clarificationRequested = "clarification_requested"
    participationReceived = "participation_received"
    appealUpdate = "appeal_update"
    resolutionUpdate = "resolution_update"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id")
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind, name="notification_kind_enum"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    referenceId: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, name="reference_id")
    isRead: Mapped[bool] = mapped_column(Boolean, default=False, name="is_read")
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")

    # Relationships
    citizen: Mapped["Citizen"] = relationship("Citizen", back_populates="notifications")


from app.models.citizen import Citizen  # noqa: E402
