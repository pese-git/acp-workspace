"""Базовый интерфейс для LLM-агентов."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from acp_server.llm.base import LLMMessage, LLMProvider, LLMToolCall
from acp_server.tools.base import ToolDefinition, ToolRegistry


@dataclass
class AgentContext:
    """Контекст выполнения агента для одного prompt turn."""

    session_id: str
    prompt: list[dict[str, Any]]  # Содержимое prompt от пользователя
    conversation_history: list[LLMMessage]  # История сообщений для LLM
    available_tools: list[ToolDefinition]  # Инструменты для этого turn
    config: dict[str, Any]  # SessionState.config_values


@dataclass
class AgentResponse:
    """Ответ агента после обработки prompt."""

    text: str
    tool_calls: list[LLMToolCall]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", "error"
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMAgent(ABC):
    """Базовый интерфейс для LLM-агентов.

    Агент отвечает за:
    - Обработку prompt turns
    - Управление историей сообщений
    - Интеграцию с LLM провайдером
    - Координацию выполнения инструментов
    """

    @abstractmethod
    async def initialize(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
    ) -> None:
        """Инициализация агента."""
        pass

    @abstractmethod
    async def process_prompt(self, context: AgentContext) -> AgentResponse:
        """Обработать prompt и вернуть ответ."""
        pass

    @abstractmethod
    async def cancel_prompt(self, session_id: str) -> None:
        """Отменить текущую обработку prompt."""
        pass

    @abstractmethod
    def add_to_history(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Добавить сообщение в историю сессии."""
        pass

    @abstractmethod
    def get_session_history(self, session_id: str) -> list[LLMMessage]:
        """Получить историю сообщений для сессии."""
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> None:
        """Завершить сессию и освободить ресурсы."""
        pass
