import random
import uuid
from locust import HttpUser, task, between


class LokaUser(HttpUser):
    # Simulated think time between user requests
    wait_time = between(1, 4)

    def on_start(self) -> None:
        self.issueIds = []
        self.commentIds = []
        self.performAuthentication()

    def performAuthentication(self) -> None:
        # Generate a unique testing email address
        uniqueEmail = f"tester_{uuid.uuid4().hex[:8]}@loka.test"

        # 1. Send Mock OTP
        sendOtpBody = {"email": uniqueEmail}
        with self.client.post(
            "/auth/send-otp",
            json=sendOtpBody,
            name="/auth/send-otp",
            catch_response=True
        ) as response:
            if response.status_code != 200:
                response.failure(f"Failed to send OTP: {response.text}")
                return

        # 2. Verify OTP using default mock code "123456"
        verifyOtpBody = {
            "email": uniqueEmail,
            "otp": "123456"
        }
        with self.client.post(
            "/auth/verify-otp",
            json=verifyOtpBody,
            name="/auth/verify-otp",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    responseData = response.json()
                    accessToken = responseData.get("accessToken")
                    if accessToken:
                        # Set JWT header for all subsequent API requests
                        self.client.headers["Authorization"] = f"Bearer {accessToken}"
                    else:
                        response.failure("accessToken missing in response payload")
                except Exception as e:
                    response.failure(f"Failed to parse JSON response: {str(e)}")
            else:
                response.failure(f"Failed to verify OTP: {response.text}")

    @task(35)
    def feedNearby(self) -> None:
        with self.client.get(
            "/feed/nearby?limit=10",
            name="/feed/nearby",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    items = response.json().get("items", [])
                    # Populate issueIds for other tasks
                    self.issueIds = [item["id"] for item in items if "id" in item]
                except Exception as e:
                    response.failure(f"Failed to parse nearby feed JSON: {str(e)}")
            else:
                response.failure(f"Failed to fetch nearby feed: {response.text}")

    @task(20)
    def feedPriority(self) -> None:
        self.client.get("/feed/priority?limit=10", name="/feed/priority")

    @task(30)
    def issueDetailAndComments(self) -> None:
        if not self.issueIds:
            # Fallback to feed loading if no issues available yet
            self.feedNearby()
        if not self.issueIds:
            return

        randomIssueId = random.choice(self.issueIds)
        # 1. Fetch Issue Details
        self.client.get(f"/issues/{randomIssueId}", name="/issues/{id}")

        # 2. Fetch Comments for the Issue
        with self.client.get(
            f"/issues/{randomIssueId}/comments?sortBy=top&stance=all",
            name="/issues/{id}/comments",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    items = response.json().get("items", [])
                    self.commentIds = [item["id"] for item in items if "id" in item]
                except Exception as e:
                    response.failure(f"Failed to parse comments JSON: {str(e)}")

    @task(10)
    def addComment(self) -> None:
        if not self.issueIds:
            self.feedNearby()
        if not self.issueIds:
            return

        randomIssueId = random.choice(self.issueIds)
        commentBody = {
            "text": f"Load testing comment by Locust user: {uuid.uuid4().hex[:6]}"
        }
        self.client.post(
            f"/issues/{randomIssueId}/comments",
            json=commentBody,
            name="/issues/{id}/comments"
        )

    @task(5)
    def likeComment(self) -> None:
        if not self.issueIds:
            self.feedNearby()
        if not self.issueIds:
            return

        randomIssueId = random.choice(self.issueIds)
        
        # Ensure we have comments to like
        if not self.commentIds:
            self.issueDetailAndComments()
        if not self.commentIds:
            return

        randomCommentId = random.choice(self.commentIds)
        # Like a comment
        self.client.post(
            f"/issues/{randomIssueId}/comments/{randomCommentId}/like",
            json={},
            name="/issues/{id}/comments/{commentId}/like"
        )
