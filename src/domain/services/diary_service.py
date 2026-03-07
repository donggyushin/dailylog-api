import re
import uuid
from datetime import date, datetime
from typing import List, Optional

import httpx
from bson import ObjectId
from src.domain.entities.chat import ChatMessage, ChatSession, MessageRole
from src.domain.entities.diary import Diary
from src.domain.entities.user import User
from src.domain.exceptions import NotFoundError
from src.domain.interfaces.ai_chat_bot import AIChatBot
from src.domain.interfaces.chat_repository import ChatRepository
from src.domain.interfaces.diary_repository import DiaryRepository
from src.domain.interfaces.image_generator import ImageGenerator
from src.domain.interfaces.image_storage import ImageStorage
from src.domain.interfaces.payments_repository import PaymentsRepository
from src.domain.interfaces.user_repository import UserRepository


class DiaryService:
    def __init__(
        self,
        diary_repository: DiaryRepository,
        chat_repository: ChatRepository,
        ai_chat_bot: AIChatBot,
        image_generator: ImageGenerator,
        image_storage: ImageStorage,
        payments_repository: PaymentsRepository,
        user_repository: UserRepository,
    ):
        self.diary_repository = diary_repository
        self.chat_repository = chat_repository
        self.ai_chat_bot = ai_chat_bot
        self.image_generator = image_generator
        self.image_storage = image_storage
        self.payments_repository = payments_repository
        self.user_repository = user_repository

    async def write_diary_direct(
        self, current_user: User, title: Optional[str], content: str
    ) -> Diary:
        diary = Diary(
            user_id=current_user.id,
            chat_session_id="",
            title=title,
            content=content,
            user_wrote_this_diary_directly=True,
        )

        diary = await self.diary_repository.create(diary)

        return diary

    async def update_diary(
        self, diary_id: str, title: Optional[str], content: str
    ) -> Diary:
        diary = await self.diary_repository.find_by_id(diary_id)
        if diary is None:
            raise NotFoundError()
        diary.title = title
        diary.content = content
        diary.updated_at = datetime.now()

        diary = await self.diary_repository.update(diary)

        return diary

    async def find_next_prev_diary(
        self, diary_id: str
    ) -> tuple[Optional[Diary], Optional[Diary]]:
        diary = await self.diary_repository.find_by_id(diary_id)
        if diary is None:
            raise NotFoundError()
        next = await self.diary_repository.get_next_diary(diary)
        prev = await self.diary_repository.get_prev_diary(diary)

        return (next, prev)

    async def delete(self, diary_id: str):
        found_diary = await self.diary_repository.find_by_id(diary_id)
        if found_diary is None:
            raise NotFoundError()

        await self.diary_repository.delete(found_diary)

    async def update_thumbnail(self, diary_id: str, thumbnail_url: str) -> Diary:
        found_diary = await self.diary_repository.find_by_id(diary_id)

        if found_diary is None:
            raise NotFoundError()

        # Download image from the provided URL (disable SSL verification for Docker)
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(thumbnail_url)
            response.raise_for_status()
            image_data = response.content

        # Generate unique filename
        file_name = f"diary-thumbnails/{diary_id}-{uuid.uuid4()}.png"

        # Upload to R2 and get permanent URL
        permanent_url = await self.image_storage.upload(image_data, file_name)

        # Update diary with permanent URL
        found_diary.thumbnail_url = permanent_url

        await self.diary_repository.update(found_diary)

        return found_diary

    async def generate_example_thumbnail(self, diary_id: str) -> str:
        diary = await self.diary_repository.find_by_id(diary_id)

        if diary is None:
            raise NotFoundError()

        diary_content = diary.content

        img_url = await self.image_generator.generate(
            prompt=f"""Create a soft, dreamy anime-style background illustration in the style of Studio Ghibli and Makoto Shinkai, inspired by this diary entry.

Art Style:
- Soft, fluffy clouds with gentle gradients (Ghibli-style sky)
- Warm, glowing light particles and lens flares (Shinkai-style atmosphere)
- Watercolor-like soft edges and gentle color transitions
- Cozy, whimsical, and emotionally warm tone
- Pastel and warm color palette with soft shadows

Visual Mood:
- Comforting and nostalgic atmosphere
- Gentle, diffused lighting that creates a warm glow
- Peaceful, quiet moment captured in time
- Emotionally inviting scene that feels like a safe, cozy space

Key Elements to Include:
- Fluffy, cotton-like clouds with soft pink/orange/purple tints
- Gentle sunlight rays streaming through windows or trees
- Small, cute details: potted plants, books, cushions, small animals (cats, birds)
- Natural elements: grass swaying gently, leaves floating, flower petals
- Warm indoor spaces: wooden floors, soft curtains, warm light from lamps
- Windows showing beautiful skies (sunrise, sunset, or blue sky with puffy clouds)

Color Palette:
- Warm pastels: soft pink, peach, cream, lavender, mint, sky blue
- Golden hour lighting: warm orange and yellow tones
- Avoid harsh contrasts - everything should feel soft and blended
- Colors should evoke comfort, warmth, and emotional safety

Lighting & Atmosphere:
- Soft bokeh effects and light particles floating in the air
- Gentle lens flares and light bloom
- Diffused shadows that feel soft, not harsh
- Atmospheric haze that adds depth and dreaminess
- Light should feel like it's hugging the scene

Composition:
- Cozy, intimate framing - as if we're peeking into a peaceful moment
- Balance between interior comfort and outdoor beauty
- Include small, endearing details that tell a gentle story
- Everything should feel inviting and emotionally warm

Create a scene that feels like a warm hug, where the viewer can feel comforted and emotionally connected to the moment. The image should be cute, fluffy, nostalgic, and deeply emotional.

Diary content:
{diary_content}"""
        )

        return img_url

    async def get_diary_list(
        self, user: User, cursor_id: Optional[str], size: int
    ) -> List[Diary]:
        return await self.diary_repository.get_diary_list(user.id, cursor_id, size)

    async def get_chat_session(self, user: User) -> ChatSession:
        active_session = await self.chat_repository.find_active_session(user.id)

        if active_session:
            return active_session

        previous_user_wrote_diaries = await self.diary_repository.get_diary_list(
            user.id, None, 10
        )

        # 시스템 프롬프트 추가
        system_prompt = ChatMessage(
            id=str(ObjectId()),
            user_id=user.id,
            role=MessageRole.system,
            content=f"""
            당신은 유저와 대화를 나누고, 그 대화를 바탕으로 유저 본인의 목소리로 일기를 작성하는 에이전트입니다.

            [참고 정보]
            유저 프로필: {user}
            최근 작성한 일기들: {previous_user_wrote_diaries}

            [중요: 일기 작성 원칙]

            1. 시점과 목소리
            - 반드시 1인칭 시점으로 작성하세요. ("나는", "내가", "나의")
            - 유저 본인이 직접 쓴 것처럼, 유저의 목소리가 되어야 합니다.
            - 누군가에게 말하는 형식이 아니라, 일기장에 혼잣말을 기록하는 독백 형식입니다.

            2. 문학적 표현
            - 평범한 일상에서 시적인 순간을 포착하세요.
            - 구체적인 감각 묘사를 활용하세요. (빛, 소리, 냄새, 촉감, 온도)
            - 직접적인 감정 표현보다는 은유와 비유로 간접적으로 드러내세요.
            - 예: "슬프다" 대신 → "마음 한켠에 잔물결이 일었다"

            3. 문장의 리듬
            - 긴 문장과 짧은 문장을 적절히 섞어 리듬감을 만드세요.
            - 때로는 문장을 끊어 여운을 남기세요.
            - 운문처럼 흐르되, 과도하게 시적이어서 어색해지지 않도록 주의하세요.

            4. 이영도 작가의 작법 정신
            - "소설의 설정은 나무의 뿌리와 같다. 넓고 튼튼해야 하지만 직접 드러내면 말라죽는다."
              → 감정과 의미를 직접 설명하지 말고, 장면과 묘사로 암시하세요.
            - "길은 방랑자가 흘린 눈물을 기억할 수 있지만, 방랑자를 따라갈 수는 없다."
              → 일상의 사물과 공간에도 감정과 기억이 스며들어 있음을 표현하세요.
            - 평범한 순간에 철학적 깊이를 담으세요. 하지만 설교조가 되지 않도록 주의하세요.

            5. 일기의 톤
            - 내면의 독백이므로, 솔직하고 꾸밈없는 톤을 유지하세요.
            - 과장되거나 연극적이지 않게, 담담하면서도 서정적으로 작성하세요.
            - 길이는 적당히 조절하세요. (300-600자 정도)

            [대화 진행 방식]
            유저가 답변하면, 자연스러운 대화를 통해 하루에 대한 충분한 정보를 이끌어내세요.
            - 단순한 사실뿐 아니라, 그때의 감정, 분위기, 감각적 디테일을 파악하세요.
            - 충분한 정보를 얻었다면 "오늘 하루 있었던 일로 일기를 작성해드릴까요?" 라고 물으세요.
            - 유저가 긍정하면, 위의 원칙을 따라 일기를 작성하세요.

            [일기 출력 형식]
            [TITLE_START]
            간결하고 시적인 제목 (5-10자)
            [TITLE_END]

            [CONTENT_START]
            유저 본인의 목소리로 작성된 1인칭 일기
            [CONTENT_END]
            """,
        )

        first_message = ChatMessage(
            id=str(ObjectId()),
            user_id=user.id,
            role=MessageRole.assistant,
            content="안녕하세요, 오늘 어떤 하루를 보냈는지 저에게 들려주시겠어요?",
        )

        new_session = ChatSession(
            id="", user_id=user.id, messages=[system_prompt, first_message]
        )

        new_session = await self.chat_repository.create_session(new_session)
        return new_session

    async def end_current_session(self, user: User):
        active_session = await self.chat_repository.find_active_session(user.id)
        if active_session:
            await self.end_chat_session(active_session.id)

    async def end_chat_session(self, session_id: str):
        session = await self.chat_repository.find_session(session_id)
        await self.chat_repository.end_session(session)

    async def send_chat_message(
        self,
        new_message: ChatMessage,
        session_id: str,
    ) -> ChatMessage:
        session = await self.chat_repository.find_session(session_id)
        session.messages.append(new_message)

        await self.chat_repository.add_message(session, new_message)
        reply = await self.ai_chat_bot.send(session)
        reply = await self.chat_repository.add_message(session, reply)
        return reply

    async def write_diary(self, session_id: str, message_id: str) -> Diary:
        target_message = await self.chat_repository.find_message(session_id, message_id)

        # AI 응답에서 title과 content 추출
        content_text = target_message.content

        # 정규표현식으로 title 추출
        title_match = re.search(
            r"\[TITLE_START\](.*?)\[TITLE_END\]", content_text, re.DOTALL
        )
        title = title_match.group(1).strip() if title_match else None

        # 정규표현식으로 content 추출
        content_match = re.search(
            r"\[CONTENT_START\](.*?)\[CONTENT_END\]", content_text, re.DOTALL
        )
        content = content_match.group(1).strip() if content_match else content_text

        diary = Diary(
            user_id=target_message.user_id,
            chat_session_id=session_id,
            title=title,
            content=content,
            thumbnail_url=None,
        )

        diary = await self.diary_repository.create(diary)
        await self.end_chat_session(session_id)

        payments_logs = await self.payments_repository.find_by_user_id(
            target_message.user_id, None, 1
        )

        is_user_free_trial = True

        if payments_logs.__len__() > 0:
            payments = payments_logs[0]
            if payments.end_date >= date.today():
                is_user_free_trial = False

        if is_user_free_trial:
            # user 의 free_trial_count 를 1 줄여야 함
            current_user = await self.user_repository.find_by_id(target_message.user_id)
            if current_user is None:
                raise NotFoundError()
            current_user.free_trial_count -= 1
            await self.user_repository.update(current_user)

        return diary

    async def get_diary_by_date(self, writed_at: date, user: User) -> Diary:
        diary = await self.diary_repository.find_by_date(writed_at, user.id)
        if diary is None:
            raise NotFoundError()

        return diary

    async def get_diary_by_id(self, diary_id: str) -> Diary:
        diary = await self.diary_repository.find_by_id(diary_id)

        if diary:
            return diary
        else:
            raise NotFoundError()
