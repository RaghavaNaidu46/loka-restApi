from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from app.core.config import settings


def createAccessToken(citizenId: str, role: str = "citizen") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.accessTokenExpireMinutes)
    payload = {
        "sub": citizenId,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secretKey, algorithm=settings.algorithm)


def createRefreshToken(citizenId: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refreshTokenExpireDays)
    payload = {
        "sub": citizenId,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secretKey, algorithm=settings.algorithm)


def decodeToken(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secretKey, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


import bcrypt


def hashPassword(password: str) -> str:
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
    try:
        return bcrypt.checkpw(plainPassword.encode('utf-8'), hashedPassword.encode('utf-8'))
    except Exception:
        return False

