"""Mock LLM провайдер для тестирования."""
# mypy: ignore-errors

from collections.abc import AsyncIterator
from typing import Any

from acp_server.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall


class MockLLMProvider(LLMProvider):
    """Mock провайдер для unit-тестирования.

    Возвращает предсказуемые ответы для тестирования логики агента
    без обращения к реальному API.
    """

    def __init__(
        self,
        response: str = "Mock response",
        tool_calls: list[LLMToolCall] | None = None,
    ) -> None:
        """Инициализация mock провайдера.

        Args:
            response: Текст ответа, который будет возвращен
            tool_calls: Список tool calls для возврата
        """
        self.response = response
        self.tool_calls = tool_calls or []
        self.last_messages: list[LLMMessage] | None = None
        self.last_tools: list[dict[str, Any]] | None = None

    async def initialize(self, config: dict[str, Any]) -> None:
        """Mock инициализация."""
        pass

    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Вернуть mock ответ."""
        self.last_messages = messages
        self.last_tools = tools

        return LLMResponse(
            text=self.response,
            tool_calls=self.tool_calls,
            stop_reason="end_turn" if not self.tool_calls else "tool_use",
        )

    async def stream_completion(  # type: ignore[override]
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Вернуть mock потоковый ответ."""
        self.last_messages = messages
        self.last_tools = tools

        yield LLMResponse(
            text=self.response,
            tool_calls=self.tool_calls,
            stop_reason="end_turn" if not self.tool_calls else "tool_use",
        )
