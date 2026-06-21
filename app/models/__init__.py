# Models package — import all so SQLAlchemy discovers all tables
from app.models.district import District
from app.models.citizen import Citizen
from app.models.issue import Issue
from app.models.participation import Participation
from app.models.comment import Comment
from app.models.evidence import Evidence
from app.models.notification import Notification
from app.models.moderation import ModerationAction, Appeal, VerificationRecord
from app.models.comment_like import CommentLike
from app.models.comment_report import CommentReport

__all__ = [
    "District",
    "Citizen",
    "Issue",
    "Participation",
    "Comment",
    "CommentLike",
    "CommentReport",
    "Evidence",
    "Notification",
    "ModerationAction",
    "Appeal",
    "VerificationRecord",
]
