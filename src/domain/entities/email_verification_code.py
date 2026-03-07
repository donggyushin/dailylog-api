from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel, Field


class EmailVerificationCode(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: str = Field()
    email: str = Field()
    code: str = Field()
    expired_at: datetime
