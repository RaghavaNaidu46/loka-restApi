from pydantic import BaseModel, field_validator
import re

EMAIL_REGEX = re.compile(r"^[\w\.\+-]+@[\w\.-]+\.\w+$")

def clean_and_validate_email(v: str) -> str:
    cleaned = v.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email format")
    return cleaned


class SendOtpRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validateEmail(cls, v: str) -> str:
        return clean_and_validate_email(v)


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


class SignupRequest(BaseModel):
    displayName: str
    email: str
    password: str
    confirmPassword: str

    @field_validator("email")
    @classmethod
    def validateEmail(cls, v: str) -> str:
        return clean_and_validate_email(v)


class VerifySignupRequest(BaseModel):
    email: str
    code: str


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validateEmail(cls, v: str) -> str:
        return clean_and_validate_email(v)
