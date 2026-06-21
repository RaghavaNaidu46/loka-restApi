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
async def testListPendingIssues(
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

    # Seed an issue with status submitted
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Pending Issue for Moderation",
        description="This issue has been submitted and is pending moderator approval.",
        desiredOutcome="Approve this issue.",
        category=IssueCategory.roads,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.submitted
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed a moderator citizen
    moderator = Citizen(
        email="moderator_test@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    # Generate moderator token
    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await httpClient.get("/moderation/pending", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert any(item["id"] == str(issue.id) for item in data["items"])


@pytest.mark.asyncio
async def testApproveIssue(
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

    # Seed submitted issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Submitted Issue to Approve",
        description="This issue will be approved by the test moderator.",
        desiredOutcome="Approval achieved.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.submitted
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed moderator citizen
    moderator = Citizen(
        email="moderator_approve@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await httpClient.post(
        f"/moderation/issues/{issue.id}/approve",
        headers=headers,
        json="Valid reason for approval"
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Issue approved and set to active"

    # Reload from DB and verify status is active
    await dbSession.refresh(issue)
    assert issue.status == IssueStatus.active


@pytest.mark.asyncio
async def testRejectIssue(
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

    # Seed submitted issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Submitted Issue to Reject",
        description="This issue will be rejected due to insufficient details.",
        desiredOutcome="Rejection output.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.submitted
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed moderator citizen
    moderator = Citizen(
        email="moderator_reject@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await httpClient.post(
        f"/moderation/issues/{issue.id}/reject",
        headers=headers,
        json="Rejection reason details"
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Issue rejected"

    # Reload from DB and verify status is rejected
    await dbSession.refresh(issue)
    assert issue.status == IssueStatus.rejected


@pytest.mark.asyncio
async def testRequestClarification(
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

    # Seed submitted issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Submitted Issue to Clarify",
        description="This issue needs some more clarification on photos.",
        desiredOutcome="Clarification request.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.submitted
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed moderator citizen
    moderator = Citizen(
        email="moderator_clarify@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    response = await httpClient.post(
        f"/moderation/issues/{issue.id}/clarify",
        headers=headers,
        json="Please add photos for clarification."
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Clarification requested and creator notified"


@pytest.mark.asyncio
async def testMergeIssue(
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

    # Seed issue1 (draft/active) and issue2 (duplicate to be merged)
    issue1 = Issue(
        creatorId=verifiedCitizen.id,
        title="Water leak in block A",
        description="Water is leaking from the pipeline in block A since yesterday.",
        desiredOutcome="Fix the leak.",
        category=IssueCategory.water,
        area="Block A",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    issue2 = Issue(
        creatorId=verifiedCitizen.id,
        title="Leakage of water in block A",
        description="Duplicate entry for water leak in block A.",
        desiredOutcome="Merge this issue.",
        category=IssueCategory.water,
        area="Block A",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add_all([issue1, issue2])
    await dbSession.flush()

    # Seed moderator citizen
    moderator = Citizen(
        email="moderator_merge@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    # Merge issue2 into issue1
    response = await httpClient.post(
        f"/moderation/issues/{issue2.id}/merge",
        headers=headers,
        json={
            "targetIssueId": str(issue1.id),
            "reason": "Duplicate issue merged"
        }
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Issue merged"
    assert response.json()["mergedIntoId"] == str(issue1.id)

    # Reload issue2 and verify status is merged
    await dbSession.refresh(issue2)
    assert issue2.status == IssueStatus.merged
    assert issue2.mergedIntoId == issue1.id


@pytest.mark.asyncio
async def testModerationAccessDenied(
    verifiedClient: AsyncClient
):
    # Try calling list pending moderator endpoint with verifiedClient (citizen role)
    response = await verifiedClient.get("/moderation/pending")
    assert response.status_code == 403
    assert response.json()["detail"] == "Moderator access required"


@pytest.mark.asyncio
async def testApproveNonExistentIssue(
    httpClient: AsyncClient,
    dbSession: AsyncSession
):
    # Seed moderator citizen
    moderator = Citizen(
        email="moderator_unauth@loka.test",
        displayName="Moderator User",
        verificationStatus=VerificationStatus.verified,
        role="moderator"
    )
    dbSession.add(moderator)
    await dbSession.flush()

    token = createAccessToken(str(moderator.id), role=moderator.role)
    headers = {"Authorization": f"Bearer {token}"}

    randomIssueId = uuid.uuid4()
    response = await httpClient.post(
        f"/moderation/issues/{randomIssueId}/approve",
        headers=headers,
        json="Approve non-existent issue"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"
