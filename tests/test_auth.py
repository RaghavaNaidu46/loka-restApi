# pyrefly: ignore [missing-import]
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def testSendOtp(httpClient: AsyncClient):
    response = await httpClient.post(
        "/auth/send-otp",
        json={"email": "tester_unit@loka.test"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "OTP sent successfully"


@pytest.mark.asyncio
async def testVerifyOtp(httpClient: AsyncClient):
    # 1. Trigger OTP send
    email = "tester_unit_verify@loka.test"
    await httpClient.post("/auth/send-otp", json={"email": email})
    
    # 2. Verify with mock OTP code "123456"
    response = await httpClient.post(
        "/auth/verify-otp",
        json={"email": email, "otp": "123456"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" in data


@pytest.mark.asyncio
async def testVerifyOtpInvalidCode(httpClient: AsyncClient):
    email = "tester_unit_invalid@loka.test"
    await httpClient.post("/auth/send-otp", json={"email": email})
    
    # Verify with incorrect OTP code
    response = await httpClient.post(
        "/auth/verify-otp",
        json={"email": email, "otp": "999999"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired OTP"


@pytest.mark.asyncio
async def testVerifyOtpMissingParameters(httpClient: AsyncClient):
    # Send request with missing email parameter
    response = await httpClient.post(
        "/auth/verify-otp",
        json={"otp": "123456"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def testRefreshTokenInvalid(httpClient: AsyncClient):
    # Try to rotate access token using a malformed refresh token string
    response = await httpClient.post(
        "/auth/refresh",
        json={"refreshToken": "invalid-token-signature"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

