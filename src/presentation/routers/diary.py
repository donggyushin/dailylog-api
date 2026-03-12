from datetime import date, timedelta
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.domain.entities.chat import ChatSession
from src.domain.entities.diary import Diary, Emotion
from src.domain.entities.user import User
from src.domain.services.chat_history_service import ChatHistoryService
from src.domain.services.diary_service import DiaryService
from src.domain.services.diary_statistics_service import DiaryStatisticsService
from src.presentation.dependencies import (
    get_chat_history_service,
    get_current_user,
    get_diary_service,
    get_diary_statistics_service,
)

router = APIRouter(prefix="/api/v1", tags=["Diaries"])


# ========================================
# Request/Response Models
# ========================================


class WriteDiaryRequest(BaseModel):
    session_id: str
    message_id: str


class DiaryThumbnailExampleResponse(BaseModel):
    img_url: str


class ChangeDiaryThumbnailRequest(BaseModel):
    img_url: str


class DiaryTagsUpdateRequest(BaseModel):
    tags: List[str]


class GetNextAndPrevDiariesResponse(BaseModel):
    next: Optional[Diary]
    prev: Optional[Diary]


class WriteDiaryDirectRequest(BaseModel):
    title: Optional[str]
    content: str
    chat_session_id: Optional[str] = Field(default=None)


class EmotionTimelinePoint(BaseModel):
    diary_date: date = Field(description="Diary write date")
    emotion: Emotion = Field(description="Detected emotion")
    emotion_score: int = Field(description="Emotion Score from 0 to 10")
    diary_id: str = Field(description="Diary ID for navigation")
    title: Optional[str] = Field(default=None, description="Diary title")


class EmotionSummary(BaseModel):
    total_count: int = Field(description="Total diaries in range")
    date_range: dict = Field(description="Actual date range {start, end}")
    emotion_counts: dict[str, int] = Field(description="Count by emotion type")
    most_common_emotion: Optional[str] = Field(
        default=None, description="Most frequent emotion"
    )


class EmotionTimelineResponse(BaseModel):
    timeline: List[EmotionTimelinePoint]
    summary: EmotionSummary


# ========================================
# Endpoints
# ========================================


@router.get(
    "/diaries",
    response_model=List[Diary],
    status_code=status.HTTP_200_OK,
)
async def get_diary_list(
    current_user: Annotated[User, Depends(get_current_user)],
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    cursor_id: Annotated[
        Optional[str], Query(description="Cursor ID for pagination")
    ] = None,
    size: Annotated[
        int, Query(ge=1, le=100, description="Number of diaries to fetch")
    ] = 30,
):
    diaries = await diary_service.get_diary_list(current_user, cursor_id, size)
    return diaries


@router.get(
    "/diaries/search",
    response_model=List[Diary],
    status_code=status.HTTP_200_OK,
)
async def search_diaries(
    current_user: Annotated[User, Depends(get_current_user)],
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    query: Annotated[str, Query(description="Search keyword for title or content")],
    cursor_id: Annotated[
        Optional[str], Query(description="Cursor ID for pagination")
    ] = None,
    size: Annotated[
        int, Query(ge=1, le=100, description="Number of diaries to fetch")
    ] = 30,
):
    try:
        diaries = await diary_service.search_diaries(
            current_user, query, cursor_id, size
        )
        return diaries
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search diaries: {str(e)}",
        )


@router.get(
    "/diaries/saved",
    response_model=List[Diary],
    status_code=status.HTTP_200_OK,
)
async def get_saved_diaries(
    current_user: Annotated[User, Depends(get_current_user)],
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    cursor_id: Annotated[
        Optional[str], Query(description="Cursor ID for pagination")
    ] = None,
    size: Annotated[
        int, Query(ge=1, le=100, description="Number of diaries to fetch")
    ] = 30,
):
    try:
        diaries = await diary_service.get_saved_diaries(current_user, cursor_id, size)
        return diaries
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search diaries: {str(e)}",
        )


