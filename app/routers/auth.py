import random
import string
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.database import getDb
from app.core.security import createAccessToken, createRefreshToken, decodeToken
from app.core.redis import setOtp, getOtp, deleteOtp, blacklistToken, isTokenBlacklisted
from app.core.config import settings
from app.models.citizen import Citizen
from app.schemas.auth import (
    SendOtpRequest,
    VerifyOtpRequest,
    TokenResponse,
    RefreshRequest,
    MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def generateOtp() -> str:
    if settings.mockOtp:
        return settings.mockOtpCode
    return "".join(random.choices(string.digits, k=6))


@router.post("/send-otp", response_model=MessageResponse, summary="Send OTP to email address")
async def sendOtp(
    body: SendOtpRequest,
    db: Annotated[AsyncSession, Depends(getDb)],
):
    otp = generateOtp()
    await setOtp(body.email, otp)
    print(f"[LokaDebug] Generated OTP for {body.email}: {otp}")

    if settings.mockOtp:
        print(f"[DEV] OTP for {body.email}: {otp}")
    else:
        # Send real SMTP email containing the verification OTP code
        from app.services.email_service import sendEmail, getOtpEmailTemplate
        try:
            htmlContent = getOtpEmailTemplate(otp)
            await sendEmail(body.email, "Loka Verification Code", htmlContent)
        except Exception as e:
            print(f"[ERROR] Failed to send SMTP email: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to deliver verification email: {str(e)}"
            )

    return MessageResponse(message="OTP sent successfully")


@router.post("/verify-otp", response_model=TokenResponse, summary="Verify OTP and receive tokens")
async def verifyOtp(
    body: VerifyOtpRequest,
    db: Annotated[AsyncSession, Depends(getDb)],
):
    storedOtp = await getOtp(body.email)
    if not storedOtp or storedOtp != body.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    await deleteOtp(body.email)

    # Get or create citizen
    result = await db.execute(select(Citizen).where(Citizen.email == body.email))
    citizen = result.scalar_one_or_none()

    if not citizen:
        citizen = Citizen(email=body.email)
        if body.email.endswith("@loka.test"):
            from app.models.citizen import VerificationStatus
            citizen.verificationStatus = VerificationStatus.verified
        db.add(citizen)
        await db.flush()

    # Update last active
    await db.execute(
        update(Citizen)
        .where(Citizen.id == citizen.id)
        .values(lastActiveAt=datetime.now(timezone.utc))
    )

    accessToken = createAccessToken(str(citizen.id), role=citizen.role)
    refreshToken = createRefreshToken(str(citizen.id))

    return TokenResponse(accessToken=accessToken, refreshToken=refreshToken)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate access token using refresh token")
async def refreshToken(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(getDb)],
):
    if await isTokenBlacklisted(body.refreshToken):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    payload = decodeToken(body.refreshToken)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    citizenId = payload.get("sub")
    result = await db.execute(select(Citizen).where(Citizen.id == citizenId))
    citizen = result.scalar_one_or_none()
    if not citizen:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Citizen not found")

    # Blacklist old refresh token
    expiry = payload.get("exp", 0)
    ttl = max(0, expiry - int(datetime.now(timezone.utc).timestamp()))
    await blacklistToken(body.refreshToken, ttl)

    newAccessToken = createAccessToken(str(citizen.id), role=citizen.role)
    newRefreshToken = createRefreshToken(str(citizen.id))

    return TokenResponse(accessToken=newAccessToken, refreshToken=newRefreshToken)


@router.post("/logout", response_model=MessageResponse, summary="Logout and invalidate tokens")
async def logout(
    body: RefreshRequest,
):
    payload = decodeToken(body.refreshToken)
    if payload:
        expiry = payload.get("exp", 0)
        ttl = max(0, expiry - int(datetime.now(timezone.utc).timestamp()))
        await blacklistToken(body.refreshToken, ttl)

    return MessageResponse(message="Logged out successfully")
