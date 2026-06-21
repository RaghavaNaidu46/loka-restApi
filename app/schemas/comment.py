import uuid
from pydantic import BaseModel, field_validator


class AddCommentRequest(BaseModel):
    text: str
    parentId: uuid.UUID | None = None

    @field_validator("text")
    @classmethod
    def validateText(cls, v: str) -> str:
        if len(v.strip()) < 5:
            raise ValueError("Comment must be at least 5 characters")
        if len(v.strip()) > 1000:
            raise ValueError("Comment cannot exceed 1000 characters")
        return v.strip()


class CommentResponse(BaseModel):
    id: uuid.UUID
    citizenId: uuid.UUID
    citizenDisplayName: str | None
    issueId: uuid.UUID
    text: str
    createdAt: str
    parentId: uuid.UUID | None = None
    likesCount: int = 0
    hasLiked: bool = False
    stance: str | None = None
    authorRole: str = "citizen"
    isAuthor: bool = False

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    items: list[CommentResponse]
    total: int
    cursor: str | None = None
