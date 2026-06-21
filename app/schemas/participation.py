from pydantic import BaseModel, field_validator
import uuid


class SupportRequest(BaseModel):
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def mustBeConfirmed(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must explicitly confirm this permanent action")
        return v


class OpposeRequest(BaseModel):
    explanation: str
    confirmed: bool

    @field_validator("explanation")
    @classmethod
    def validateExplanation(cls, v: str) -> str:
        if len(v.strip()) < 30:
            raise ValueError("Opposition explanation must be at least 30 characters")
        return v.strip()

    @field_validator("confirmed")
    @classmethod
    def mustBeConfirmed(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must explicitly confirm this permanent action")
        return v


class ParticipationStatusResponse(BaseModel):
    issueId: uuid.UUID
    hasParticipated: bool
    participationType: str | None = None
