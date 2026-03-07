from datetime import date
from typing import Optional, List
from src.domain.entities.diary import Diary
from src.domain.interfaces.diary_repository import DiaryRepository


class DiaryStatisticsService:
    """Service for diary statistics and analytics operations."""

    def __init__(self, diary_repository: DiaryRepository):
        self.diary_repository = diary_repository

    async def get_emotions_timeline(
        self, user_id: str, start_date: Optional[date], end_date: Optional[date]
    ) -> tuple[List[Diary], dict]:
        """Get emotion timeline with summary statistics."""

        diaries = await self.diary_repository.get_emotions_timeline(
            user_id, start_date, end_date
        )

        # 요약 통계 계산
        emotion_counts: dict[str, int] = {}
        for diary in diaries:
            emotion_value = diary.emotion.value if diary.emotion else "unknown"
            emotion_counts[emotion_value] = emotion_counts.get(emotion_value, 0) + 1

        # 가장 많은 감정 찾기
        most_common = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else None

        # 실제 날짜 범위
        date_range = {
            "start": diaries[0].writed_at.isoformat() if diaries else None,
            "end": diaries[-1].writed_at.isoformat() if diaries else None
        }

        summary = {
            "total_count": len(diaries),
            "date_range": date_range,
            "emotion_counts": emotion_counts,
            "most_common_emotion": most_common
        }

        return diaries, summary
