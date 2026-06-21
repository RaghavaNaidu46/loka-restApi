import uuid
import enum
from sqlalchemy import Text, Enum, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ParticipationType(str, enum.Enum):
    support = "support"
    oppose = "oppose"


class Participation(Base):
    __tablename__ = "participations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizenId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="citizen_id")
    issueId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False, name="issue_id")
    type: Mapped[ParticipationType] = mapped_column(Enum(ParticipationType, name="participation_type_enum"))
    opposeExplanation: Mapped[str | None] = mapped_column(Text, nullable=True, name="oppose_explanation")
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")

    # Relationships
    citizen: Mapped["Citizen"] = relationship("Citizen", back_populates="participations")
    issue: Mapped["Issue"] = relationship("Issue", back_populates="participations")

    __table_args__ = (
        UniqueConstraint("citizen_id", "issue_id", name="uq_citizen_issue_participation"),
    )


from app.models.citizen import Citizen  # noqa: E402
from app.models.issue import Issue  # noqa: E402
