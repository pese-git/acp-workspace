"""LLM провайдеры и интерфейсы для работы с языковыми моделями.

Поддерживает несколько реализаций: OpenAI, Mock (для разработки и тестирования).
"""

from codelab.server.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolCall,
)
from codelab.server.llm.mock_provider import MockLLMProvider
from codelab.server.llm.openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMToolCall",
    "OpenAIProvider",
    "MockLLMProvider",
]
