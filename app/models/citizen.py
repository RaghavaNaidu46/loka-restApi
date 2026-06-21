import uuid
import enum
from sqlalchemy import String, Enum, ForeignKey, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class VerificationStatus(str, enum.Enum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class AccountStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class Citizen(Base):
    __tablename__ = "citizens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phoneNumber: Mapped[str | None] = mapped_column(String(15), unique=True, nullable=True, name="phone_number")
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, name="email")
    passwordHash: Mapped[str | None] = mapped_column(String(255), nullable=True, name="password_hash")
    isEmailVerified: Mapped[bool] = mapped_column(default=False, name="is_email_verified")
    displayName: Mapped[str | None] = mapped_column(String(80), nullable=True, name="display_name")
    originalName: Mapped[str | None] = mapped_column(String(100), nullable=True, name="original_name")
    dateOfBirth: Mapped[str | None] = mapped_column(String(20), nullable=True, name="date_of_birth")
    address: Mapped[str | None] = mapped_column(Text, nullable=True, name="address")
    aadhaarNumber: Mapped[str | None] = mapped_column(String(20), nullable=True, name="aadhaar_number")
    verificationStatus: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status_enum"),
        default=VerificationStatus.unverified,
        name="verification_status",
    )
    role: Mapped[str] = mapped_column(String(20), default="citizen")
    homeDistrictId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("districts.id"), nullable=True, name="home_district_id"
    )
    livingInDistrictId: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("districts.id"), nullable=True, name="living_in_district_id"
    )
    accountStatus: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status_enum"),
        default=AccountStatus.active,
        name="account_status",
    )
    createdAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), name="created_at")
    lastActiveAt: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, name="last_active_at")

    # Relationships
    homeDistrict: Mapped["District"] = relationship("District", foreign_keys=[homeDistrictId])
    livingInDistrict: Mapped["District"] = relationship("District", foreign_keys=[livingInDistrictId])
    issues: Mapped[list["Issue"]] = relationship("Issue", back_populates="creator")
    participations: Mapped[list["Participation"]] = relationship("Participation", back_populates="citizen")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="citizen")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="citizen")


from app.models.district import District  # noqa: E402
from app.models.issue import Issue  # noqa: E402
from app.models.participation import Participation  # noqa: E402
from app.models.comment import Comment  # noqa: E402
from app.models.notification import Notification  # noqa: E402
