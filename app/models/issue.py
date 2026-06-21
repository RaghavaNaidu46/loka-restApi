import uuid
import enum
from sqlalchemy import String, Text, Integer, Enum, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy import func
from app.core.database import Base


class IssueCategory(str, enum.Enum):
    roads = "roads"
    water = "water"
    electricity = "electricity"
    health = "health"
    education = "education"
    environment = "environment"
    publicSafety = "public_safety"
    governance = "governance"


class IssueStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    underReview = "under_review"
    published = "published"
    active = "active"
    resolved = "resolved"
    archived = "archived"
    rejected = "rejected"
    merged = "merged"


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creatorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="creator_id")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    desiredOutcome: Mapped[str] = mapped_column(Text, nullable=False, name="desired_outcome")
    category: Mapped[IssueCategory] = mapped_column(Enum(IssueCategory, name="issue_category_enum"))
    area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    districtId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=False, name="district_id")
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status_enum"),
        default=IssueStatus.draft,
    )
    supportCount: Mapped[int] = mapped_column(Integer, default=0, name="support_count")
    opposeCount: Mapped[int] = mapped_column(Integer, default=0, name="oppose_count")
    evidenceCount: Mapped[int] = mapped_column(Integer, default=0, name="evidence_count")
    searchVector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True, name="search_vector")
    mergedIntoId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=True, name="merged_into_id"
    )
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")
    updatedAt: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), name="updated_at"
    )

    # Relationships
    creator: Mapped["Citizen"] = relationship("Citizen", back_populates="issues")
    district: Mapped["District"] = relationship("District")
    participations: Mapped[list["Participation"]] = relationship("Participation", back_populates="issue")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="issue")
    evidence: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="issue")

    __table_args__ = (
        Index("ix_issues_search_vector", "search_vector", postgresql_using="gin"),
        Index("ix_issues_district_status", "district_id", "status"),
        Index("ix_issues_category", "category"),
        Index("ix_issues_created_at", "created_at"),
    )


from app.models.citizen import Citizen  # noqa: E402
from app.models.district import District  # noqa: E402
from app.models.participation import Participation  # noqa: E402
from app.models.comment import Comment  # noqa: E402
from app.models.evidence import Evidence  # noqa: E402
