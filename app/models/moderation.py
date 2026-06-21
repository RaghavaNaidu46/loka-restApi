import uuid
import enum
from sqlalchemy import String, Text, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ModerationTargetType(str, enum.Enum):
    issue = "issue"
    comment = "comment"
    evidence = "evidence"


class ModerationActionType(str, enum.Enum):
    approve = "approve"
    reject = "reject"
    merge = "merge"
    clarify = "clarify"
    hide = "hide"
    restore = "restore"


class AppealStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    upheld = "upheld"
    overturned = "overturned"


class VerificationRecordStatus(str, enum.Enum):
    pending = "pending"
    valid = "valid"
    invalid = "invalid"
    expired = "expired"


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    moderatorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="moderator_id")
    targetType: Mapped[ModerationTargetType] = mapped_column(Enum(ModerationTargetType, name="mod_target_type_enum"), name="target_type")
    targetId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, name="target_id")
    actionType: Mapped[ModerationActionType] = mapped_column(Enum(ModerationActionType, name="mod_action_type_enum"), name="action_type")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id")
    actionId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("moderation_actions.id"), nullable=False, name="action_id")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AppealStatus] = mapped_column(Enum(AppealStatus, name="appeal_status_enum"), default=AppealStatus.pending)
    resolutionNotes: Mapped[str | None] = mapped_column(Text, nullable=True, name="resolution_notes")
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id")
    verificationType: Mapped[str] = mapped_column(String(50), default="aadhaar_offline_xml", name="verification_type")
    status: Mapped[VerificationRecordStatus] = mapped_column(Enum(VerificationRecordStatus, name="ver_record_status_enum"))
    uidaiRef: Mapped[str | None] = mapped_column(String(255), nullable=True, name="uidai_ref")
    verifiedAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, name="verified_at")
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")
