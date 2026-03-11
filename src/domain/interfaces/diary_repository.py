from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from src.domain.entities.diary import Diary


class DiaryRepository(ABC):
    @abstractmethod
    async def create(self, diary: Diary) -> Diary:
        pass

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Diary]:
        pass

    @abstractmethod
    async def find_by_date(self, date: date, user_id: str) -> Optional[Diary]:
        pass

    @abstractmethod
    async def get_diary_list(
        self, user_id: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        pass

    @abstractmethod
    async def update(self, diary: Diary) -> Diary:
        pass

    @abstractmethod
    async def delete(self, diary: Diary):
        pass

    @abstractmethod
    async def get_next_diary(self, diary: Diary) -> Optional[Diary]:
        pass

    @abstractmethod
    async def get_prev_diary(self, diary: Diary) -> Optional[Diary]:
        pass

    @abstractmethod
    async def get_emotions_timeline(
        self, user_id: str, start_date: Optional[date], end_date: Optional[date]
    ) -> List[Diary]:
        """Get diaries with emotion data for timeline visualization."""
        pass

    @abstractmethod
    async def search(
        self, user_id: str, query: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        pass

    @abstractmethod
    async def get_saved_diaries(
        self, user_id: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        pass
