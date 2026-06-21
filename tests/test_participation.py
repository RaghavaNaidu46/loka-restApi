# pyrefly: ignore [missing-import]
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.district import District
from app.models.issue import Issue, IssueStatus, IssueCategory
from app.models.citizen import Citizen
from app.models.participation import Participation, ParticipationType


@pytest.mark.asyncio
async def testSupportIssue(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Make citizen geographically eligible
    verifiedCitizen.homeDistrictId = district.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed active issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Active Issue for Support",
        description="This is an active issue in the same district to allow support.",
        desiredOutcome="Resolve issue with correct feedback.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(
        f"/issues/{issueId}/support",
        json={"confirmed": True}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Support recorded permanently"


@pytest.mark.asyncio
async def testOpposeIssue(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Make citizen geographically eligible
    verifiedCitizen.livingInDistrictId = district.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed active issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Active Issue for Oppose",
        description="This is an active issue in the same district to allow opposition.",
        desiredOutcome="Resolve issue with opposition feedback.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(
        f"/issues/{issueId}/oppose",
        json={
            "explanation": "I oppose this issue because there is already an existing pipeline being built.",
            "confirmed": True
        }
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Opposition recorded permanently"


@pytest.mark.asyncio
async def testGetParticipationStatus(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Make citizen geographically eligible
    verifiedCitizen.homeDistrictId = district.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed active issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Participation Status Issue",
        description="Checking if the user has participated in this issue or not.",
        desiredOutcome="Check participation status correctly.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    # Check status (should be false)
    response = await verifiedClient.get(f"/issues/{issueId}/participation/status")
    assert response.status_code == 200
    assert response.json()["hasParticipated"] is False

    # Participate (Support)
    await verifiedClient.post(f"/issues/{issueId}/support", json={"confirmed": True})

    # Check status again (should be true and type support)
    response2 = await verifiedClient.get(f"/issues/{issueId}/participation/status")
    assert response2.status_code == 200
    assert response2.json()["hasParticipated"] is True
    assert response2.json()["participationType"] == "support"


@pytest.mark.asyncio
async def testSupportNonExistentIssue(
    verifiedClient: AsyncClient
):
    randomIssueId = uuid.uuid4()
    response = await verifiedClient.post(
        f"/issues/{randomIssueId}/support",
        json={"confirmed": True}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"


@pytest.mark.asyncio
async def testSupportDraftIssue(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Make citizen geographically eligible
    verifiedCitizen.homeDistrictId = district.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed draft issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Draft Issue for Support Test",
        description="This draft issue should block any kind of participation.",
        desiredOutcome="Refuse participation on draft issue.",
        category=IssueCategory.roads,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.draft
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(f"/issues/{issueId}/support", json={"confirmed": True})
    assert response.status_code == 400
    assert response.json()["detail"] == "This issue is not open for participation"


@pytest.mark.asyncio
async def testSupportOutsideDistrict(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Seed an otherDistrict to avoid FK constraints violations
    otherDistrict = District(name="Other District", state="Other State", country="India")
    dbSession.add(otherDistrict)
    await dbSession.flush()

    # Set citizen's home and living districts to different valid IDs
    verifiedCitizen.homeDistrictId = otherDistrict.id
    verifiedCitizen.livingInDistrictId = otherDistrict.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed active issue in the main district
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Active Issue in Different District",
        description="This issue is in a district that the citizen doesn't belong to.",
        desiredOutcome="Should fail with 403 Forbidden.",
        category=IssueCategory.roads,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(f"/issues/{issueId}/support", json={"confirmed": True})
    assert response.status_code == 403
    assert response.json()["detail"] == "You can only participate in issues within your home or living-in district"


@pytest.mark.asyncio
async def testSupportTwice(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession,
    verifiedCitizen: Citizen
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Make citizen geographically eligible
    verifiedCitizen.homeDistrictId = district.id
    dbSession.add(verifiedCitizen)
    await dbSession.flush()

    # Seed active issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Double Support Test Issue",
        description="Check if duplicate support requests are handled properly.",
        desiredOutcome="Fail the second support request.",
        category=IssueCategory.roads,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    # First support request (should pass)
    response1 = await verifiedClient.post(f"/issues/{issueId}/support", json={"confirmed": True})
    assert response1.status_code == 200

    # Second support request (should fail)
    response2 = await verifiedClient.post(f"/issues/{issueId}/support", json={"confirmed": True})
    assert response2.status_code == 409
    assert response2.json()["detail"] == "You have already participated in this issue"
