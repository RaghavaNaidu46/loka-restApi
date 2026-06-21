import uuid
from pydantic import BaseModel, field_validator
from app.models.issue import IssueCategory, IssueStatus
from app.schemas.district import DistrictResponse


class IssueLocationSchema(BaseModel):
    area: str | None = None
    city: str
    districtId: uuid.UUID


class CreateIssueRequest(BaseModel):
    title: str
    description: str
    desiredOutcome: str
    category: IssueCategory
    location: IssueLocationSchema

    @field_validator("title")
    @classmethod
    def validateTitle(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("Title must be at least 10 characters")
        return v.strip()

    @field_validator("description")
    @classmethod
    def validateDescription(cls, v: str) -> str:
        if len(v.strip()) < 30:
            raise ValueError("Description must be at least 30 characters")
        return v.strip()

    @field_validator("desiredOutcome")
    @classmethod
    def validateDesiredOutcome(cls, v: str) -> str:
        if len(v.strip()) < 20:
            raise ValueError("Desired outcome must be at least 20 characters")
        return v.strip()


class UpdateIssueRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    desiredOutcome: str | None = None
    category: IssueCategory | None = None
    location: IssueLocationSchema | None = None


class IssueResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    desiredOutcome: str
    category: IssueCategory
    area: str | None
    city: str
    district: DistrictResponse
    status: IssueStatus
    supportCount: int
    opposeCount: int
    evidenceCount: int
    creatorDisplayName: str | None
    createdAt: str
    updatedAt: str
    participationStatus: str | None = None  # injected by endpoint

    model_config = {"from_attributes": True}


class IssueListResponse(BaseModel):
    items: list[IssueResponse]
    total: int
    cursor: str | None = None
