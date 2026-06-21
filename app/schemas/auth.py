from pydantic import BaseModel, field_validator
import re


class SendOtpRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validateEmail(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", cleaned):
            raise ValueError("Invalid email format")
        return cleaned


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"


class RefreshRequest(BaseModel):
    refreshToken: str


class MessageResponse(BaseModel):
    message: str
