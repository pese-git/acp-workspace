"""Базовый интерфейс для провайдеров LLM."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessage:
    """Сообщение для LLM."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMToolCall:
    """Вызов инструмента из LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Ответ от LLM."""

    text: str
    tool_calls: list[LLMToolCall]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", "error"


class LLMProvider(ABC):
    """Интерфейс для взаимодействия с LLM API.

    Провайдер инкапсулирует всю специфику работы с конкретной LLM,
    включая форматирование сообщений, обработку tool calls, retry-логику.
    """

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера с конфигурацией."""
        pass

    @abstractmethod
    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Получить завершение от LLM."""
        pass

    @abstractmethod
    async def stream_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Потоковое получение ответа от LLM."""
        pass
