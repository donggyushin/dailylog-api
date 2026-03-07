import os
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.domain.entities.user import User
from src.domain.interfaces.ai_chat_bot import AIChatBot
from src.domain.interfaces.chat_repository import ChatRepository
from src.domain.interfaces.diary_repository import DiaryRepository
from src.domain.interfaces.email_sender import EmailSender
from src.domain.interfaces.email_verification_code_repository import (
    EmailVerificationCodeRepository,
)
from src.domain.interfaces.emotion_analyzer import EmotionAnalyzer
from src.domain.interfaces.hasher import Hasher
from src.domain.interfaces.image_generator import ImageGenerator
from src.domain.interfaces.image_storage import ImageStorage
from src.domain.interfaces.jwt_provider import JWTProvider
from src.domain.interfaces.payments_repository import PaymentsRepository
from src.domain.interfaces.random_name_generator import RandomNameGenerator
from src.domain.interfaces.refresh_token_repository import RefreshTokenRepository
from src.domain.interfaces.user_repository import UserRepository
from src.domain.interfaces.verification_code_generator import VerificationCodeGenerator
from src.domain.services.auth_service import AuthService
from src.domain.services.change_password_service import ChangePasswordService
from src.domain.services.chat_history_service import ChatHistoryService
from src.domain.services.diary_service import DiaryService
from src.domain.services.email_verification_service import EmailVerificationService
from src.domain.services.user_profile_service import UserProfileService
from src.infrastructure.anthropic_ai_chat_bot import AnthropicAIChatBot
from src.infrastructure.anthropic_emotion_analyzer import AnthropicEmotionAnalyzer
from src.infrastructure.bcrypt_hasher import BcryptHasher
from src.infrastructure.cloudflare_r2_storage import CloudflareR2Storage
from src.infrastructure.dall_e_image_generator import DallEImageGenerator
from src.infrastructure.database import get_database
from src.infrastructure.faker_random_name_generator import FakerRandomNameGenerator
from src.infrastructure.mongo_chat_repository import MongoChatRepository
from src.infrastructure.mongo_diary_repository import MongoDiaryRepository
from src.infrastructure.mongo_email_verification_code_repository import (
    MongoEmailVerificationCodeRepository,
)
from src.infrastructure.mongo_payments_repository import MongoPaymentsRepository
from src.infrastructure.mongo_refresh_token_repository import (
    MongoRefreshTokenRepository,
)
from src.infrastructure.mongo_user_repository import MongoUserRepository
from src.infrastructure.py_jwt_provider import PyJWTProvider
from src.infrastructure.random_number_code_generator import RandomNumberCodeGenerator
from src.infrastructure.resend_email_sender import ResendEmailSender


def get_db() -> AsyncIOMotorDatabase:
    """Get database connection"""
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection not available",
        )
    return db


def get_payments_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> PaymentsRepository:
    return MongoPaymentsRepository(db.client)


def get_diary_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> DiaryRepository:
    return MongoDiaryRepository(db.client)


def get_user_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> UserRepository:
    """Get user repository instance"""
    return MongoUserRepository(db.client)


def get_refresh_token_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> RefreshTokenRepository:
    """Get refresh token repository instance"""
    return MongoRefreshTokenRepository(db.client)


def get_email_verification_code_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> EmailVerificationCodeRepository:
    return MongoEmailVerificationCodeRepository(db.client)


def get_chat_repository(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_db)],
) -> ChatRepository:
    return MongoChatRepository(db.client)


def get_hasher() -> Hasher:
    """Get password hasher instance"""
    return BcryptHasher()


def get_jwt_provider() -> JWTProvider:
    """Get JWT provider instance"""
    jwt_secret = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    return PyJWTProvider(secret_key=jwt_secret)


def get_email_sender() -> EmailSender:
    return ResendEmailSender()


def get_random_name_generator() -> RandomNameGenerator:
    return FakerRandomNameGenerator()


