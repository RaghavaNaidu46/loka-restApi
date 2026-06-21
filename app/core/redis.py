"""
Redis client with in-memory fallback for development.
When MOCK_REDIS=true, all OTP and token operations run in-process
so you don't need a running Redis instance during local development.
"""
import asyncio
from app.core.config import settings

# ── In-memory fallback store ──────────────────────────────────────────────────
_mockStore: dict[str, str] = {}

_redisClient = None


async def _getReal():
    global _redisClient
    if _redisClient is None:
        import redis.asyncio as aioredis
        _redisClient = aioredis.from_url(
            settings.redisUrl,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redisClient


# ── OTP helpers ───────────────────────────────────────────────────────────────

async def setOtp(email: str, otp: str) -> None:
    if settings.mockRedis:
        _mockStore[f"otp:{email}"] = otp
        return
    client = await _getReal()
    await client.setex(f"otp:{email}", settings.otpExpireSeconds, otp)


async def getOtp(email: str) -> str | None:
    if settings.mockRedis:
        return _mockStore.get(f"otp:{email}")
    client = await _getReal()
    return await client.get(f"otp:{email}")


async def deleteOtp(email: str) -> None:
    if settings.mockRedis:
        _mockStore.pop(f"otp:{email}", None)
        return
    client = await _getReal()
    await client.delete(f"otp:{email}")


# ── Token blacklist helpers ───────────────────────────────────────────────────

async def blacklistToken(token: str, ttlSeconds: int) -> None:
    if settings.mockRedis:
        _mockStore[f"blacklist:{token}"] = "1"
        return
    client = await _getReal()
    await client.setex(f"blacklist:{token}", ttlSeconds, "1")


async def isTokenBlacklisted(token: str) -> bool:
    if settings.mockRedis:
        return f"blacklist:{token}" in _mockStore
    client = await _getReal()
    return await client.exists(f"blacklist:{token}") == 1
