import uuid
from pydantic import BaseModel
from app.models.citizen import VerificationStatus, AccountStatus
from app.schemas.district import DistrictResponse


class CitizenPublicResponse(BaseModel):
    id: uuid.UUID
    displayName: str | None
    homeDistrict: DistrictResponse | None
    createdAt: str

    model_config = {"from_attributes": True}


class CitizenMeResponse(BaseModel):
    id: uuid.UUID
    phoneNumber: str | None = None
    email: str | None = None
    displayName: str | None
    verificationStatus: VerificationStatus
    accountStatus: AccountStatus
    homeDistrict: DistrictResponse | None
    livingInDistrict: DistrictResponse | None
    createdAt: str
    lastActiveAt: str | None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    displayName: str | None = None


class UpdateDistrictsRequest(BaseModel):
    livingInDistrictId: uuid.UUID
