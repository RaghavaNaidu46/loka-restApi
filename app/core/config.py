from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List
import json


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Loka"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str
    SYNC_DATABASE_URL: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    MOCK_REDIS: bool = True

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OTP
    OTP_EXPIRE_SECONDS: int = 300
    MOCK_OTP: bool = True
    MOCK_OTP_CODE: str = "123456"

    # Aadhaar
    MOCK_VERIFICATION: bool = True
    DEBUG_OCR: bool = False

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    EMAIL_FROM: str = ""
    TEST_EMAIL: str = ""

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parseOrigins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Convenience properties (camelCase for use in code)
    @property
    def appName(self) -> str:
        return self.APP_NAME

    @property
    def appEnv(self) -> str:
        return self.APP_ENV

    @property
    def debug(self) -> bool:
        return self.DEBUG

    @property
    def databaseUrl(self) -> str:
        return self.DATABASE_URL


    @property
    def syncDatabaseUrl(self) -> str:
        return self.SYNC_DATABASE_URL

    @property
    def redisUrl(self) -> str:
        return self.REDIS_URL

    @property
    def secretKey(self) -> str:
        return self.SECRET_KEY

    @property
    def algorithm(self) -> str:
        return self.ALGORITHM

    @property
    def accessTokenExpireMinutes(self) -> int:
        return self.ACCESS_TOKEN_EXPIRE_MINUTES

    @property
    def refreshTokenExpireDays(self) -> int:
        return self.REFRESH_TOKEN_EXPIRE_DAYS

    @property
    def otpExpireSeconds(self) -> int:
        return self.OTP_EXPIRE_SECONDS

    @property
    def mockOtp(self) -> bool:
        return self.MOCK_OTP

    @property
    def mockOtpCode(self) -> str:
        return self.MOCK_OTP_CODE

    @property
    def mockRedis(self) -> bool:
        return self.MOCK_REDIS

    @property
    def mockVerification(self) -> bool:
        return self.MOCK_VERIFICATION

    @property
    def debugOcr(self) -> bool:
        return self.DEBUG_OCR

    @property
    def uploadDir(self) -> str:
        return self.UPLOAD_DIR

    @property
    def allowedOrigins(self) -> List[str]:
        return self.ALLOWED_ORIGINS

    @property
    def smtpHost(self) -> str:
        return self.SMTP_HOST

    @property
    def smtpPort(self) -> int:
        return self.SMTP_PORT

    @property
    def smtpUser(self) -> str:
        return self.SMTP_USER

    @property
    def smtpPass(self) -> str:
        return self.SMTP_PASS

    @property
    def emailFrom(self) -> str:
        return self.EMAIL_FROM

    @property
    def testEmail(self) -> str:
        return self.TEST_EMAIL

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
