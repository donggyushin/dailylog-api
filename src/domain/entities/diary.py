from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class Diary(BaseModel):
    id: str = Field(default="")
    user_id: str = Field()
    chat_session_id: str = Field()
    title: Optional[str] = Field()
    content: str = Field(min_length=20)
    writed_at: date = Field(default_factory=date.today)
    thumbnail_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    user_wrote_this_diary_directly: bool = Field(default=False)
