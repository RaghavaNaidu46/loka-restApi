# pyrefly: ignore [missing-import]
import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.district import District
from app.models.issue import Issue, IssueStatus, IssueCategory
from app.models.citizen import Citizen, VerificationStatus
from app.core.security import createAccessToken


@pytest.mark.asyncio
async def testCreateDraftIssue(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession
):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Create issue request body
    requestBody = {
        "title": "Road repair request in Sector 5",
        "description": "The main road in Sector 5 has multiple large potholes causing severe accidents.",
        "desiredOutcome": "Resurfacing the entire stretch of road.",
        "category": "roads",
        "location": {
            "area": "Sector 5",
            "city": "Test City",
            "districtId": str(district.id)
        }
    }

    # Expunge all to keep session clean
    dbSession.expunge_all()

    response = await verifiedClient.post("/issues", json=requestBody)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Road repair request in Sector 5"
    assert data["status"] == "draft"
    assert data["district"]["id"] == str(district.id)


@pytest.mark.asyncio
async def testUpdateDraftIssue(
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

    # Seed draft issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Potholes in Main Street",
        description="The main street has severe potholes requiring urgent repair from the municipality.",
        desiredOutcome="Smooth road surface for easy vehicle transport.",
        category=IssueCategory.roads,
        area="Main Street",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.draft
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    # Update title
    updateBody = {
        "title": "Severely damaged Potholes in Main Street"
    }

    response = await verifiedClient.patch(f"/issues/{issueId}", json=updateBody)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Severely damaged Potholes in Main Street"


@pytest.mark.asyncio
async def testSubmitDraftIssue(
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

    # Seed draft issue (use roads instead of garbage)
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Garbage dumping on park side",
        description="Garbage is being dumped directly on the park side leading to bad smell.",
        desiredOutcome="Clear the garbage and install warning signs.",
        category=IssueCategory.roads,
        area="Park Side",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.draft
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(f"/issues/{issueId}/submit")
    assert response.status_code == 200
    assert "message" in response.json()


@pytest.mark.asyncio
async def testGetRelatedIssues(
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

    # Seed two active issues with same category and district
    issue1 = Issue(
        creatorId=verifiedCitizen.id,
        title="Water pollution issue one",
        description="The water supply in Sector 1 is contaminated with mud and sand particles.",
        desiredOutcome="Install a new water filter system.",
        category=IssueCategory.water,
        area="Sector 1",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    issue2 = Issue(
        creatorId=verifiedCitizen.id,
        title="Water pollution issue two",
        description="Sector 2 water supply is yellowish and smells extremely foul.",
        desiredOutcome="Flush the main water supply pipeline.",
        category=IssueCategory.water,
        area="Sector 2",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add_all([issue1, issue2])
    await dbSession.flush()

    issue1Id = issue1.id
    issue2Id = issue2.id
    dbSession.expunge_all()

    response = await verifiedClient.get(f"/issues/{issue1Id}/related")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["id"] == str(issue2Id)


@pytest.mark.asyncio
async def testCreateIssueWithInvalidDistrict(
    verifiedClient: AsyncClient
):
    randomDistrictId = uuid.uuid4()
    requestBody = {
        "title": "Water leakage in Sector 3",
        "description": "There is a massive water leak from the main valve in Sector 3.",
        "desiredOutcome": "Fix the leakage immediately to prevent wastage.",
        "category": "water",
        "location": {
            "area": "Sector 3",
            "city": "Test City",
            "districtId": str(randomDistrictId)
        }
    }

    response = await verifiedClient.post("/issues", json=requestBody)
    assert response.status_code == 404
    assert response.json()["detail"] == "District not found"


@pytest.mark.asyncio
async def testCreateIssueValidationError(
    verifiedClient: AsyncClient,
    dbSession: AsyncSession
):
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Send title that is too short
    requestBody = {
        "title": "Short",
        "description": "Too short description to validate the API response.",
        "desiredOutcome": "Outcome is long enough.",
        "category": "water",
        "location": {
            "area": "Sector 3",
            "city": "Test City",
            "districtId": str(district.id)
        }
    }

    dbSession.expunge_all()

    response = await verifiedClient.post("/issues", json=requestBody)
    assert response.status_code == 422


@pytest.mark.asyncio
async def testUpdateNonExistentIssue(
    verifiedClient: AsyncClient
):
    randomIssueId = uuid.uuid4()
    updateBody = {
        "title": "Updating non-existent issue"
    }

    response = await verifiedClient.patch(f"/issues/{randomIssueId}", json=updateBody)
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"


@pytest.mark.asyncio
async def testUpdateIssueNotOwned(
    verifiedClient: AsyncClient,
    httpClient: AsyncClient,
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

    # Seed an issue owned by verifiedCitizen (use roads instead of garbage)
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Park cleaning request",
        description="The children's park is filled with plastic wrappers and garbage.",
        desiredOutcome="Organize a cleanliness drive and add garbage bins.",
        category=IssueCategory.roads,
        area="Park",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.draft
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed another citizen
    otherCitizen = Citizen(
        email="other_owner@loka.test",
        displayName="Other Citizen",
        verificationStatus=VerificationStatus.verified,
        role="citizen"
    )
    dbSession.add(otherCitizen)
    await dbSession.flush()

    issueId = issue.id
    otherCitizenId = otherCitizen.id
    otherCitizenRole = otherCitizen.role
    dbSession.expunge_all()

    # Login as otherCitizen
    otherToken = createAccessToken(str(otherCitizenId), role=otherCitizenRole)
    otherHeaders = {"Authorization": f"Bearer {otherToken}"}

    # Try updating the issue
    response = await httpClient.patch(
        f"/issues/{issueId}",
        headers=otherHeaders,
        json={"title": "This should fail because I don't own it"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"


@pytest.mark.asyncio
async def testUpdateNonDraftIssue(
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

    # Seed an active issue owned by verifiedCitizen (use electricity instead of sewerage)
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Drainage cleaning request",
        description="The open drainage in Sector 4 is clogged causing dirty water overflow.",
        desiredOutcome="Clean and cover the open drainage lines.",
        category=IssueCategory.electricity,
        area="Sector 4",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    # Try updating active issue
    response = await verifiedClient.patch(
        f"/issues/{issueId}",
        json={"title": "Change title of active issue"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only draft issues can be edited"


@pytest.mark.asyncio
async def testSubmitNonDraftIssue(
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

    # Seed an active issue owned by verifiedCitizen
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Traffic signal installation",
        description="Intersection of block A and B needs traffic signals due to high collision rates.",
        desiredOutcome="Install functioning traffic signals and crossing lines.",
        category=IssueCategory.roads,
        area="Intersection",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    issueId = issue.id
    dbSession.expunge_all()

    response = await verifiedClient.post(f"/issues/{issueId}/submit")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only draft issues can be submitted"
