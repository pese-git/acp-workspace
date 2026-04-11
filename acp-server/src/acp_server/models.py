"""Pydantic модели для типизации данных ACP Server.

Предоставляет строго типизированные модели для замены dict[str, Any]
в истории сообщений, командах, планах агента и других структурах данных.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# Модели для истории сообщений (history)
class MessageContent(BaseModel):
    """Содержимое сообщения в истории."""

    type: str
    text: str | None = None
    # Дополнительные поля для разных типов контента
    data: dict[str, Any] | None = None


class HistoryMessage(BaseModel):
    """Сообщение в истории сессии."""

    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "system"] = "user"
    content: list[MessageContent] | str | list[dict[str, Any]] | None = None
    text: str | None = None
    timestamp: str | None = None


# Модели для команд (available_commands)
class CommandParameter(BaseModel):
    """Параметр команды."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class AvailableCommand(BaseModel):
    """Доступная команда (slash command)."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str
    parameters: list[CommandParameter] = Field(default_factory=list)


# Модели для плана агента (latest_plan)
class PlanStep(BaseModel):
    """Шаг в плане агента."""

    model_config = ConfigDict(extra="allow")

    step_number: int | None = None
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    result: str | None = None


class AgentPlan(BaseModel):
    """План выполнения задачи агентом."""

    model_config = ConfigDict(extra="allow")

    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


# Модели для tool calls
class ToolCallParameter(BaseModel):
    """Параметр вызова инструмента."""

    name: str
    value: Any


class ToolCall(BaseModel):
    """Вызов инструмента агентом."""

    id: str
    name: str
    parameters: list[ToolCallParameter] = Field(default_factory=list)
    status: Literal["pending", "approved", "denied", "completed", "failed"] = "pending"
    result: Any = None
    error: str | None = None


# Модели для разрешений (permissions)
class Permission(BaseModel):
    """Разрешение на выполнение операции."""

    id: str
    type: Literal["tool_call", "file_access", "terminal_access"]
    resource: str
    action: str
    status: Literal["pending", "granted", "denied"] = "pending"
    requested_at: str
    resolved_at: str | None = None
