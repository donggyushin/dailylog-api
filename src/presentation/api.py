from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Annotated, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.domain.entities.chat import ChatMessage, ChatSession
from src.domain.entities.diary import Diary, Emotion
from src.domain.entities.user import Gender, User
from src.domain.exceptions import (
    EmailAlreadyExistsError,
    ExpiredError,
    NotCorrectError,
    NotFoundError,
    PasswordLengthNotEnoughError,
    PasswordNotCorrectError,
    UserNotFoundError,
)
from src.domain.services.auth_service import AuthService
from src.domain.services.change_password_service import ChangePasswordService
from src.domain.services.chat_history_service import ChatHistoryService
from src.domain.services.diary_service import DiaryService
from src.domain.services.diary_statistics_service import DiaryStatisticsService
from src.domain.services.email_verification_service import EmailVerificationService
from src.domain.services.user_profile_service import UserProfileService
from src.infrastructure.database import connect_to_mongo, close_mongo_connection
from src.presentation.dependencies import (
    get_auth_service,
    get_change_password_service,
    get_chat_history_service,
    get_current_user,
    get_diary_service,
    get_diary_statistics_service,
    get_email_verification_service,
    get_user_profile_service,
)


# ========================================
# Request/Response Models
# ========================================


# Authentication Models
class RegisterRequest(BaseModel):
    email: str = Field(min_length=10, description="User email")
    password: str = Field(min_length=10, description="User password")


class AuthTokenResponse(BaseModel):
    accessToken: str
    refreshToken: str


class RefreshTokenRequest(BaseModel):
    refreshToken: str


# User Profile Models
class UpdateUserRequest(BaseModel):
    username: str
    birth: Optional[date]
    gender: Optional[Gender]


# Email Verification Models
class VerifyEmailRequest(BaseModel):
    code: str


# Password Change Models
class EmailVerificationCodeForChangingPasswordRequest(BaseModel):
    email: str


class EmailVerifyForChangingPasswordRequest(BaseModel):
    email: str
    code: str


class EmailVerifyForChangingPasswordResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    token: str
    new_password: str


# Chat Models
class ChatSendMessageRequest(BaseModel):
    session_id: str
    message: ChatMessage


# Diary Models
class WriteDiaryRequest(BaseModel):
    session_id: str
    message_id: str


class DiaryThumbnailExampleResponse(BaseModel):
    img_url: str


class ChangeDiaryThumbnailRequest(BaseModel):
    img_url: str


class GetNextAndPrevDiariesResponse(BaseModel):
    next: Optional[Diary]
    prev: Optional[Diary]


class WriteDiaryDirectRequest(BaseModel):
    title: Optional[str]
    content: str


# Emotion Timeline Models
class EmotionTimelinePoint(BaseModel):
    diary_date: date = Field(description="Diary write date")
    emotion: Emotion = Field(description="Detected emotion")
    diary_id: str = Field(description="Diary ID for navigation")
    title: Optional[str] = Field(default=None, description="Diary title")


class EmotionSummary(BaseModel):
    total_count: int = Field(description="Total diaries in range")
    date_range: dict = Field(description="Actual date range {start, end}")
    emotion_counts: dict[str, int] = Field(description="Count by emotion type")
    most_common_emotion: Optional[str] = Field(default=None, description="Most frequent emotion")


class EmotionTimelineResponse(BaseModel):
    timeline: List[EmotionTimelinePoint]
    summary: EmotionSummary


# ========================================
# Application Setup
# ========================================


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(lifespan=lifespan)

# CORS 설정: 개발 환경에서 모든 origin 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용하도록 변경 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========================================
# Health Check
# ========================================


@app.get("/api/v1", tags=["Health"])
async def hello():
    return {"message": "hello world"}


# ========================================
# Authentication
# ========================================


@app.post(
    "/api/v1/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Register a new user and return JWT tokens"""
    try:
        tokens = await auth_service.register(
            email=request.email, password=request.password
        )
        return AuthTokenResponse(**tokens)
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PasswordLengthNotEnoughError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/v1/login", response_model=AuthTokenResponse, tags=["Authentication"])
async def login(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        token = await auth_service.login(request.email, request.password)
        return AuthTokenResponse(**token)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 정보입니다."
        )
    except PasswordNotCorrectError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="유효하지 않은 정보입니다."
        )