@router.get(
    "/diaries/emotions/timeline",
    response_model=EmotionTimelineResponse,
    status_code=status.HTTP_200_OK,
)
async def get_emotion_timeline(
    current_user: Annotated[User, Depends(get_current_user)],
    statistics_service: Annotated[
        DiaryStatisticsService, Depends(get_diary_statistics_service)
    ],
    start_date: Annotated[
        Optional[date], Query(description="Filter start date (inclusive)")
    ] = None,
    end_date: Annotated[
        Optional[date], Query(description="Filter end date (inclusive)")
    ] = None,
):
    """
    Get emotion timeline data for visualizing mood changes over time.

    Returns timeline of emotions from user's diaries with summary statistics.
    Only includes diaries with analyzed emotions.
    """
    # 날짜 범위 기본값: 최근 90일
    if start_date is None and end_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

    # 날짜 범위 검증
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date",
        )

    try:
        diaries, summary = await statistics_service.get_emotions_timeline(
            current_user.id, start_date, end_date
        )

        # Response 형식으로 변환 (defensive check for None emotions)
        timeline = []
        for diary in diaries:
            if diary.emotion is not None:  # Type narrowing for mypy
                timeline.append(
                    EmotionTimelinePoint(
                        diary_date=diary.writed_at,
                        emotion=diary.emotion,
                        emotion_score=diary.emotion.score(),
                        diary_id=diary.id,
                        title=diary.title,
                    )
                )

        return EmotionTimelineResponse(
            timeline=timeline, summary=EmotionSummary(**summary)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch emotion timeline: {str(e)}",
        )


@router.get("/diary", response_model=Diary)
async def find_diary_by_date(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    writed_at: Annotated[date, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
):
    try:
        diary = await diary_service.get_diary_by_date(writed_at, current_user)
        return diary
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/diary/{diary_id}",
    response_model=Diary,
    status_code=status.HTTP_200_OK,
)
async def find_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    try:
        return await diary_service.get_diary_by_id(diary_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get(
    "/diary/{diary_id}/chat_session",
    response_model=ChatSession,
)
async def get_chat_session_from_diary_id(
    chat_history_service: Annotated[
        ChatHistoryService, Depends(get_chat_history_service)
    ],
    diary_id: str,
):
    try:
        chat_session = await chat_history_service.find_session(diary_id)
        return chat_session
    except Exception as e:
        raise e


@router.get(
    "/diary/thumbnail/{diary_id}",
    response_model=DiaryThumbnailExampleResponse,
    status_code=status.HTTP_200_OK,
)
async def generate_diary_thumbnail_example_image(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    img_url = await diary_service.generate_example_thumbnail(diary_id)
    return DiaryThumbnailExampleResponse(img_url=img_url)


@router.get(
    "/diary/{diary_id}/next_prev",
)
async def get_next_prev_diaries(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    diary_id: str,
) -> GetNextAndPrevDiariesResponse:
    try:
        result = await diary_service.find_next_prev_diary(diary_id)
        response = GetNextAndPrevDiariesResponse(next=result[0], prev=result[1])
        return response
    except Exception as e:
        raise e


@router.post(
    "/diary",
    response_model=Diary,
    status_code=status.HTTP_200_OK,
)
async def write_diary(
    request: WriteDiaryRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
):
    return await diary_service.write_diary(request.session_id, request.message_id)


@router.post("/diary/direct")
async def write_diary_directly(
    current_user: Annotated[User, Depends(get_current_user)],
    request: WriteDiaryDirectRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
) -> Diary:
    try:
        diary = await diary_service.write_diary_direct(
            current_user, request.title, request.content, request.chat_session_id
        )
        return diary
    except Exception as e:
        raise e


@router.post("/diary/{diary_id}/saved", response_model=Diary)
async def save_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    try:
        diary = await diary_service.update_saved(diary_id, True)
        return diary
    except Exception as e:
        print(f"Error updating thumbnail: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/diary/{diary_id}")
async def update_diary(
    request: WriteDiaryDirectRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    diary_id: str,
) -> Diary:
    try:
        diary = await diary_service.update_diary(
            diary_id, request.title, request.content
        )
        return diary
    except Exception as e:
        print(f"Error updating thumbnail: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/diary/{diary_id}/tags", response_model=Diary)
async def update_diary_tags(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    request: DiaryTagsUpdateRequest,
    diary_id: str,
):
    try:
        diary = await diary_service.update_tags(diary_id, request.tags)
        return diary
    except Exception as e:
        print(f"Error updating thumbnail: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/diary/{diary_id}/thumbnail", response_model=Diary)
async def change_diary_thumbnail(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    request: ChangeDiaryThumbnailRequest,
    diary_id: str,
):
    try:
        diary = await diary_service.update_thumbnail(diary_id, request.img_url)
        return diary
    except Exception as e:
        print(f"Error updating thumbnail: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/diary/{diary_id}/emotion")
async def update_diary_emotion(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
) -> Diary:
    try:
        diary = await diary_service.update_diary_emotion(diary_id)
        return diary
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/diary/{diary_id}")
async def delete_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    await diary_service.delete(diary_id)


@router.delete("/diary/{diary_id}/saved", response_model=Diary)
async def unsave_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    try:
        diary = await diary_service.update_saved(diary_id, False)
        return diary
    except Exception as e:
        print(f"Error updating thumbnail: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
