from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import getDb
from app.core.security import decodeToken
from app.core.redis import isTokenBlacklisted
from app.models.citizen import Citizen, VerificationStatus, AccountStatus

bearerScheme = HTTPBearer()


async def getCurrentCitizen(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearerScheme)],
    db: Annotated[AsyncSession, Depends(getDb)],
) -> Citizen:
    token = credentials.credentials
    credentialsException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if await isTokenBlacklisted(token):
        raise credentialsException

    payload = decodeToken(token)
    if not payload or payload.get("type") != "access":
        raise credentialsException

    citizenId = payload.get("sub")
    result = await db.execute(select(Citizen).where(Citizen.id == citizenId))
    citizen = result.scalar_one_or_none()

    if not citizen:
        raise credentialsException

    if citizen.accountStatus != AccountStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or deleted",
        )

    return citizen


async def getVerifiedCitizen(
    citizen: Annotated[Citizen, Depends(getCurrentCitizen)],
) -> Citizen:
    if citizen.verificationStatus != VerificationStatus.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aadhaar verification required to perform this action",
        )
    return citizen


async def getModeratorCitizen(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearerScheme)],
    db: Annotated[AsyncSession, Depends(getDb)],
) -> Citizen:
    token = credentials.credentials
    credentialsException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if await isTokenBlacklisted(token):
        raise credentialsException

    payload = decodeToken(token)
    if not payload or payload.get("type") != "access":
        raise credentialsException

    if payload.get("role") not in ("moderator", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator access required",
        )

    citizenId = payload.get("sub")
    result = await db.execute(select(Citizen).where(Citizen.id == citizenId))
    citizen = result.scalar_one_or_none()

    if not citizen:
        raise credentialsException

    if citizen.accountStatus != AccountStatus.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or deleted",
        )

    return citizen


async def getOptionalCitizen(
    db: Annotated[AsyncSession, Depends(getDb)],
    credentials: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False)),
) -> Citizen | None:
    if not credentials:
        return None
    token = credentials.credentials
    if await isTokenBlacklisted(token):
        return None
    payload = decodeToken(token)
    if not payload or payload.get("type") != "access":
        return None
    citizenId = payload.get("sub")
    result = await db.execute(select(Citizen).where(Citizen.id == citizenId))
    citizen = result.scalar_one_or_none()
    if not citizen or citizen.accountStatus != AccountStatus.active:
        return None
    return citizen