@app.post(
    "/api/v1/refresh_token",
    status_code=status.HTTP_200_OK,
    response_model=AuthTokenResponse,
    tags=["Authentication"],
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    result = await auth_service.refresh_token(request.refreshToken)
    return AuthTokenResponse(**result)


# ========================================
# User Profile
# ========================================


@app.get("/api/v1/me", tags=["User Profile"])
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@app.put("/api/v1/me", tags=["User Profile"])
async def update_me(
    current_user: Annotated[User, Depends(get_current_user)],
    user_profile_service: Annotated[
        UserProfileService, Depends(get_user_profile_service)
    ],
    request: UpdateUserRequest,
) -> User:
    try:
        updated_user = current_user
        updated_user.username = request.username
        updated_user.birth = request.birth
        updated_user.gender = request.gender

        response = await user_profile_service.update_user_profile(
            current_user, updated_user
        )
        return response
    except Exception as e:
        raise e


@app.put("/api/v1/me/profile-image", tags=["User Profile"])
async def update_profile_image(
    current_user: Annotated[User, Depends(get_current_user)],
    user_profile_service: Annotated[
        UserProfileService, Depends(get_user_profile_service)
    ],
    file: UploadFile = File(...),
) -> User:
    """
    Update user profile image.

    Uploads new profile image to R2 storage and deletes old image if exists.
    """
    try:
        # Read image data from uploaded file
        image_data = await file.read()

        # Update profile image using service
        updated_user = await user_profile_service.update_profile_img(
            current_user, image_data
        )
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile image: {str(e)}",
        )


@app.delete("/api/v1/me/profile-image", tags=["User Profile"])
async def delete_profile_image(
    current_user: Annotated[User, Depends(get_current_user)],
    user_profile_service: Annotated[
        UserProfileService, Depends(get_user_profile_service)
    ],
) -> User:
    """
    Delete user profile image.

    Removes profile image from R2 storage and sets profile_image_url to None.
    """
    try:
        # Pass None to delete image without uploading new one
        updated_user = await user_profile_service.update_profile_img(current_user, None)
        return updated_user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile image: {str(e)}",
        )


# ========================================
# Email Verification
# ========================================


@app.post(
    "/api/v1/email_verification_code",
    status_code=status.HTTP_200_OK,
    tags=["Email Verification"],
)
async def send_email_verification_code(
    current_user: Annotated[User, Depends(get_current_user)],
    email_verification_service: Annotated[
        EmailVerificationService, Depends(get_email_verification_service)
    ],
):
    """Send email verification code to current user's email"""
    await email_verification_service.send_verification_code(current_user)


@app.post("/api/v1/verify_email", tags=["Email Verification"])
async def verify_email(
    request: VerifyEmailRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    email_verification_service: Annotated[
        EmailVerificationService, Depends(get_email_verification_service)
    ],
):
    try:
        await email_verification_service.verifiy(current_user, request.code)
    except NotCorrectError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증번호 입니다.",
        )
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증번호 입니다.",
        )
    except ExpiredError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효 기간이 만료 되었습니다.",
        )


# ========================================
# Password Change
# ========================================


@app.post("/api/v1/change_password/email_verification_code", tags=["Password Change"])
async def request_email_verification_code_for_changing_password(
    change_password_service: Annotated[
        ChangePasswordService, Depends(get_change_password_service)
    ],
    request: EmailVerificationCodeForChangingPasswordRequest,
):
    try:
        await change_password_service.request_email_verification_code(request.email)
    except Exception as e:
        raise e


@app.post("/api/v1/change_password/verify", tags=["Password Change"])
async def verify_email_verification_code_for_changing_password(
    request: EmailVerifyForChangingPasswordRequest,
    change_password_service: Annotated[
        ChangePasswordService, Depends(get_change_password_service)
    ],
) -> EmailVerifyForChangingPasswordResponse:
    try:
        token = await change_password_service.verify(request.email, request.code)
        response = EmailVerifyForChangingPasswordResponse(token=token)
        return response

    except Exception as e:
        raise e


@app.patch("/api/v1/change_password", tags=["Password Change"])
async def change_password(
    change_password_service: Annotated[
        ChangePasswordService, Depends(get_change_password_service)
    ],
    request: ChangePasswordRequest,
):
    try:
        await change_password_service.change_password(
            request.token, request.new_password
        )
    except Exception as e:
        raise e


# ========================================
# Chat Sessions
# ========================================


