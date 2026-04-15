"""Базовые интерфейсы для системы инструментов."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolDefinition:
    """Определение инструмента для LLM."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    kind: str  # "terminal", "filesystem", "other"
    requires_permission: bool = True


@dataclass
class ToolExecutionResult:
    """Результат выполнения инструмента.
    
    Атрибуты:
        success: Успешно ли выполнен инструмент
        output: Текстовый вывод инструмента (опционально)
        error: Сообщение об ошибке при неудачном выполнении (опционально)
        metadata: Дополнительные метаданные для специфичных инструментов (опционально)
    
    Примеры использования metadata:
        - terminal_id для terminal/create: {"terminal_id": "term_xyz789"}
        - diff для fs/write_text_file: {"diff": "--- old\\n+++ new\\n..."}
        - file_size для fs/read_text_file: {"file_size": 1024, "lines": 50}
    """

    success: bool
    output: str | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class ToolRegistry(ABC):
    """Реестр инструментов с механизмом выполнения."""

    @abstractmethod
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        kind: str,
        executor: Callable,
        requires_permission: bool = True,
    ) -> None:
        """Регистрация инструмента."""
        pass

    @abstractmethod
    def get_available_tools(
        self,
        session_id: str,
        include_permission_required: bool = True,
    ) -> list[ToolDefinition]:
        """Получить доступные инструменты для сессии."""
        pass

    @abstractmethod
    def to_llm_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Преобразовать определения инструментов для LLM."""
        pass

    @abstractmethod
    async def execute_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        session: Any = None,
    ) -> ToolExecutionResult:
        """Выполнить инструмент."""
        pass
