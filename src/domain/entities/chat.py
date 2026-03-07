from datetime import datetime
from enum import Enum
from typing import List

from bson import ObjectId
from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    system = "SYSTEM"
    assistant = "ASSISTANT"
    user = "USER"


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    user_id: str = Field()
    role: MessageRole = Field()
    content: str = Field()
    created_at: datetime = Field(default_factory=datetime.now)


class ChatSession(BaseModel):
    id: str = Field()
    user_id: str = Field()
    active: bool = Field(default=True)
    messages: List[ChatMessage] = Field()
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
