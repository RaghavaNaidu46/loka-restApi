import uuid
from sqlalchemy import ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class CommentLike(Base):
    __tablename__ = "comment_likes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id"
    )
    commentId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, name="comment_id"
    )
    createdAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), name="created_at"
    )

    __table_args__ = (
        UniqueConstraint("citizen_id", "comment_id", name="uq_citizen_comment_like"),
    )
