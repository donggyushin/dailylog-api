import os

from anthropic import AsyncAnthropic
from anthropic.types import TextBlock

from src.domain.entities.diary import Emotion
from src.domain.interfaces.emotion_analyzer import EmotionAnalyzer


class AnthropicEmotionAnalyzer(EmotionAnalyzer):
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-sonnet-4-6"

    async def analyze(self, content: str) -> Emotion:
        """
        Analyze the emotional tone of diary content using Claude AI.

        Args:
            content: The diary content to analyze

        Returns:
            Emotion: One of HAPPY, SAD, ANGRY, ANXIOUS, PEACEFUL, NORMAL
        """
        system_prompt = """당신은 일기 내용을 분석하여 감정을 분류하는 전문가입니다.

일기 내용을 읽고 전체적인 감정 톤을 다음 6가지 중 하나로 분류하세요:

1. happy - 기쁨, 행복, 즐거움, 흥분, 만족감이 느껴지는 경우
2. sad - 슬픔, 우울, 상실감, 아쉬움이 느껴지는 경우
3. angry - 화남, 짜증, 분노, 억울함이 느껴지는 경우
4. anxious - 불안, 걱정, 두려움, 긴장감이 느껴지는 경우
5. peaceful - 평온, 차분함, 고요함, 안정감이 느껴지는 경우
6. normal - 특별한 감정 없이 평범하고 담담한 경우

중요:
- 일기 전체의 지배적인 감정을 파악하세요
- 여러 감정이 섞여 있다면 가장 강하게 느껴지는 것을 선택하세요
- 반드시 위 6가지 중 하나의 단어만 출력하세요 (소문자로)
- 다른 설명이나 부연 없이 감정 단어 하나만 답변하세요"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=10,  # 감정 단어 하나만 출력하면 되므로 짧게
            system=system_prompt,
            messages=[{"role": "user", "content": f"일기 내용:\n\n{content}"}],
        )

        # 응답에서 텍스트 추출
        emotion_text = ""
        for item in response.content:
            if isinstance(item, TextBlock):
                emotion_text = item.text.strip().lower()
                break

        # 감정 문자열을 Enum으로 변환
        emotion_map = {
            "happy": Emotion.HAPPY,
            "sad": Emotion.SAD,
            "angry": Emotion.ANGRY,
            "anxious": Emotion.ANXIOUS,
            "peaceful": Emotion.PEACEFUL,
            "normal": Emotion.NORMAL,
        }

        # 기본값은 NORMAL
        return emotion_map.get(emotion_text, Emotion.NORMAL)