def get_verification_code_generator() -> VerificationCodeGenerator:
    return RandomNumberCodeGenerator()


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    refresh_token_repo: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    hasher: Annotated[Hasher, Depends(get_hasher)],
    jwt_provider: Annotated[JWTProvider, Depends(get_jwt_provider)],
    random_name_generator: Annotated[
        RandomNameGenerator, Depends(get_random_name_generator)
    ],
) -> AuthService:
    """Get auth service instance with all dependencies injected"""
    return AuthService(
        user_repository=user_repo,
        jwt_provider=jwt_provider,
        hasher=hasher,
        refresh_token_repository=refresh_token_repo,
        random_name_generator=random_name_generator,
    )


def get_email_verification_service(
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    verification_code_generator: Annotated[
        VerificationCodeGenerator, Depends(get_verification_code_generator)
    ],
    email_verification_code_repository: Annotated[
        EmailVerificationCodeRepository, Depends(get_email_verification_code_repository)
    ],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> EmailVerificationService:
    return EmailVerificationService(
        email_sender,
        verification_code_generator,
        email_verification_code_repository,
        user_repository,
    )


def get_change_password_service(
    email_verification_code_repository: Annotated[
        EmailVerificationCodeRepository, Depends(get_email_verification_code_repository)
    ],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    verification_code_generator: Annotated[
        VerificationCodeGenerator, Depends(get_verification_code_generator)
    ],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    jwt_provider: Annotated[JWTProvider, Depends(get_jwt_provider)],
    hasher: Annotated[Hasher, Depends(get_hasher)],
):
    service = ChangePasswordService(
        email_verification_code_repository,
        user_repository,
        verification_code_generator,
        email_sender,
        jwt_provider,
        hasher,
    )

    return service


def get_ai_chat_bot() -> AIChatBot:
    return AnthropicAIChatBot()


def get_image_generator() -> ImageGenerator:
    return DallEImageGenerator()


def get_image_storage() -> ImageStorage:
    return CloudflareR2Storage()


def get_emotion_analyzer() -> EmotionAnalyzer:
    return AnthropicEmotionAnalyzer()


def get_chat_history_service(
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
    diary_repository: Annotated[DiaryRepository, Depends(get_diary_repository)],
) -> ChatHistoryService:
    service = ChatHistoryService(chat_repository, diary_repository)
    return service


def get_user_profile_service(
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    image_storage: Annotated[ImageStorage, Depends(get_image_storage)],
) -> UserProfileService:
    service = UserProfileService(user_repository, image_storage)
    return service


def get_diary_service(
    diary_repository: Annotated[DiaryRepository, Depends(get_diary_repository)],
    chat_repository: Annotated[ChatRepository, Depends(get_chat_repository)],
    ai_chat_bot: Annotated[AIChatBot, Depends(get_ai_chat_bot)],
    image_generator: Annotated[ImageGenerator, Depends(get_image_generator)],
    image_storage: Annotated[ImageStorage, Depends(get_image_storage)],
    payments_repository: Annotated[
        PaymentsRepository, Depends(get_payments_repository)
    ],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
    emotion_analyzer: Annotated[EmotionAnalyzer, Depends(get_emotion_analyzer)],
) -> DiaryService:
    return DiaryService(
        diary_repository,
        chat_repository,
        ai_chat_bot,
        image_generator,
        image_storage,
        payments_repository,
        user_repository,
        emotion_analyzer,
    )


# HTTPBearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    jwt_provider: Annotated[JWTProvider, Depends(get_jwt_provider)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """
    Extract and verify JWT token from Authorization header, return current user

    Args:
        credentials: HTTP Bearer token from Authorization header
        jwt_provider: JWT provider for token verification
        user_repository: User repository for fetching user data

    Returns:
        User: Current authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Verify JWT and extract payload
        payload = jwt_provider.verify_token(token)
        user_id: Optional[str] = payload.get("user_id")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id not found in payload",
            )

        # Fetch user from database
        user = await user_repository.find_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return user

    except Exception as e:
        # JWT verification failed or other errors
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
        )
