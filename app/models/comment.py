import uuid
import enum
from sqlalchemy import Text, String, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class CommentStatus(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"
    removed = "removed"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id")
    issueId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False, name="issue_id")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    parentId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, name="parent_id"
    )
    modStatus: Mapped[CommentStatus] = mapped_column(
        Enum(CommentStatus, name="comment_status_enum"),
        default=CommentStatus.visible,
        name="mod_status",
    )
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")

    # Relationships
    citizen: Mapped["Citizen"] = relationship("Citizen", back_populates="comments")
    issue: Mapped["Issue"] = relationship("Issue", back_populates="comments")
    parent: Mapped["Comment | None"] = relationship("Comment", remote_side=[id], back_populates="replies")
    replies: Mapped[list["Comment"]] = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")


from app.models.citizen import Citizen  # noqa: E402
from app.models.issue import Issue  # noqa: E402
