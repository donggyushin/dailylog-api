from abc import ABC, abstractmethod

from src.domain.entities.diary import Emotion


class EmotionAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, content: str) -> Emotion:
        """
        Analyze the emotional tone of the given text content.

        Args:
            content: The text content to analyze (diary content)

        Returns:
            Emotion: The detected emotion (HAPPY, SAD, ANGRY, ANXIOUS, PEACEFUL, NORMAL)
        """
        pass
