"""Dataclasses для состояния протокола ACP.

Содержит все структуры данных для хранения состояния сессий,
tool calls, и других компонентов протокола.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..messages import ACPMessage, JsonRpcId
from ..models import AvailableCommand, HistoryMessage, PlanStep


@dataclass(slots=True)
class SessionState:
    """Состояние ACP-сессии, хранимое в памяти сервера.

    Объект содержит контекст работы сессии, историю, конфигурацию и состояние
    инструментальных вызовов.

    Пример использования:
        state = SessionState(session_id="sess_1", cwd="/tmp", mcp_servers=[])
    """

    session_id: str
    cwd: str
    mcp_servers: list[dict[str, Any]]
    # Заголовок сессии для UI; выставляется из первого пользовательского запроса.
    title: str | None = None
    # Время последнего изменения сессии в формате ISO 8601.
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    # Значения конфигурационных опций в рамках этой сессии.
    config_values: dict[str, str] = field(default_factory=dict)
    # Упрощенная история, достаточная для текущих update-сценариев.
    history: list[HistoryMessage | dict[str, Any]] = field(default_factory=list)
    # Текущее активное выполнение prompt-turn (если есть).
    active_turn: ActiveTurnState | None = None
    # Локальный счетчик для стабильной генерации toolCallId.
    tool_call_counter: int = 0
    # Реестр созданных tool calls и их состояний.
    tool_calls: dict[str, ToolCallState] = field(default_factory=dict)
    # Набор доступных slash-команд для `available_commands_update`.
    available_commands: list[AvailableCommand | dict[str, Any]] = field(default_factory=list)
    # Последний опубликованный план выполнения для `session/update: plan`.
    latest_plan: list[PlanStep | dict[str, Any]] = field(default_factory=list)
    # Персистентные permission-решения по kind (например, allow_always).
    permission_policy: dict[str, str] = field(default_factory=dict)
    # Идентификаторы permission-запросов, отмененных через `session/cancel`.
    # Нужны для детерминированного игнорирования поздних client-responses.
    cancelled_permission_requests: set[JsonRpcId] = field(default_factory=set)
    # Идентификаторы agent->client RPC, отмененных через `session/cancel`.
    # Поздние ответы на такие запросы должны игнорироваться детерминированно.
    cancelled_client_rpc_requests: set[JsonRpcId] = field(default_factory=set)
    # Runtime-capabilities клиента, зафиксированные для этой сессии.
    runtime_capabilities: ClientRuntimeCapabilities | None = None
    # История событий: session/update, turn_complete, permission requests и т.д.
    # Используется для полного восстановления истории при перезагрузке сессии.
    events_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ToolCallState:
    """Состояние одного tool call внутри prompt-turn.

    Используется для управления жизненным циклом `pending -> in_progress -> ...`
    и генерации корректных `tool_call_update` уведомлений.

    Пример использования:
        call = ToolCallState("call_001", "Demo", "other", "pending")
    """

    # Идентификатор связывает `tool_call` и `tool_call_update` события.
    tool_call_id: str
    # Заголовок для отображения в клиенте.
    title: str
    # Категория вызова (например, other/execute/search).
    kind: str
    # Текущий статус жизненного цикла tool call.
    status: str
    # Контент, возвращенный при завершении (если есть).
    content: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ActiveTurnState:
    """Состояние текущего prompt-turn для корректной обработки cancel.

    Содержит идентификатор JSON-RPC запроса prompt и признак запроса отмены.

    Пример использования:
        turn = ActiveTurnState(prompt_request_id="req_1", session_id="sess_1")
    """

    prompt_request_id: JsonRpcId | None
    session_id: str
    cancel_requested: bool = False
    # Идентификатор исходящего permission-request при режиме `ask`.
    permission_request_id: JsonRpcId | None = None
    # Связанный tool call, ожидающий решения пользователя.
    permission_tool_call_id: str | None = None
    # Фаза жизненного цикла prompt-turn для детерминированного поведения.
    phase: str = "running"
    # Исходящий запрос к клиенту (fs/*), если turn ожидает его completion.
    pending_client_request: PendingClientRequestState | None = None


@dataclass(slots=True)
class PromptDirectives:
    """Нормализованные флаги поведения prompt-turn из пользовательского ввода.

    Используются для детерминированной slash-driven оркестрации prompt-turn
    без legacy marker-триггеров.

    Пример использования:
        directives = PromptDirectives(request_tool=True, keep_tool_pending=False)
    """

    request_tool: bool = False
    keep_tool_pending: bool = False
    publish_plan: bool = False
    plan_entries: list[dict[str, str]] | None = None
    tool_kind: str = "other"
    fs_read_path: str | None = None
    fs_write_path: str | None = None
    fs_write_content: str | None = None
    terminal_command: str | None = None
    forced_stop_reason: str | None = None


@dataclass(slots=True)
class PendingClientRequestState:
    """Состояние исходящего agent->client request внутри активного turn.

    Нужно для корреляции входящего client response с ожидаемым действием
    (например, `fs/read_text_file` или `fs/write_text_file`).

    Пример использования:
        pending = PendingClientRequestState(
            request_id="req_1",
            kind="fs_read",
            tool_call_id="call_001",
            path="/tmp/README.md",
        )
    """

    request_id: JsonRpcId
    kind: str
    tool_call_id: str
    path: str
    expected_new_text: str | None = None
    terminal_id: str | None = None
    terminal_output: str | None = None
    terminal_exit_code: int | None = None
    terminal_signal: str | None = None
    terminal_truncated: bool | None = None


@dataclass(slots=True)
class PreparedFsClientRequest:
    """Подготовленный пакет сообщений для fs/* agent->client запроса.

    Пример использования:
        prepared = PreparedFsClientRequest(messages=[...], pending_request=pending)
    """

    kind: str
    messages: list[ACPMessage]
    pending_request: PendingClientRequestState


@dataclass(slots=True)
class ClientRuntimeCapabilities:
    """Согласованные на `initialize` возможности клиентского runtime.

    Используются как feature-gate для веток, где агент ожидает клиентские
    RPC-возможности (например, запуск инструментов через client-side runtime).

    Пример использования:
        caps = ClientRuntimeCapabilities(fs_read=False, fs_write=False, terminal=True)
    """

    fs_read: bool = False
    fs_write: bool = False
    terminal: bool = False


@dataclass(slots=True)
class ProtocolOutcome:
    """Результат обработки входящего ACP-сообщения.

    Включает финальный response (если нужен) и список промежуточных
    notifications, которые транспорт должен отправить в указанном порядке.

    Пример использования:
        outcome = ProtocolOutcome(response=ACPMessage.response("id", {}))
    """

    response: ACPMessage | None = None
    notifications: list[ACPMessage] = field(default_factory=list)
    # Дополнительные response-сообщения для отложенных JSON-RPC запросов (WS).
    followup_responses: list[ACPMessage] = field(default_factory=list)
