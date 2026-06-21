import uuid
import enum
from sqlalchemy import String, Enum, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class EvidenceType(str, enum.Enum):
    photo = "photo"
    video = "video"
    document = "document"


class EvidenceModStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issueId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False, name="issue_id")
    uploadedBy: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("citizens.id"), nullable=False, name="uploaded_by")
    evidenceType: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType, name="evidence_type_enum"), name="evidence_type")
    storageRef: Mapped[str] = mapped_column(String(500), nullable=False, name="storage_ref")
    modStatus: Mapped[EvidenceModStatus] = mapped_column(
        Enum(EvidenceModStatus, name="evidence_mod_status_enum"),
        default=EvidenceModStatus.pending,
        name="mod_status",
    )
    uploadedAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="uploaded_at")

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="evidence")
    uploader: Mapped["Citizen"] = relationship("Citizen")


from app.models.issue import Issue  # noqa: E402
from app.models.citizen import Citizen  # noqa: E402
