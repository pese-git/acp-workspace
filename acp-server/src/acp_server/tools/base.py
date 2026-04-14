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
    """Результат выполнения инструмента."""

    success: bool
    output: str | None = None
    error: str | None = None


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
    ) -> ToolExecutionResult:
        """Выполнить инструмент."""
        pass
