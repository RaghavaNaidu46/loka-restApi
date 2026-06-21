# pyrefly: ignore [missing-import]
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.district import District
from app.models.issue import Issue, IssueStatus, IssueCategory
from app.models.citizen import Citizen, VerificationStatus
from app.models.comment import Comment, CommentStatus
from app.core.security import createAccessToken


@pytest.mark.asyncio
async def testCommentsEngine(
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

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Comments Test",
        description="Testing threaded comments and liking.",
        desiredOutcome="Verifying comments engine behaviour.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    # 1. Post a Root Comment
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments",
        json={"text": "This is a root comment from unit tests."}
    )
    assert response.status_code == 200
    rootComment = response.json()
    assert rootComment["text"] == "This is a root comment from unit tests."
    assert rootComment["parentId"] is None

    # 2. Post a Threaded Reply
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments",
        json={
            "text": "This is a threaded reply to the root comment.",
            "parentId": rootComment["id"]
        }
    )
    assert response.status_code == 200
    replyComment = response.json()
    assert replyComment["parentId"] == rootComment["id"]

    # 3. Like the Root Comment
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments/{rootComment['id']}/like"
    )
    assert response.status_code == 200

    # 4. Fetch Comments and verify counts, likes, and roles
    response = await verifiedClient.get(f"/issues/{issue.id}/comments?sortBy=top")
    assert response.status_code == 200
    commentsData = response.json()
    assert commentsData["total"] == 2
    
    commentsList = commentsData["items"]
    # Check that root comment is returned with correct likesCount & hasLiked
    rootInList = next(c for c in commentsList if c["id"] == rootComment["id"])
    assert rootInList["likesCount"] == 1
    assert rootInList["hasLiked"] is True
    assert rootInList["isAuthor"] is True  # Commenter is issue creator

    # 5. Report Root Comment 3 times and check that it is hidden
    # Seed 2 other citizens to report it (since a citizen can only report once)
    otherCitizen1 = Citizen(
        email="report1@loka.test",
        displayName="Reporter One",
        verificationStatus=VerificationStatus.verified,
        role="citizen"
    )
    otherCitizen2 = Citizen(
        email="report2@loka.test",
        displayName="Reporter Two",
        verificationStatus=VerificationStatus.verified,
        role="citizen"
    )
    dbSession.add_all([otherCitizen1, otherCitizen2])
    await dbSession.flush()

    # Report 1: by verifiedCitizen (current client)
    response = await verifiedClient.post(f"/issues/{issue.id}/comments/{rootComment['id']}/report")
    assert response.status_code == 200

    # Report 2: by otherCitizen1
    token1 = createAccessToken(str(otherCitizen1.id), role=otherCitizen1.role)
    headers1 = {"Authorization": f"Bearer {token1}"}
    response = await httpClient.post(
        f"/issues/{issue.id}/comments/{rootComment['id']}/report",
        headers=headers1
    )
    assert response.status_code == 200

    # Report 3: by otherCitizen2
    token2 = createAccessToken(str(otherCitizen2.id), role=otherCitizen2.role)
    headers2 = {"Authorization": f"Bearer {token2}"}
    response = await httpClient.post(
        f"/issues/{issue.id}/comments/{rootComment['id']}/report",
        headers=headers2
    )
    assert response.status_code == 200

    # Reload comment from DB and check that it is hidden
    commentResult = await dbSession.execute(select(Comment).where(Comment.id == rootComment["id"]))
    comment = commentResult.scalar_one()
    await dbSession.refresh(comment)
    assert comment.modStatus == CommentStatus.hidden


