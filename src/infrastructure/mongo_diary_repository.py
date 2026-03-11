from datetime import date
from typing import List, Optional

from bson import ObjectId
from src.domain.entities.diary import Diary
from src.domain.exceptions import NotFoundError
from src.domain.interfaces.diary_repository import DiaryRepository
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class MongoDiaryRepository(DiaryRepository):
    def __init__(self, db_client: AsyncIOMotorClient, db_name: str = "dailylog"):
        self.collection: AsyncIOMotorCollection = db_client[db_name]["diaries"]

    async def delete(self, diary: Diary):
        await self.collection.delete_one({"_id": ObjectId(diary.id)})

    async def update(self, diary: Diary) -> Diary:
        diary_dict = diary.model_dump(mode="json", exclude={"id"})

        await self.collection.update_one(
            {"_id": ObjectId(diary.id)}, {"$set": diary_dict}
        )

        return diary

    async def create(self, diary: Diary) -> Diary:
        dict = diary.model_dump(mode="json", exclude={"id"})
        result = await self.collection.insert_one(dict)
        dict["id"] = str(result.inserted_id)
        return Diary(**dict)

    async def find_by_date(self, date: date, user_id: str) -> Optional[Diary]:
        result = await self.collection.find_one(
            {"writed_at": date.isoformat(), "user_id": user_id}
        )

        if result is None:
            raise NotFoundError()

        result["id"] = str(result.pop("_id"))
        return Diary(**result)

    async def find_by_id(self, id: str) -> Optional[Diary]:
        result = await self.collection.find_one({"_id": ObjectId(id)})

        if result is None:
            raise NotFoundError()

        result["id"] = str(result.pop("_id"))
        return Diary(**result)

    async def get_diary_list(
        self, user_id: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        # 해당 사용자의 일기만 조회
        query: dict = {"user_id": user_id}

        # cursor_id가 있으면 해당 일기의 날짜보다 오래된 일기들만 조회
        if cursor_id:
            cursor_diary = await self.collection.find_one({"_id": ObjectId(cursor_id)})
            if cursor_diary:
                query["writed_at"] = {"$lt": cursor_diary["writed_at"]}

        # 날짜 기준 내림차순 정렬 (최신 일기가 먼저)
        cursor = self.collection.find(query).sort("writed_at", -1).limit(size)
        results = await cursor.to_list(length=size)

        # MongoDB 문서를 Diary 엔티티로 변환
        diaries = []
        for result in results:
            result["id"] = str(result.pop("_id"))
            diaries.append(Diary(**result))

        return diaries

    async def get_next_diary(self, diary: Diary) -> Optional[Diary]:
        """현재 일기보다 더 최신 날짜의 일기 반환 (같은 유저)"""
        result = await self.collection.find_one(
            {
                "user_id": diary.user_id,
                "writed_at": {"$gt": diary.writed_at.isoformat()},
            },
            sort=[("writed_at", 1)],  # 오름차순 정렬 (가장 가까운 다음 일기)
        )

        if result is None:
            return None

        result["id"] = str(result.pop("_id"))
        return Diary(**result)

    async def get_prev_diary(self, diary: Diary) -> Optional[Diary]:
        """현재 일기보다 이전 날짜의 일기 반환 (같은 유저)"""
        result = await self.collection.find_one(
            {
                "user_id": diary.user_id,
                "writed_at": {"$lt": diary.writed_at.isoformat()},
            },
            sort=[("writed_at", -1)],  # 내림차순 정렬 (가장 가까운 이전 일기)
        )

        if result is None:
            return None

        result["id"] = str(result.pop("_id"))
        return Diary(**result)

    async def get_emotions_timeline(
        self, user_id: str, start_date: Optional[date], end_date: Optional[date]
    ) -> List[Diary]:
        """Get diaries with emotion data for timeline visualization."""
        # Query 구성
        query = {
            "user_id": user_id,
            "emotion": {"$ne": None},  # null 감정 제외
        }

        # 날짜 범위 필터
        if start_date or end_date:
            date_filter = {}
            if start_date:
                date_filter["$gte"] = start_date.isoformat()
            if end_date:
                date_filter["$lte"] = end_date.isoformat()
            query["writed_at"] = date_filter

        # 성능 최적화: 필요한 필드만 조회

        # 시간순 정렬 (오래된 것부터)
        cursor = self.collection.find(query).sort("writed_at", 1)
        results = await cursor.to_list(length=None)

        # Diary 엔티티로 변환
        diaries = []
        for result in results:
            result["id"] = str(result.pop("_id"))
            diaries.append(Diary(**result))

        return diaries

    async def search(
        self, user_id: str, query: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        """Search diaries by title, content, or tags using regex pattern matching."""
        # 기본 쿼리: 해당 사용자의 일기만 검색
        search_query: dict = {
            "user_id": user_id,
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},  # 대소문자 무시
                {"content": {"$regex": query, "$options": "i"}},
                {"tags": {"$regex": query, "$options": "i"}},  # tags 배열 내 부분 일치
            ],
        }

        # cursor_id가 있으면 해당 일기의 날짜보다 오래된 일기들만 조회
        if cursor_id:
            cursor_diary = await self.collection.find_one({"_id": ObjectId(cursor_id)})
            if cursor_diary:
                search_query["writed_at"] = {"$lt": cursor_diary["writed_at"]}

        # 날짜 기준 내림차순 정렬 (최신 일기가 먼저)
        cursor = self.collection.find(search_query).sort("writed_at", -1).limit(size)
        results = await cursor.to_list(length=size)

        # MongoDB 문서를 Diary 엔티티로 변환
        diaries = []
        for result in results:
            result["id"] = str(result.pop("_id"))
            diaries.append(Diary(**result))

        return diaries

    async def get_saved_diaries(
        self, user_id: str, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        """저장된 일기 목록 조회 (saved=True인 일기들)"""
        # 기본 쿼리: 해당 사용자의 저장된 일기만 조회
        query: dict = {
            "user_id": user_id,
            "saved": True
        }

        # cursor_id가 있으면 해당 일기의 날짜보다 오래된 일기들만 조회
        if cursor_id:
            cursor_diary = await self.collection.find_one({"_id": ObjectId(cursor_id)})
            if cursor_diary:
                query["writed_at"] = {"$lt": cursor_diary["writed_at"]}

        # 날짜 기준 내림차순 정렬 (최신 일기가 먼저)
        cursor = self.collection.find(query).sort("writed_at", -1).limit(size)
        results = await cursor.to_list(length=size)

        # MongoDB 문서를 Diary 엔티티로 변환
        diaries = []
        for result in results:
            result["id"] = str(result.pop("_id"))
            diaries.append(Diary(**result))

        return diaries