@app.get(
    "/api/v1/chat-current-session",
    response_model=ChatSession,
    status_code=status.HTTP_200_OK,
    tags=["Chat Sessions"],
)
async def get_current_chat_session(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    current_session = await diary_service.get_chat_session(current_user)
    return current_session


@app.delete("/api/v1/chat-current-session", tags=["Chat Sessions"])
async def end_current_chat_session(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await diary_service.end_current_session(current_user)


@app.post(
    "/api/v1/chat/message",
    status_code=status.HTTP_200_OK,
    response_model=ChatMessage,
    tags=["Chat Sessions"],
)
async def send_message(
    request: ChatSendMessageRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
):
    reply = await diary_service.send_chat_message(request.message, request.session_id)
    return reply


# ========================================
# Diaries
# ========================================


@app.get(
    "/api/v1/diaries",
    response_model=List[Diary],
    status_code=status.HTTP_200_OK,
    tags=["Diaries"],
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


@app.get(
    "/api/v1/diaries/emotions/timeline",
    response_model=EmotionTimelineResponse,
    status_code=status.HTTP_200_OK,
    tags=["Diaries"],
)
async def get_emotion_timeline(
    current_user: Annotated[User, Depends(get_current_user)],
    statistics_service: Annotated[DiaryStatisticsService, Depends(get_diary_statistics_service)],
    start_date: Annotated[Optional[date], Query(description="Filter start date (inclusive)")] = None,
    end_date: Annotated[Optional[date], Query(description="Filter end date (inclusive)")] = None,
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
            detail="start_date must be before or equal to end_date"
        )

    try:
        diaries, summary = await statistics_service.get_emotions_timeline(
            current_user.id, start_date, end_date
        )

        # Response 형식으로 변환 (defensive check for None emotions)
        timeline = []
        for diary in diaries:
            if diary.emotion is not None:  # Type narrowing for mypy
                timeline.append(EmotionTimelinePoint(
                    diary_date=diary.writed_at,
                    emotion=diary.emotion,
                    diary_id=diary.id,
                    title=diary.title
                ))

        return EmotionTimelineResponse(
            timeline=timeline,
            summary=EmotionSummary(**summary)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch emotion timeline: {str(e)}"
        )


@app.get("/api/v1/diary", response_model=Diary, tags=["Diaries"])
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


@app.get(
    "/api/v1/diary/{diary_id}",
    response_model=Diary,
    status_code=status.HTTP_200_OK,
    tags=["Diaries"],
)
async def find_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    try:
        return await diary_service.get_diary_by_id(diary_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@app.get(
    "/api/v1/diary/{diary_id}/chat_session",
    response_model=ChatSession,
    tags=["Diaries"],
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


@app.get(
    "/api/v1/diary/thumbnail/{diary_id}",
    response_model=DiaryThumbnailExampleResponse,
    status_code=status.HTTP_200_OK,
    tags=["Diaries"],
)
async def generate_diary_thumbnail_example_image(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    img_url = await diary_service.generate_example_thumbnail(diary_id)
    return DiaryThumbnailExampleResponse(img_url=img_url)


@app.get(
    "/api/v1/diary/{diary_id}/next_prev",
    tags=["Diaries"],
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


@app.post(
    "/api/v1/diary",
    response_model=Diary,
    status_code=status.HTTP_200_OK,
    tags=["Diaries"],
)
async def write_diary(
    request: WriteDiaryRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
):
    return await diary_service.write_diary(request.session_id, request.message_id)


@app.post("/api/v1/diary/direct", tags=["Diaries"])
async def write_diary_directly(
    current_user: Annotated[User, Depends(get_current_user)],
    request: WriteDiaryDirectRequest,
    diary_service: Annotated[DiaryService, Depends(get_diary_service)],
) -> Diary:
    try:
        diary = await diary_service.write_diary_direct(
            current_user, request.title, request.content
        )
        return diary
    except Exception as e:
        raise e


@app.put("/api/v1/diary/{diary_id}", tags=["Diaries"])
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
        raise e


@app.patch("/api/v1/diary/{diary_id}/thumbnail", response_model=Diary, tags=["Diaries"])
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


@app.patch("/api/v1/diary/{diary_id}/emotion", tags=["Diaries"])
async def update_diary_emotion(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
) -> Diary:
    try:
        diary = await diary_service.update_diary_emotion(diary_id)
        return diary
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.delete("/api/v1/diary/{diary_id}", tags=["Diaries"])
async def delete_diary(
    diary_service: Annotated[DiaryService, Depends(get_diary_service)], diary_id: str
):
    await diary_service.delete(diary_id)
