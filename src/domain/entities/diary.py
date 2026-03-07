from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Emotion(str, Enum):
    HAPPY = "happy"        # 기쁨, 행복
    SAD = "sad"            # 슬픔
    ANGRY = "angry"        # 화남, 짜증
    ANXIOUS = "anxious"    # 불안, 걱정
    PEACEFUL = "peaceful"  # 평온, 차분
    NORMAL = "normal"      # 평범, 무난


class Diary(BaseModel):
    id: str = Field()
    user_id: str = Field()
    chat_session_id: str = Field()
    title: Optional[str] = Field()
    content: str = Field(min_length=20)
    writed_at: date = Field(default_factory=date.today)
    thumbnail_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    user_wrote_this_diary_directly: bool = Field(default=False)
    emotion: Optional[Emotion] = Field(default=None)
