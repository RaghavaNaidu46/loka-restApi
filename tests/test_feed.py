# pyrefly: ignore [missing-import]
import pytest
import time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.district import District
from app.models.issue import Issue, IssueStatus, IssueCategory
from app.models.citizen import Citizen


@pytest.mark.asyncio
async def testFeeds(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Ensure at least one district exists
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Test Load and Performance Issue",
        description="A detailed test description for Loka API performance unit tests.",
        desiredOutcome="Smooth latency and zero errors.",
        category=IssueCategory.roads,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    # 1. Test Nearby Feed with latency assertion
    startTime = time.perf_counter()
    response = await verifiedClient.get("/feed/nearby?limit=5")
    duration = time.perf_counter() - startTime

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Assert feed latency is below 150ms (0.15 seconds)
    assert duration < 0.15, f"Nearby feed took too long: {duration:.4f}s (max 0.15s)"

    # 2. Test Priority Feed with latency assertion
    startTime = time.perf_counter()
    response = await verifiedClient.get("/feed/priority?limit=5")
    duration = time.perf_counter() - startTime

    assert response.status_code == 200
    assert duration < 0.15, f"Priority feed took too long: {duration:.4f}s (max 0.15s)"


@pytest.mark.asyncio
async def testFeedLimitValidationError(verifiedClient: AsyncClient):
    # Try fetching nearby feed with a limit exceeding the max constraint of 50
    response = await verifiedClient.get("/feed/nearby?limit=100")
    assert response.status_code == 422


@pytest.mark.asyncio
async def testFeedOffsetValidationError(verifiedClient: AsyncClient):
    # Try fetching nearby feed with a negative offset constraint
    response = await verifiedClient.get("/feed/nearby?offset=-5")
    assert response.status_code == 422