@pytest.mark.asyncio
async def testCommentOnNonExistentIssue(verifiedClient: AsyncClient):
    import uuid
    randomIssueId = uuid.uuid4()
    response = await verifiedClient.post(
        f"/issues/{randomIssueId}/comments",
        json={"text": "This should fail because the issue does not exist."}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"


@pytest.mark.asyncio
async def testCommentUnauthenticated(httpClient: AsyncClient, dbSession: AsyncSession, verifiedCitizen: Citizen):
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Unauth Test",
        description="Testing unauthenticated comments.",
        desiredOutcome="Should fail with 401.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Request comment posting without credentials
    response = await httpClient.post(
        f"/issues/{issue.id}/comments",
        json={"text": "This should fail because we are not authenticated."}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def testThreadedReplyDepthExceeded(
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

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Threaded Depth Test",
        description="Testing threaded comment reply limits.",
        desiredOutcome="Verifying depth limit logic.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    # 1. Post a Root Comment
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments",
        json={"text": "This is a root comment."}
    )
    rootComment = response.json()

    # 2. Post a Threaded Reply (Level 1)
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments",
        json={
            "text": "This is a reply to the root comment.",
            "parentId": rootComment["id"]
        }
    )
    replyComment = response.json()

    # 3. Try to Post a Reply to the Reply (Level 2) - should fail
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments",
        json={
            "text": "This should fail because nested replies are limited to 1 level.",
            "parentId": replyComment["id"]
        }
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Nested replies are limited to 1 level"


@pytest.mark.asyncio
async def testLikeNonExistentComment(verifiedClient: AsyncClient, dbSession: AsyncSession, verifiedCitizen: Citizen):
    import uuid
    # Setup district
    districtResult = await dbSession.execute(select(District).limit(1))
    district = districtResult.scalar_one_or_none()
    if not district:
        district = District(name="Test District", state="Test State", country="India")
        dbSession.add(district)
        await dbSession.flush()

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Like Failure Test",
        description="Testing non-existent comment liking.",
        desiredOutcome="Should fail with 404.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    randomCommentId = uuid.uuid4()
    response = await verifiedClient.post(
        f"/issues/{issue.id}/comments/{randomCommentId}/like"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Comment not found"


@pytest.mark.asyncio
async def testReportCommentTwice(
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

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Double Report Test",
        description="Testing reporting a comment multiple times.",
        desiredOutcome="Verifying idempotent response.",
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

    # Post comment
    response = await verifiedClient.post(
        f"/issues/{issueId}/comments",
        json={"text": "This comment will be reported twice."}
    )
    comment = response.json()
    commentId = comment["id"]

    # Report once
    response1 = await verifiedClient.post(f"/issues/{issueId}/comments/{commentId}/report")
    assert response1.status_code == 200
    assert response1.json()["message"] == "Comment reported for review"

    # Report twice (idempotent message check)
    response2 = await verifiedClient.post(f"/issues/{issueId}/comments/{commentId}/report")
    assert response2.status_code == 200
    assert response2.json()["message"] == "Comment already reported"


@pytest.mark.asyncio
async def testLikeCommentUnauthenticated(
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

    # Seed an issue
    issue = Issue(
        creatorId=verifiedCitizen.id,
        title="Issue for Unauth Like Test",
        description="Testing unauthenticated comment liking.",
        desiredOutcome="Should fail with 403.",
        category=IssueCategory.water,
        area="Test Area",
        city="Test City",
        districtId=district.id,
        status=IssueStatus.active
    )
    dbSession.add(issue)
    await dbSession.flush()

    # Seed comment directly in database (to bypass verifiedClient post)
    comment = Comment(
        citizenId=verifiedCitizen.id,
        issueId=issue.id,
        text="This comment will be liked without auth.",
        modStatus=CommentStatus.visible
    )
    dbSession.add(comment)
    await dbSession.flush()

    issueId = issue.id
    commentId = comment.id
    dbSession.expunge_all()

    # Try to like with unauthenticated httpClient (no Authorization header is set on httpClient)
    likeResponse = await httpClient.post(
        f"/issues/{issueId}/comments/{commentId}/like"
    )
    assert likeResponse.status_code == 403

