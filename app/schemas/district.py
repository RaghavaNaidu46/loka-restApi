import uuid
from pydantic import BaseModel


class DistrictResponse(BaseModel):
    id: uuid.UUID
    name: str
    state: str
    country: str

    model_config = {"from_attributes": True}
