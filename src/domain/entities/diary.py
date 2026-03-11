from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Emotion(str, Enum):
    HAPPY = "happy"  # 기쁨, 행복
    SAD = "sad"  # 슬픔
    ANGRY = "angry"  # 화남, 짜증
    ANXIOUS = "anxious"  # 불안, 걱정
    PEACEFUL = "peaceful"  # 평온, 차분
    NORMAL = "normal"  # 평범, 무난

    def score(self) -> int:
        if self is Emotion.HAPPY:
            return 10
        elif self is Emotion.PEACEFUL:
            return 8
        elif self is Emotion.NORMAL:
            return 6
        elif self is Emotion.SAD:
            return 4
        elif self is Emotion.ANXIOUS:
            return 2
        else:
            return 0


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
    saved: bool = Field(default=False)
    tags: List[str] = Field(default=[])
