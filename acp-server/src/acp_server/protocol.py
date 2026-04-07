"""In-memory реализация ACP-протокола для demo/интеграционных сценариев.

Модуль инкапсулирует обработку JSON-RPC методов (`initialize`, `session/*`,
legacy `ping/echo/shutdown`) и формирует поток `session/update` событий.

Пример использования:
    protocol = ACPProtocol()
    outcome = protocol.handle(ACPMessage.request("initialize", {}))
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .messages import ACPMessage, JsonRpcId


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
    history: list[dict[str, Any]] = field(default_factory=list)
    # Текущее активное выполнение prompt-turn (если есть).
    active_turn: ActiveTurnState | None = None
    # Локальный счетчик для стабильной генерации toolCallId.
    tool_call_counter: int = 0
    # Реестр созданных tool calls и их состояний.
    tool_calls: dict[str, ToolCallState] = field(default_factory=dict)
    # Набор доступных slash-команд для `available_commands_update`.
    available_commands: list[dict[str, Any]] = field(default_factory=list)
    # Последний опубликованный план выполнения для `session/update: plan`.
    latest_plan: list[dict[str, str]] = field(default_factory=list)
    # Персистентные permission-решения по kind (например, allow_always).
    permission_policy: dict[str, str] = field(default_factory=dict)
    # Идентификаторы permission-запросов, отмененных через `session/cancel`.
    # Нужны для детерминированного игнорирования поздних client-responses.
    cancelled_permission_requests: set[JsonRpcId] = field(default_factory=set)
    # Runtime-capabilities клиента, зафиксированные для этой сессии.
    runtime_capabilities: ClientRuntimeCapabilities | None = None


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


class ACPProtocol:
    """Диспетчер ACP-методов и in-memory реализация сессионного протокола.

    Класс принимает валидированные JSON-RPC сообщения и возвращает
    `ProtocolOutcome` для транспортного слоя.

    Пример использования:
        protocol = ACPProtocol()
        outcome = protocol.handle(ACPMessage.request("initialize", {}))
    """

    def __init__(self, *, require_auth: bool = False) -> None:
        """Инициализирует протокол и пустое хранилище сессий.

        Пример использования:
            protocol = ACPProtocol()
        """

        self._sessions: dict[str, SessionState] = {}
        # Последние capabilities, согласованные через initialize.
        # Для in-memory demo-сервера это достаточно; по мере роста можно
        # расширить до connection-scoped хранилища.
        self._runtime_capabilities: ClientRuntimeCapabilities | None = None
        # Флаг для сценариев, где агент требует authenticate до session setup.
        self._require_auth = require_auth
        # Состояние аутентификации текущего протокольного инстанса.
        self._authenticated = False
        self._auth_methods: list[dict[str, Any]] = [
            {
                "id": "local",
                "name": "Local authentication",
                "description": "Demo local authentication flow",
                "type": "api_key",
            }
        ]

    _config_specs: dict[str, dict[str, Any]] = {
        "mode": {
            "name": "Session Mode",
            "category": "mode",
            "default": "ask",
            "options": [
                {
                    "value": "ask",
                    "name": "Ask",
                    "description": "Request permission before sensitive actions",
                },
                {
                    "value": "code",
                    "name": "Code",
                    "description": "Execute actions without per-step approval",
                },
            ],
        },
        "model": {
            "name": "Model",
            "category": "model",
            "default": "baseline",
            "options": [
                {
                    "value": "baseline",
                    "name": "Baseline",
                    "description": "Balanced speed and quality",
                }
            ],
        },
    }
    _supported_protocol_versions = (1,)
    _supported_stop_reasons = {
        "end_turn",
        "max_tokens",
        "max_turn_requests",
        "refusal",
        "cancelled",
    }
    # Размер страницы для `session/list`; cursor указывает смещение в этом срезе.
    _session_list_page_size = 50

    def handle(self, message: ACPMessage) -> ProtocolOutcome:
        """Обрабатывает входящее сообщение и маршрутизирует его по ACP-методу.

        Метод является основной точкой входа для HTTP/WS транспорта.

        Пример использования:
            outcome = protocol.handle(ACPMessage.request("session/list", {}))
        """

        # Сервер принимает только входящие requests/notifications.
        if message.method is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    message.id,
                    code=-32600,
                    message="Invalid request: unexpected response payload",
                )
            )

        method = message.method
        params = message.params or {}

        # Явный диспетчер методов упрощает проверку протокольных веток.
        if method == "initialize":
            return ProtocolOutcome(response=self._initialize(message.id, params))
        if method == "authenticate":
            return ProtocolOutcome(response=self._authenticate(message.id, params))
        if method == "session/new":
            return ProtocolOutcome(response=self._session_new(message.id, params))
        if method == "session/load":
            return self._session_load(message.id, params)
        if method == "session/list":
            return ProtocolOutcome(response=self._session_list(message.id, params))
        if method == "session/prompt":
            return self._session_prompt(message.id, params)
        if method == "session/cancel":
            return self._session_cancel(message.id, params)
        if method == "session/set_config_option":
            return self._session_set_config_option(message.id, params)
        if method == "session/set_mode":
            return self._session_set_mode(message.id, params)
        if method == "ping":
            return ProtocolOutcome(response=ACPMessage.response(message.id, {"pong": True}))
        if method == "echo":
            return ProtocolOutcome(response=ACPMessage.response(message.id, {"echo": params}))
        if method == "shutdown":
            return ProtocolOutcome(
                response=ACPMessage.response(
                    message.id,
                    {
                        "ok": True,
                        "message": "Server session closed",
                    },
                )
            )

        if message.is_notification:
            return ProtocolOutcome()

        return ProtocolOutcome(
            response=ACPMessage.error_response(
                message.id,
                code=-32601,
                message=f"Method not found: {method}",
            )
        )

    def _initialize(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
        """Формирует ответ на `initialize` с перечнем возможностей агента.

        Пример использования:
            response = protocol._initialize("req_1", {"protocolVersion": 1})
        """

        # Для ACP handshake поле `protocolVersion` является обязательным.
        if "protocolVersion" not in params:
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: protocolVersion is required",
            )

        requested_version = params.get("protocolVersion")
        if not isinstance(requested_version, int):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: protocolVersion must be an integer",
            )

        # По спецификации клиент обязан передать объект capabilities.
        client_capabilities = params.get("clientCapabilities")
        if not isinstance(client_capabilities, dict):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: clientCapabilities must be an object",
            )

        client_info = params.get("clientInfo")
        if client_info is not None and not isinstance(client_info, dict):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: clientInfo must be an object",
            )

        # Сохраняем согласованные runtime-возможности клиента для feature-gate.
        self._runtime_capabilities = self._parse_client_runtime_capabilities(client_capabilities)

        negotiated_version = self._supported_protocol_versions[-1]
        if (
            isinstance(requested_version, int)
            and requested_version in self._supported_protocol_versions
        ):
            negotiated_version = requested_version

        # Инициализация capability negotiation для ACP v1.
        result = {
            "protocolVersion": negotiated_version,
            "agentCapabilities": {
                "loadSession": True,
                "mcpCapabilities": {"http": False, "sse": False},
                "promptCapabilities": {
                    "image": False,
                    "audio": False,
                    "embeddedContext": False,
                },
                "sessionCapabilities": {},
            },
            "agentInfo": {
                "name": "acp-server",
                "title": "ACP Server",
                "version": "0.1.0",
            },
            "authMethods": self._auth_methods if self._require_auth else [],
        }
        result["agentCapabilities"]["sessionCapabilities"] = {
            "list": {},
        }
        return ACPMessage.response(request_id, result)

    def _authenticate(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
        """Обрабатывает `authenticate` и отмечает протокольный инстанс как auth-ok.

        Пример использования:
            response = protocol._authenticate("req_1", {"methodId": "local"})
        """

        if not self._require_auth:
            return ACPMessage.response(request_id, {})

        method_id = params.get("methodId")
        if not isinstance(method_id, str):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: methodId is required",
            )

        known_method_ids = {
            method.get("id")
            for method in self._auth_methods
            if isinstance(method, dict) and isinstance(method.get("id"), str)
        }
        if method_id not in known_method_ids:
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: unknown authentication method",
            )

        self._authenticated = True
        return ACPMessage.response(request_id, {})

    def _auth_required_error(self, request_id: JsonRpcId | None) -> ACPMessage:
        """Строит унифицированную ошибку `auth_required` для session setup методов.

        Пример использования:
            return protocol._auth_required_error("req_1")
        """

        return ACPMessage.error_response(
            request_id,
            code=-32010,
            message="auth_required",
            data={"authMethods": self._auth_methods},
        )

    def _session_new(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
        """Создает новую in-memory сессию и возвращает ее идентификатор.

        Метод валидирует `cwd`, инициализирует config options и дефолтные
        slash-команды.

        Пример использования:
            response = protocol._session_new("req_1", {"cwd": "/tmp", "mcpServers": []})
        """

        if self._require_auth and not self._authenticated:
            return self._auth_required_error(request_id)

        # По спецификации cwd должен быть абсолютным путем.
        cwd = params.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: cwd must be an absolute path",
            )

        mcp_servers = params.get("mcpServers", [])
        if not isinstance(mcp_servers, list):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: mcpServers must be an array",
            )

        session_id = f"sess_{uuid4().hex[:12]}"
        config_values = {
            config_id: str(spec["default"]) for config_id, spec in self._config_specs.items()
        }
        self._sessions[session_id] = SessionState(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=[server for server in mcp_servers if isinstance(server, dict)],
            config_values=config_values,
            available_commands=self._build_default_commands(),
            runtime_capabilities=self._runtime_capabilities,
        )
        return ACPMessage.response(
            request_id,
            {
                "sessionId": session_id,
                "configOptions": self._build_config_options(config_values),
                "modes": self._build_modes_state(config_values),
            },
        )

    def _session_load(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
    ) -> ProtocolOutcome:
        """Загружает существующую сессию и реплеит состояние через updates.

        Возвращает `result: null` и набор `session/update` уведомлений:
        история сообщений, config options, команды и session info.

        Пример использования:
            outcome = protocol._session_load(
                "req_1",
                {"sessionId": "sess_1", "cwd": "/tmp", "mcpServers": []},
            )
        """

        if self._require_auth and not self._authenticated:
            return ProtocolOutcome(response=self._auth_required_error(request_id))

        # Загрузка поддерживает in-memory сессии и реплей накопленной истории в `session/update`.
        session_id = params.get("sessionId")
        cwd = params.get("cwd")
        mcp_servers = params.get("mcpServers")

        if not isinstance(session_id, str):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: sessionId is required",
                )
            )
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: cwd must be an absolute path",
                )
            )
        if not isinstance(mcp_servers, list):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: mcpServers must be an array",
                )
            )

        session = self._sessions.get(session_id)
        if session is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32001,
                    message=f"Session not found: {session_id}",
                )
            )

        # При загрузке фиксируем актуальный контекст клиента.
        session.cwd = cwd
        session.mcp_servers = [server for server in mcp_servers if isinstance(server, dict)]
        session.runtime_capabilities = self._runtime_capabilities

        notifications: list[ACPMessage] = []
        for entry in session.history:
            role = entry.get("role") if isinstance(entry, dict) else None
            content = entry.get("content") if isinstance(entry, dict) else None
            if role == "user" and isinstance(content, list):
                for block in content:
                    notifications.append(
                        ACPMessage.notification(
                            "session/update",
                            {
                                "sessionId": session_id,
                                "update": {
                                    "sessionUpdate": "user_message_chunk",
                                    "content": block,
                                },
                            },
                        )
                    )
            if role == "agent" and isinstance(content, list):
                for block in content:
                    notifications.append(
                        ACPMessage.notification(
                            "session/update",
                            {
                                "sessionId": session_id,
                                "update": {
                                    "sessionUpdate": "agent_message_chunk",
                                    "content": block,
                                },
                            },
                        )
                    )

        if session.latest_plan:
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "plan",
                            "entries": session.latest_plan,
                        },
                    },
                )
            )

        # Реплеим текущее состояние tool calls, чтобы клиент восстановил UI.
        for tool_call in session.tool_calls.values():
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": tool_call.tool_call_id,
                            "title": tool_call.title,
                            "kind": tool_call.kind,
                            "status": "pending",
                        },
                    },
                )
            )
            if tool_call.status != "pending":
                update_payload: dict[str, Any] = {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": tool_call.tool_call_id,
                    "status": tool_call.status,
                }
                if tool_call.content:
                    update_payload["content"] = tool_call.content
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": update_payload,
                        },
                    )
                )

        notifications.append(
            ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "config_option_update",
                        "configOptions": self._build_config_options(session.config_values),
                    },
                },
            )
        )
        notifications.append(
            ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "available_commands_update",
                        "availableCommands": session.available_commands,
                    },
                },
            )
        )
        notifications.append(
            self._session_info_notification(
                session_id=session_id,
                title=session.title,
                updated_at=session.updated_at,
            )
        )

        return ProtocolOutcome(
            response=ACPMessage.response(
                request_id,
                {
                    "configOptions": self._build_config_options(session.config_values),
                    "modes": self._build_modes_state(session.config_values),
                },
            ),
            notifications=notifications,
        )

    def _session_list(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
        """Возвращает список сессий с опциональной фильтрацией по `cwd`.

        Пример использования:
            response = protocol._session_list("req_1", {"cwd": "/tmp"})
        """

        # Поддерживаем фильтрацию сессий по cwd для клиентских списков.
        cwd_filter = params.get("cwd")
        cursor = params.get("cursor")
        if cwd_filter is not None and (
            not isinstance(cwd_filter, str) or not Path(cwd_filter).is_absolute()
        ):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: cwd must be an absolute path",
            )
        if cursor is not None and not isinstance(cursor, str):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: cursor must be a string",
            )

        start_index = 0
        if isinstance(cursor, str):
            decoded = self._decode_session_cursor(cursor)
            if decoded is None:
                return ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: cursor is invalid",
                )
            start_index = decoded

        sessions: list[dict[str, Any]] = []
        for session in self._sessions.values():
            if isinstance(cwd_filter, str) and session.cwd != cwd_filter:
                continue
            sessions.append(
                {
                    "sessionId": session.session_id,
                    "cwd": session.cwd,
                    "title": session.title,
                    "updatedAt": session.updated_at,
                }
            )

        sorted_sessions = sorted(
            sessions, key=lambda item: str(item.get("updatedAt") or ""), reverse=True
        )
        page_end = start_index + self._session_list_page_size
        page = sorted_sessions[start_index:page_end]
        next_cursor: str | None = None
        if page_end < len(sorted_sessions):
            next_cursor = self._encode_session_cursor(page_end)

        return ACPMessage.response(request_id, {"sessions": page, "nextCursor": next_cursor})

    def _encode_session_cursor(self, index: int) -> str:
        """Кодирует индекс страницы в opaque cursor для `session/list`.

        Пример использования:
            cursor = protocol._encode_session_cursor(50)
        """

        payload = json.dumps({"index": index}, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii")

    def _decode_session_cursor(self, cursor: str) -> int | None:
        """Декодирует opaque cursor `session/list` в индекс начала страницы.

        Возвращает `None`, если cursor поврежден или невалиден.

        Пример использования:
            index = protocol._decode_session_cursor(cursor)
        """

        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        index = payload.get("index")
        if not isinstance(index, int) or index < 0:
            return None
        return index

    def _build_modes_state(self, values: dict[str, str]) -> dict[str, Any]:
        """Строит legacy-состояние modes для совместимых клиентов ACP.

        Пример использования:
            modes = protocol._build_modes_state({"mode": "ask", "model": "baseline"})
        """

        mode_option = self._config_specs.get("mode", {})
        available_modes = []
        for option in mode_option.get("options", []):
            if isinstance(option, dict) and isinstance(option.get("value"), str):
                available_modes.append(
                    {
                        "id": option["value"],
                        "name": option.get("name", option["value"]),
                        "description": option.get("description"),
                    }
                )

        return {
            "availableModes": available_modes,
            "currentModeId": values.get("mode", str(mode_option.get("default", "ask"))),
        }

    def _session_prompt(
        self, request_id: JsonRpcId | None, params: dict[str, Any]
    ) -> ProtocolOutcome:
        """Обрабатывает пользовательский prompt-turn и формирует updates.

        Метод валидирует контент, добавляет сообщение агента, обновляет историю,
        публикует `session_info_update` и `available_commands_update`.

        Пример использования:
            outcome = protocol._session_prompt("req_1", {"sessionId": "sess_1", "prompt": []})
        """

        session_id = params.get("sessionId")
        prompt = params.get("prompt")

        if not isinstance(session_id, str):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: sessionId is required",
                )
            )

        session = self._sessions.get(session_id)
        if session is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32001,
                    message=f"Session not found: {session_id}",
                )
            )

        if not isinstance(prompt, list):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: prompt must be an array",
                )
            )

        content_error = self._validate_prompt_content(request_id, prompt)
        if content_error is not None:
            return ProtocolOutcome(response=content_error)

        if session.active_turn is not None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32002,
                    message=f"Session busy: active turn in progress for {session_id}",
                )
            )

        session.active_turn = ActiveTurnState(prompt_request_id=request_id, session_id=session_id)

        # Извлекаем первый text-блок для демо-ответа и формирования заголовка сессии.
        text_blocks: list[str] = []
        for block in prompt:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ):
                text_blocks.append(block["text"])
        text_preview = text_blocks[0] if text_blocks else "Prompt received"
        prompt_for_title = text_preview.strip()
        directives = self._extract_prompt_directives(text_preview)
        tool_runtime_available = self._can_run_tool_runtime(session)
        should_run_tool_flow = directives.request_tool and tool_runtime_available
        tool_title = self._resolve_demo_tool_title(directives.tool_kind)

        # Все промежуточные события отправляются через `session/update`.
        notifications: list[ACPMessage] = []

        agent_text = f"ACK: {text_preview}"
        update = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": agent_text,
                    },
                },
            },
        )
        notifications.append(update)

        if directives.publish_plan:
            # В demo-режиме публикуем пример плана для клиентских UI.
            plan_entries = [
                {
                    "content": "Проанализировать текущее состояние проекта",
                    "priority": "high",
                    "status": "completed",
                },
                {
                    "content": "Внести минимальные изменения в код",
                    "priority": "high",
                    "status": "in_progress",
                },
                {
                    "content": "Запустить проверки и подготовить результат",
                    "priority": "medium",
                    "status": "pending",
                },
            ]
            session.latest_plan = plan_entries
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "plan",
                            "entries": plan_entries,
                        },
                    },
                )
            )

        terminal_request = self._build_terminal_client_request(
            session=session,
            session_id=session_id,
            directives=directives,
        )
        fs_request = self._build_fs_client_request(
            session=session,
            session_id=session_id,
            directives=directives,
        )

        should_request_permission = False
        prompt_stop_reason = self._resolve_prompt_stop_reason(directives)
        if terminal_request is not None:
            if self._can_use_terminal_client_rpc(session):
                notifications.extend(terminal_request.messages)
                session.active_turn.pending_client_request = terminal_request.pending_request
                session.active_turn.phase = "waiting_client_rpc"
            else:
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        "Terminal RPC is unavailable for this "
                                        "client capabilities profile."
                                    ),
                                },
                            },
                        },
                    )
                )
        elif fs_request is not None:
            if self._can_use_fs_client_rpc(session, fs_request.kind):
                notifications.extend(fs_request.messages)
                session.active_turn.pending_client_request = fs_request.pending_request
                session.active_turn.phase = "waiting_client_rpc"
            else:
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        "File system RPC is unavailable for this "
                                        "client capabilities profile."
                                    ),
                                },
                            },
                        },
                    )
                )
        elif should_run_tool_flow and session.config_values.get("mode", "ask") == "ask":
            tool_call_id = self._create_tool_call(
                session=session,
                title=tool_title,
                kind=directives.tool_kind,
            )
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": tool_call_id,
                            "title": tool_title,
                            "kind": directives.tool_kind,
                            "status": "pending",
                        },
                    },
                )
            )
            remembered_permission = session.permission_policy.get(directives.tool_kind)
            if remembered_permission == "allow_always":
                notifications.extend(
                    self._build_demo_tool_execution_updates(
                        session=session,
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        allowed=True,
                    )
                )
            elif remembered_permission == "reject_always":
                notifications.extend(
                    self._build_demo_tool_execution_updates(
                        session=session,
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        allowed=False,
                    )
                )
                prompt_stop_reason = "cancelled"
            else:
                permission_request = ACPMessage.request(
                    "session/request_permission",
                    {
                        "sessionId": session_id,
                        "toolCall": {
                            "toolCallId": tool_call_id,
                            "title": tool_title,
                            "kind": directives.tool_kind,
                            "status": "pending",
                        },
                        "options": self._build_permission_options(),
                    },
                )
                session.active_turn.permission_request_id = permission_request.id
                session.active_turn.permission_tool_call_id = tool_call_id
                session.active_turn.phase = "waiting_permission"
                notifications.append(permission_request)
                should_request_permission = True
        else:
            # Демонстрационный tool-call lifecycle для совместимости с ACP-клиентами.
            tool_notifications = self._build_tool_call_updates(
                session=session,
                session_id=session_id,
                prompt_requests_tool=should_run_tool_flow,
                leave_running=directives.keep_tool_pending,
                tool_kind=directives.tool_kind,
            )
            notifications.extend(tool_notifications)

            if directives.request_tool and not should_run_tool_flow:
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {
                                    "type": "text",
                                    "text": (
                                        "Tool runtime unavailable for this client "
                                        "capabilities profile."
                                    ),
                                },
                            },
                        },
                    )
                )

        session.history.append({"role": "user", "content": prompt})
        session.history.append(
            {
                "role": "agent",
                "content": [
                    {
                        "type": "text",
                        "text": agent_text,
                    }
                ],
            }
        )
        session.updated_at = datetime.now(UTC).isoformat()

        # Заголовок задаем один раз, чтобы не перетирать пользовательские изменения.
        title_changed = False
        if session.title is None and prompt_for_title:
            session.title = prompt_for_title[:80]
            title_changed = True

        notifications.append(
            self._session_info_notification(
                session_id=session_id,
                title=session.title if title_changed else None,
                updated_at=session.updated_at,
            )
        )

        # Команды можно динамически менять между запросами; отправляем текущий snapshot.
        notifications.append(
            ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "available_commands_update",
                        "availableCommands": session.available_commands,
                    },
                },
            )
        )

        should_defer_completion = (
            directives.keep_tool_pending and should_run_tool_flow
        ) or should_request_permission
        should_defer_completion = (
            should_defer_completion or session.active_turn.pending_client_request is not None
        )
        if should_defer_completion:
            # Для незавершенных tool-call оставляем prompt-request «в полете».
            # Финальный response будет отправлен позже (автозавершение или cancel).
            if directives.keep_tool_pending and should_run_tool_flow:
                session.active_turn.phase = "waiting_tool_completion"
            return ProtocolOutcome(response=None, notifications=notifications)

        outcome = ProtocolOutcome(
            response=ACPMessage.response(request_id, {"stopReason": prompt_stop_reason}),
            notifications=notifications,
        )
        session.active_turn = None
        return outcome

    def _session_cancel(
        self, request_id: JsonRpcId | None, params: dict[str, Any]
    ) -> ProtocolOutcome:
        """Отменяет текущий turn сессии и активные tool calls.

        Если запрос пришел как notification (без `id`), response не возвращается.

        Пример использования:
            outcome = protocol._session_cancel(None, {"sessionId": "sess_1"})
        """

        session_id = params.get("sessionId")
        notifications: list[ACPMessage] = []
        if isinstance(session_id, str) and session_id in self._sessions:
            session = self._sessions[session_id]
            if (
                session.active_turn is not None
                and session.active_turn.permission_request_id is not None
            ):
                # Фиксируем отмененный permission-request, чтобы его поздний
                # response не мог повлиять на последующие turn-циклы.
                session.cancelled_permission_requests.add(session.active_turn.permission_request_id)
            pending = (
                session.active_turn.pending_client_request
                if session.active_turn is not None
                else None
            )
            if pending is not None and pending.terminal_id is not None:
                # Для terminal-flow отправляем best-effort cleanup перед завершением turn.
                notifications.append(
                    ACPMessage.request(
                        "terminal/kill",
                        {
                            "sessionId": session_id,
                            "terminalId": pending.terminal_id,
                        },
                    )
                )
                notifications.append(
                    ACPMessage.request(
                        "terminal/release",
                        {
                            "sessionId": session_id,
                            "terminalId": pending.terminal_id,
                        },
                    )
                )
            cancelled_prompt_response = self._finalize_active_turn(
                session=session,
                stop_reason="cancelled",
            )
            # При отмене переводим все незавершенные tool calls в `cancelled`.
            notifications.extend(
                self._cancel_active_tool_calls(session=session, session_id=session_id)
            )
            session.updated_at = datetime.now(UTC).isoformat()
            notifications.append(
                self._session_info_notification(
                    session_id=session_id,
                    title=None,
                    updated_at=session.updated_at,
                )
            )
            followup_responses: list[ACPMessage] = []
            if cancelled_prompt_response is not None:
                followup_responses.append(cancelled_prompt_response)
        else:
            followup_responses = []

        if request_id is None:
            return ProtocolOutcome(
                response=None,
                notifications=notifications,
                followup_responses=followup_responses,
            )

        return ProtocolOutcome(
            response=ACPMessage.response(request_id, None),
            notifications=notifications,
            followup_responses=followup_responses,
        )

    def complete_active_turn(
        self, session_id: str, *, stop_reason: str = "end_turn"
    ) -> ACPMessage | None:
        """Завершает активный prompt-turn и возвращает финальный response.

        Используется транспортом WS для отложенного ответа на `session/prompt`.

        Пример использования:
            response = protocol.complete_active_turn("sess_1", stop_reason="end_turn")
        """

        session = self._sessions.get(session_id)
        if session is None:
            return None
        return self._finalize_active_turn(
            session=session,
            stop_reason=self._normalize_stop_reason(stop_reason),
        )

    def should_auto_complete_active_turn(self, session_id: str) -> bool:
        """Возвращает `True`, если active turn можно безопасно автозавершить.

        Если turn ожидает permission-response, автозавершение запрещено.

        Пример использования:
            if protocol.should_auto_complete_active_turn("sess_1"):
                ...
        """

        session = self._sessions.get(session_id)
        if session is None or session.active_turn is None:
            return False
        return session.active_turn.phase == "waiting_tool_completion"

    def handle_client_response(self, message: ACPMessage) -> ProtocolOutcome:
        """Обрабатывает входящий response от клиента для server-originated requests.

        Сейчас используется для `session/request_permission`, отправленного ранее
        в рамках active prompt-turn.

        Пример использования:
            outcome = protocol.handle_client_response(client_response)
        """

        if message.id is None:
            return ProtocolOutcome()

        resolved_client_rpc = self._resolve_pending_client_rpc_response(
            request_id=message.id,
            result=message.result,
            error=message.error.model_dump(exclude_none=True)
            if message.error is not None
            else None,
        )
        if resolved_client_rpc is not None:
            return resolved_client_rpc

        if self._consume_cancelled_permission_response(message.id):
            # Late response на уже отмененный permission-request считаем
            # корректно обработанным no-op, чтобы избежать race-эффектов.
            return ProtocolOutcome()

        resolved = self._resolve_permission_response(message.id, message.result)
        if resolved is None:
            return ProtocolOutcome()
        return resolved

    def _consume_cancelled_permission_response(self, request_id: JsonRpcId) -> bool:
        """Поглощает late-response на ранее отмененный permission-request.

        Возвращает `True`, если идентификатор найден в canceled-tombstones и
        удален; иначе `False`.

        Пример использования:
            if protocol._consume_cancelled_permission_response("perm_1"):
                ...
        """

        for session in self._sessions.values():
            if request_id not in session.cancelled_permission_requests:
                continue
            session.cancelled_permission_requests.remove(request_id)
            return True
        return False

    def _resolve_pending_client_rpc_response(
        self,
        *,
        request_id: JsonRpcId,
        result: Any,
        error: dict[str, Any] | None,
    ) -> ProtocolOutcome | None:
        """Обрабатывает response на ожидаемый agent->client fs/* request.

        Пример использования:
            outcome = protocol._resolve_pending_client_rpc_response(
                request_id="req_1",
                result={"content": "ok"},
                error=None,
            )
        """

        session = self._find_session_by_pending_client_request_id(request_id)
        if session is None or session.active_turn is None:
            return None
        pending = session.active_turn.pending_client_request
        if pending is None:
            return None

        session_id = session.session_id
        notifications: list[ACPMessage] = []

        if error is not None:
            self._update_tool_call_status(session, pending.tool_call_id, "failed")
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": pending.tool_call_id,
                            "status": "failed",
                            "content": [
                                {
                                    "type": "content",
                                    "content": {
                                        "type": "text",
                                        "text": "Client RPC request failed.",
                                    },
                                }
                            ],
                        },
                    },
                )
            )
            session.updated_at = datetime.now(UTC).isoformat()
            notifications.append(
                self._session_info_notification(
                    session_id=session_id,
                    title=None,
                    updated_at=session.updated_at,
                )
            )
            failed = self._finalize_active_turn(session=session, stop_reason="end_turn")
            return ProtocolOutcome(
                notifications=notifications,
                followup_responses=[failed] if failed is not None else [],
            )

        if pending.kind == "fs_read":
            content_text = ""
            if isinstance(result, dict) and isinstance(result.get("content"), str):
                content_text = result["content"]
            self._update_tool_call_status(
                session,
                pending.tool_call_id,
                "completed",
                content=[
                    {
                        "type": "content",
                        "content": {
                            "type": "text",
                            "text": content_text,
                        },
                    }
                ],
            )
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": pending.tool_call_id,
                            "status": "completed",
                            "content": [
                                {
                                    "type": "content",
                                    "content": {
                                        "type": "text",
                                        "text": content_text,
                                    },
                                }
                            ],
                        },
                    },
                )
            )
        elif pending.kind == "fs_write":
            old_text: str | None = None
            new_text = pending.expected_new_text or ""
            if isinstance(result, dict):
                if isinstance(result.get("oldText"), str):
                    old_text = result["oldText"]
                if isinstance(result.get("newText"), str):
                    new_text = result["newText"]

            diff_content = [
                {
                    "type": "diff",
                    "path": pending.path,
                    "oldText": old_text,
                    "newText": new_text,
                }
            ]
            self._update_tool_call_status(
                session,
                pending.tool_call_id,
                "completed",
                content=diff_content,
            )
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": pending.tool_call_id,
                            "status": "completed",
                            "content": diff_content,
                        },
                    },
                )
            )
        elif pending.kind == "terminal_create":
            terminal_id = None
            if isinstance(result, dict) and isinstance(result.get("terminalId"), str):
                terminal_id = result["terminalId"]
            if terminal_id is None:
                self._update_tool_call_status(session, pending.tool_call_id, "failed")
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "tool_call_update",
                                "toolCallId": pending.tool_call_id,
                                "status": "failed",
                            },
                        },
                    )
                )
                done = self._finalize_active_turn(session=session, stop_reason="end_turn")
                return ProtocolOutcome(
                    notifications=notifications,
                    followup_responses=[done] if done is not None else [],
                )

            self._update_tool_call_status(session, pending.tool_call_id, "in_progress")
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": pending.tool_call_id,
                            "status": "in_progress",
                            "content": [{"type": "terminal", "terminalId": terminal_id}],
                        },
                    },
                )
            )

            output_request = ACPMessage.request(
                "terminal/output",
                {
                    "sessionId": session_id,
                    "terminalId": terminal_id,
                },
            )
            if output_request.id is None:
                return None
            session.active_turn.pending_client_request = PendingClientRequestState(
                request_id=output_request.id,
                kind="terminal_output",
                tool_call_id=pending.tool_call_id,
                path=pending.path,
                terminal_id=terminal_id,
            )
            notifications.append(output_request)
            return ProtocolOutcome(notifications=notifications)
        elif pending.kind == "terminal_output":
            terminal_id = pending.terminal_id
            if terminal_id is None:
                return None
            output_text = ""
            if isinstance(result, dict) and isinstance(result.get("output"), str):
                output_text = result["output"]

            wait_request = ACPMessage.request(
                "terminal/wait_for_exit",
                {
                    "sessionId": session_id,
                    "terminalId": terminal_id,
                },
            )
            if wait_request.id is None:
                return None
            session.active_turn.pending_client_request = PendingClientRequestState(
                request_id=wait_request.id,
                kind="terminal_wait_for_exit",
                tool_call_id=pending.tool_call_id,
                path=pending.path,
                terminal_id=terminal_id,
                terminal_output=output_text,
            )
            notifications.append(wait_request)
            return ProtocolOutcome(notifications=notifications)
        elif pending.kind == "terminal_wait_for_exit":
            terminal_id = pending.terminal_id
            if terminal_id is None:
                return None
            exit_code = None
            if isinstance(result, dict) and isinstance(result.get("exitCode"), int):
                exit_code = result["exitCode"]

            release_request = ACPMessage.request(
                "terminal/release",
                {
                    "sessionId": session_id,
                    "terminalId": terminal_id,
                },
            )
            if release_request.id is None:
                return None
            session.active_turn.pending_client_request = PendingClientRequestState(
                request_id=release_request.id,
                kind="terminal_release",
                tool_call_id=pending.tool_call_id,
                path=pending.path,
                terminal_id=terminal_id,
                terminal_output=pending.terminal_output,
                terminal_exit_code=exit_code,
            )
            notifications.append(release_request)
            return ProtocolOutcome(notifications=notifications)
        elif pending.kind == "terminal_release":
            terminal_id = pending.terminal_id
            if terminal_id is None:
                return None
            completion_text = (
                f"Terminal command finished with exit code {pending.terminal_exit_code}."
            )
            if pending.terminal_exit_code is None:
                completion_text = "Terminal command finished."
            if pending.terminal_output:
                completion_text = f"{completion_text} Output: {pending.terminal_output}"

            completed_content = [
                {
                    "type": "terminal",
                    "terminalId": terminal_id,
                },
                {
                    "type": "content",
                    "content": {
                        "type": "text",
                        "text": completion_text,
                    },
                },
            ]
            self._update_tool_call_status(
                session,
                pending.tool_call_id,
                "completed",
                content=completed_content,
            )
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": pending.tool_call_id,
                            "status": "completed",
                            "content": completed_content,
                            "rawOutput": {
                                "exitCode": pending.terminal_exit_code,
                            },
                        },
                    },
                )
            )
        else:
            return None

        session.active_turn.pending_client_request = None
        session.updated_at = datetime.now(UTC).isoformat()
        notifications.append(
            self._session_info_notification(
                session_id=session_id,
                title=None,
                updated_at=session.updated_at,
            )
        )
        completed = self._finalize_active_turn(session=session, stop_reason="end_turn")
        return ProtocolOutcome(
            notifications=notifications,
            followup_responses=[completed] if completed is not None else [],
        )

    def _find_session_by_pending_client_request_id(
        self,
        request_id: JsonRpcId,
    ) -> SessionState | None:
        """Ищет сессию по id ожидаемого agent->client запроса.

        Пример использования:
            session = protocol._find_session_by_pending_client_request_id("req_1")
        """

        for session in self._sessions.values():
            active_turn = session.active_turn
            if active_turn is None or active_turn.pending_client_request is None:
                continue
            if active_turn.pending_client_request.request_id == request_id:
                return session
        return None

    def _finalize_active_turn(
        self, session: SessionState, *, stop_reason: str
    ) -> ACPMessage | None:
        """Финализирует текущий active turn и очищает его состояние.

        Пример использования:
            response = protocol._finalize_active_turn(state, stop_reason="cancelled")
        """

        active_turn = session.active_turn
        if active_turn is None or active_turn.prompt_request_id is None:
            return None

        session.active_turn = None
        return ACPMessage.response(
            active_turn.prompt_request_id,
            {"stopReason": self._normalize_stop_reason(stop_reason)},
        )

    def _resolve_permission_response(
        self,
        permission_request_id: JsonRpcId,
        result: Any,
    ) -> ProtocolOutcome | None:
        """Применяет решение по permission-request к активному prompt-turn.

        Пример использования:
            outcome = protocol._resolve_permission_response(
                "perm_1",
                {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
            )
        """

        session = self._find_session_by_permission_request_id(permission_request_id)
        if session is None or session.active_turn is None:
            return None
        tool_call_id = session.active_turn.permission_tool_call_id
        if tool_call_id is None:
            return None

        session_id = session.session_id
        notifications: list[ACPMessage] = []
        outcome_value = self._extract_permission_outcome(result)
        selected_option = self._extract_permission_option_id(result)
        selected_option_id = selected_option if isinstance(selected_option, str) else None
        tool_call_state = session.tool_calls.get(tool_call_id)
        tool_kind = tool_call_state.kind if tool_call_state is not None else None
        if tool_kind is not None and selected_option_id in {"allow_always", "reject_always"}:
            # Сохраняем policy-решение для следующих tool-call этого же kind.
            session.permission_policy[tool_kind] = selected_option_id
        should_allow = outcome_value == "selected" and selected_option_id is not None
        if selected_option_id is not None:
            should_allow = should_allow and selected_option_id.startswith("allow")
        if not should_allow:
            notifications.extend(
                self._build_demo_tool_execution_updates(
                    session=session,
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    allowed=False,
                )
            )
            session.updated_at = datetime.now(UTC).isoformat()
            notifications.append(
                self._session_info_notification(
                    session_id=session_id,
                    title=None,
                    updated_at=session.updated_at,
                )
            )
            cancelled = self._finalize_active_turn(session=session, stop_reason="cancelled")
            return ProtocolOutcome(
                notifications=notifications,
                followup_responses=[cancelled] if cancelled is not None else [],
            )

        notifications.extend(
            self._build_demo_tool_execution_updates(
                session=session,
                session_id=session_id,
                tool_call_id=tool_call_id,
                allowed=True,
            )
        )

        session.updated_at = datetime.now(UTC).isoformat()
        notifications.append(
            self._session_info_notification(
                session_id=session_id,
                title=None,
                updated_at=session.updated_at,
            )
        )
        completed = self._finalize_active_turn(session=session, stop_reason="end_turn")
        return ProtocolOutcome(
            notifications=notifications,
            followup_responses=[completed] if completed is not None else [],
        )

    def _build_demo_tool_execution_updates(
        self,
        *,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        allowed: bool,
    ) -> list[ACPMessage]:
        """Строит lifecycle updates для локального tool execution после policy-решения.

        Пример использования:
            updates = protocol._build_demo_tool_execution_updates(
                session=state,
                session_id="sess_1",
                tool_call_id="call_1",
                allowed=True,
            )
        """

        if not allowed:
            self._update_tool_call_status(session, tool_call_id, "cancelled")
            return [
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": tool_call_id,
                            "status": "cancelled",
                        },
                    },
                )
            ]

        notifications: list[ACPMessage] = []
        self._update_tool_call_status(session, tool_call_id, "in_progress")
        notifications.append(
            ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "tool_call_update",
                        "toolCallId": tool_call_id,
                        "status": "in_progress",
                    },
                },
            )
        )
        completed_content = [
            {
                "type": "content",
                "content": {
                    "type": "text",
                    "text": "Tool completed successfully.",
                },
            }
        ]
        self._update_tool_call_status(
            session,
            tool_call_id,
            "completed",
            content=completed_content,
        )
        notifications.append(
            ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "tool_call_update",
                        "toolCallId": tool_call_id,
                        "status": "completed",
                        "content": completed_content,
                    },
                },
            )
        )
        return notifications

    def _parse_client_runtime_capabilities(
        self,
        capabilities: dict[str, Any],
    ) -> ClientRuntimeCapabilities:
        """Преобразует payload `clientCapabilities` в внутреннюю модель.

        Пример использования:
            caps = protocol._parse_client_runtime_capabilities(
                {"fs": {"readTextFile": True}, "terminal": False},
            )
        """

        fs_payload = capabilities.get("fs") if isinstance(capabilities, dict) else None
        read_text = False
        write_text = False
        if isinstance(fs_payload, dict):
            read_text = bool(fs_payload.get("readTextFile") is True)
            write_text = bool(fs_payload.get("writeTextFile") is True)

        terminal_enabled = bool(capabilities.get("terminal") is True)
        return ClientRuntimeCapabilities(
            fs_read=read_text,
            fs_write=write_text,
            terminal=terminal_enabled,
        )

    def _can_run_tool_runtime(self, session: SessionState) -> bool:
        """Проверяет, можно ли запускать tool-runtime ветки в текущем соединении.

        Пример использования:
            if protocol._can_run_tool_runtime():
                ...
        """

        caps = session.runtime_capabilities
        if caps is None:
            # До успешного initialize runtime-возможности не согласованы,
            # поэтому tool-runtime ветки должны оставаться выключенными.
            return False
        return caps.terminal or caps.fs_read or caps.fs_write

    def _can_use_fs_client_rpc(self, session: SessionState, kind: str) -> bool:
        """Проверяет доступность fs/* client RPC для указанной операции.

        Пример использования:
            enabled = protocol._can_use_fs_client_rpc("fs_read")
        """

        caps = session.runtime_capabilities
        if caps is None:
            return False
        if kind == "fs_read":
            return caps.fs_read
        if kind == "fs_write":
            return caps.fs_write
        return False

    def _can_use_terminal_client_rpc(self, session: SessionState) -> bool:
        """Проверяет доступность terminal/* client RPC в текущем runtime.

        Пример использования:
            enabled = protocol._can_use_terminal_client_rpc()
        """

        caps = session.runtime_capabilities
        if caps is None:
            return False
        return caps.terminal

    def _build_fs_client_request(
        self,
        *,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит исходящий fs/* request и связанный tool_call lifecycle.

        Пример использования:
            prepared = protocol._build_fs_client_request(
                session=state,
                session_id="sess_1",
                directives=directives,
            )
        """

        if directives.fs_read_path is not None:
            target_path = self._normalize_session_path(session.cwd, directives.fs_read_path)
            if target_path is None:
                return None
            tool_call_id = self._create_tool_call(
                session=session,
                title="Read text file",
                kind="read",
            )
            created = ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": tool_call_id,
                        "title": "Read text file",
                        "kind": "read",
                        "status": "pending",
                        "locations": [{"path": target_path}],
                    },
                },
            )
            fs_request = ACPMessage.request(
                "fs/read_text_file",
                {
                    "sessionId": session_id,
                    "path": target_path,
                },
            )
            if fs_request.id is None:
                return None
            pending = PendingClientRequestState(
                request_id=fs_request.id,
                kind="fs_read",
                tool_call_id=tool_call_id,
                path=target_path,
            )
            return PreparedFsClientRequest(
                kind="fs_read",
                messages=[created, fs_request],
                pending_request=pending,
            )

        if directives.fs_write_path is not None and directives.fs_write_content is not None:
            target_path = self._normalize_session_path(session.cwd, directives.fs_write_path)
            if target_path is None:
                return None
            tool_call_id = self._create_tool_call(
                session=session,
                title="Write text file",
                kind="edit",
            )
            created = ACPMessage.notification(
                "session/update",
                {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": tool_call_id,
                        "title": "Write text file",
                        "kind": "edit",
                        "status": "pending",
                        "locations": [{"path": target_path}],
                    },
                },
            )
            fs_request = ACPMessage.request(
                "fs/write_text_file",
                {
                    "sessionId": session_id,
                    "path": target_path,
                    "content": directives.fs_write_content,
                },
            )
            if fs_request.id is None:
                return None
            pending = PendingClientRequestState(
                request_id=fs_request.id,
                kind="fs_write",
                tool_call_id=tool_call_id,
                path=target_path,
                expected_new_text=directives.fs_write_content,
            )
            return PreparedFsClientRequest(
                kind="fs_write",
                messages=[created, fs_request],
                pending_request=pending,
            )

        return None

    def _build_terminal_client_request(
        self,
        *,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит исходящий terminal/create request и tool_call lifecycle.

        Возвращает структуру того же формата, что и fs-подготовка, чтобы
        использовать общий пайплайн pending client RPC.

        Пример использования:
            prepared = protocol._build_terminal_client_request(
                session=state,
                session_id="sess_1",
                directives=directives,
            )
        """

        if directives.terminal_command is None:
            return None

        tool_call_id = self._create_tool_call(
            session=session,
            title="Run terminal command",
            kind="execute",
        )
        created = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCallId": tool_call_id,
                    "title": "Run terminal command",
                    "kind": "execute",
                    "status": "pending",
                    "rawInput": {
                        "command": directives.terminal_command,
                    },
                },
            },
        )
        terminal_create_request = ACPMessage.request(
            "terminal/create",
            {
                "sessionId": session_id,
                "command": directives.terminal_command,
            },
        )
        if terminal_create_request.id is None:
            return None

        pending = PendingClientRequestState(
            request_id=terminal_create_request.id,
            kind="terminal_create",
            tool_call_id=tool_call_id,
            path=directives.terminal_command,
        )
        return PreparedFsClientRequest(
            kind="terminal_create",
            messages=[created, terminal_create_request],
            pending_request=pending,
        )

    def _normalize_session_path(self, cwd: str, candidate: str) -> str | None:
        """Преобразует путь из slash-команды в абсолютный путь в рамках cwd.

        Пример использования:
            path = protocol._normalize_session_path("/tmp", "README.md")
        """

        if not isinstance(candidate, str) or not candidate.strip():
            return None
        candidate_path = Path(candidate)
        if candidate_path.is_absolute():
            return str(candidate_path)
        return str(Path(cwd) / candidate_path)

    def _find_session_by_permission_request_id(
        self,
        permission_request_id: JsonRpcId,
    ) -> SessionState | None:
        """Ищет сессию с активным turn, ожидающим ответ по permission-request.

        Пример использования:
            session = protocol._find_session_by_permission_request_id("perm_1")
        """

        for session in self._sessions.values():
            active_turn = session.active_turn
            if active_turn is None:
                continue
            if active_turn.permission_request_id == permission_request_id:
                return session
        return None

    def _extract_permission_outcome(self, result: Any) -> str | None:
        """Извлекает outcome из `session/request_permission` response.

        Поддерживает текущий ACP shape (`{"outcome": {"outcome": ...}}`) и
        legacy-вариант (`{"outcome": ...}`) для обратной совместимости.

        Пример использования:
            outcome = protocol._extract_permission_outcome(
                {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
            )
        """

        if not isinstance(result, dict):
            return None

        nested_outcome = result.get("outcome")
        if isinstance(nested_outcome, dict):
            raw_value = nested_outcome.get("outcome")
            if isinstance(raw_value, str):
                return raw_value

        # Legacy fallback для старых клиентов.
        if isinstance(nested_outcome, str):
            return nested_outcome
        return None

    def _extract_permission_option_id(self, result: Any) -> str | None:
        """Извлекает `optionId` из `session/request_permission` response.

        Поддерживает ACP shape (`{"outcome": {"optionId": ...}}`) и legacy
        (`{"optionId": ...}`) формат для обратной совместимости.

        Пример использования:
            option_id = protocol._extract_permission_option_id(
                {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
            )
        """

        if not isinstance(result, dict):
            return None

        nested_outcome = result.get("outcome")
        if isinstance(nested_outcome, dict):
            raw_option_id = nested_outcome.get("optionId")
            if isinstance(raw_option_id, str):
                return raw_option_id

        raw_option_id = result.get("optionId")
        if isinstance(raw_option_id, str):
            return raw_option_id
        return None

    def _build_permission_options(self) -> list[dict[str, Any]]:
        """Возвращает варианты решения для `session/request_permission`.

        Пример использования:
            options = protocol._build_permission_options()
        """

        return [
            {
                "optionId": "allow_once",
                "name": "Allow once",
                "kind": "allow_once",
            },
            {
                "optionId": "allow_always",
                "name": "Always allow this tool",
                "kind": "allow_always",
            },
            {
                "optionId": "reject_once",
                "name": "Reject once",
                "kind": "reject_once",
            },
            {
                "optionId": "reject_always",
                "name": "Always reject this tool",
                "kind": "reject_always",
            },
        ]

    def _session_set_config_option(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
    ) -> ProtocolOutcome:
        """Изменяет значение конфигурационной опции сессии.

        В случае успеха возвращает новый snapshot `configOptions` и отправляет
        `config_option_update` + `session_info_update`.

        Пример использования:
            outcome = protocol._session_set_config_option(
                "req_1",
                {"sessionId": "sess_1", "configId": "mode", "value": "code"},
            )
        """

        # Конфиг опции валидируем по локальной спецификации и допустимым значениям.
        session_id = params.get("sessionId")
        config_id = params.get("configId")
        value = params.get("value")

        if not isinstance(session_id, str):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: sessionId is required",
                )
            )
        if not isinstance(config_id, str) or not isinstance(value, str):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: configId and value must be strings",
                )
            )

        session = self._sessions.get(session_id)
        if session is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32001,
                    message=f"Session not found: {session_id}",
                )
            )

        spec = self._config_specs.get(config_id)
        if spec is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message=f"Invalid params: unknown config option {config_id}",
                )
            )

        available_values = {
            str(option["value"])
            for option in spec["options"]
            if isinstance(option, dict) and isinstance(option.get("value"), str)
        }
        if value not in available_values:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message=f"Invalid params: unsupported value {value} for {config_id}",
                )
            )

        session.config_values[config_id] = value
        session.updated_at = datetime.now(UTC).isoformat()
        config_options = self._build_config_options(session.config_values)
        # Отправляем полный snapshot configOptions, чтобы клиент не делал merge вручную.
        config_notification = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "config_option_update",
                    "configOptions": config_options,
                },
            },
        )

        return ProtocolOutcome(
            response=ACPMessage.response(
                request_id,
                {
                    "configOptions": config_options,
                    "modes": self._build_modes_state(session.config_values),
                },
            ),
            notifications=self._build_config_update_notifications(
                session_id=session_id,
                config_id=config_id,
                session=session,
                config_notification=config_notification,
            ),
        )

    def _session_set_mode(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
    ) -> ProtocolOutcome:
        """Legacy-совместимый метод смены режима через `session/set_mode`.

        Пример использования:
            outcome = protocol._session_set_mode(
                "req_1",
                {"sessionId": "sess_1", "modeId": "code"},
            )
        """

        session_id = params.get("sessionId")
        mode_id = params.get("modeId")
        if not isinstance(session_id, str) or not isinstance(mode_id, str):
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: sessionId and modeId must be strings",
                )
            )

        mapped = self._session_set_config_option(
            request_id,
            {
                "sessionId": session_id,
                "configId": "mode",
                "value": mode_id,
            },
        )
        if mapped.response is None or mapped.response.error is not None:
            return mapped

        # По схеме `session/set_mode` возвращает пустой объект.
        return ProtocolOutcome(
            response=ACPMessage.response(request_id, {}),
            notifications=mapped.notifications,
        )

    def _build_config_update_notifications(
        self,
        *,
        session_id: str,
        config_id: str,
        session: SessionState,
        config_notification: ACPMessage,
    ) -> list[ACPMessage]:
        """Формирует набор notifications после обновления config option.

        Пример использования:
            notes = protocol._build_config_update_notifications(
                session_id="sess_1",
                config_id="mode",
                session=state,
                config_notification=cfg_note,
            )
        """

        notifications: list[ACPMessage] = [config_notification]
        if config_id == "mode":
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "current_mode_update",
                            "currentModeId": session.config_values.get("mode", "ask"),
                        },
                    },
                )
            )
        notifications.append(
            self._session_info_notification(
                session_id=session_id,
                title=None,
                updated_at=session.updated_at,
            )
        )
        return notifications

    def _build_config_options(self, values: dict[str, str]) -> list[dict[str, Any]]:
        """Строит wire-представление списка config options для клиента.

        Пример использования:
            options = protocol._build_config_options({"mode": "ask", "model": "baseline"})
        """

        options: list[dict[str, Any]] = []
        for config_id, spec in self._config_specs.items():
            options.append(
                {
                    "id": config_id,
                    "name": spec["name"],
                    "category": spec["category"],
                    "type": "select",
                    "currentValue": values.get(config_id, spec["default"]),
                    "options": spec["options"],
                }
            )
        return options

    def _validate_prompt_content(
        self,
        request_id: JsonRpcId | None,
        prompt: list[Any],
    ) -> ACPMessage | None:
        """Проверяет корректность ContentBlock-массива для `session/prompt`.

        Поддерживаются типы `text` и `resource_link`.
        При ошибке возвращается `ACPMessage.error_response`, иначе `None`.

        Пример использования:
            error = protocol._validate_prompt_content("req_1", [{"type": "text", "text": "hi"}])
        """

        for block in prompt:
            if not isinstance(block, dict):
                return ACPMessage.error_response(
                    request_id,
                    code=-32602,
                    message="Invalid params: each prompt item must be an object",
                )
            block_type = block.get("type")
            if block_type == "text":
                if not isinstance(block.get("text"), str):
                    return ACPMessage.error_response(
                        request_id,
                        code=-32602,
                        message="Invalid params: text content requires text string",
                    )
                continue
            if block_type == "resource_link":
                has_uri = isinstance(block.get("uri"), str)
                has_name = isinstance(block.get("name"), str)
                if not has_uri or not has_name:
                    return ACPMessage.error_response(
                        request_id,
                        code=-32602,
                        message="Invalid params: resource_link requires uri and name",
                    )
                continue
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message=f"Invalid params: unsupported content type {block_type}",
            )
        return None

    def _extract_prompt_directives(self, text_preview: str) -> PromptDirectives:
        """Извлекает служебные флаги turn из текстового preview prompt.

        Поддерживаются только slash-команды (`/plan`, `/tool`, `/tool-pending`
        и RPC-команды `/fs-read`, `/fs-write`, `/term-run`).

        Пример использования:
            directives = protocol._extract_prompt_directives("/tool /plan")
        """

        normalized_tokens = {
            token.strip().lower()
            for token in text_preview.replace("\n", " ").split(" ")
            if token.strip()
        }

        has_plan_directive = "/plan" in normalized_tokens
        has_tool_directive = "/tool" in normalized_tokens
        has_pending_directive = "/tool-pending" in normalized_tokens
        tool_kind = "other"
        fs_read_path: str | None = None
        fs_write_path: str | None = None
        fs_write_content: str | None = None
        terminal_command: str | None = None
        forced_stop_reason: str | None = None

        stripped_preview = text_preview.strip()
        if stripped_preview.startswith("/fs-read "):
            maybe_path = stripped_preview[len("/fs-read ") :].strip()
            if maybe_path:
                fs_read_path = maybe_path
        if stripped_preview.startswith("/fs-write "):
            raw_write_payload = stripped_preview[len("/fs-write ") :].strip()
            path_and_content = raw_write_payload.split(" ", 1)
            if len(path_and_content) == 2:
                candidate_path = path_and_content[0].strip()
                candidate_content = path_and_content[1]
                if candidate_path:
                    fs_write_path = candidate_path
                    fs_write_content = candidate_content
        if stripped_preview.startswith("/term-run "):
            raw_command = stripped_preview[len("/term-run ") :].strip()
            if raw_command:
                terminal_command = raw_command
        if stripped_preview.startswith("/stop-max-tokens"):
            forced_stop_reason = "max_tokens"
        if stripped_preview.startswith("/stop-max-turn-requests"):
            forced_stop_reason = "max_turn_requests"
        if stripped_preview.startswith("/refuse"):
            forced_stop_reason = "refusal"

        # Поддерживаем опциональный kind в `/tool <kind> ...` и
        # `/tool-pending <kind> ...` для policy-scope beyond `other`.
        if stripped_preview.startswith("/tool "):
            candidate = stripped_preview[len("/tool ") :].split(" ", 1)[0].strip().lower()
            if candidate == "write":
                candidate = "edit"
            if candidate in {"other", "read", "edit", "execute", "search"}:
                tool_kind = candidate
        if stripped_preview.startswith("/tool-pending "):
            candidate = stripped_preview[len("/tool-pending ") :].split(" ", 1)[0].strip().lower()
            if candidate == "write":
                candidate = "edit"
            if candidate in {"other", "read", "edit", "execute", "search"}:
                tool_kind = candidate

        return PromptDirectives(
            request_tool=has_tool_directive or has_pending_directive,
            keep_tool_pending=has_pending_directive,
            publish_plan=has_plan_directive,
            tool_kind=tool_kind,
            fs_read_path=fs_read_path,
            fs_write_path=fs_write_path,
            fs_write_content=fs_write_content,
            terminal_command=terminal_command,
            forced_stop_reason=forced_stop_reason,
        )

    def _resolve_prompt_stop_reason(self, directives: PromptDirectives) -> str:
        """Возвращает stopReason для текущего prompt-turn.

        Пример использования:
            reason = protocol._resolve_prompt_stop_reason(directives)
        """

        if directives.forced_stop_reason is not None:
            return self._normalize_stop_reason(directives.forced_stop_reason)
        return "end_turn"

    def _normalize_stop_reason(self, stop_reason: str) -> str:
        """Нормализует stopReason к поддерживаемому значению ACP.

        Пример использования:
            reason = protocol._normalize_stop_reason("max_tokens")
        """

        if stop_reason in self._supported_stop_reasons:
            return stop_reason
        return "end_turn"

    def _resolve_demo_tool_title(self, kind: str) -> str:
        """Возвращает человекочитаемый title для demo tool-call по kind.

        Пример использования:
            title = protocol._resolve_demo_tool_title("execute")
        """

        titles = {
            "read": "Tool read operation",
            "edit": "Tool edit operation",
            "execute": "Tool execution",
            "search": "Tool search operation",
            "other": "Tool operation",
        }
        return titles.get(kind, "Tool operation")

    def _build_tool_call_updates(
        self,
        *,
        session: SessionState,
        session_id: str,
        prompt_requests_tool: bool,
        leave_running: bool,
        tool_kind: str,
    ) -> list[ACPMessage]:
        """Генерирует demo-последовательность `tool_call`/`tool_call_update`.

        Включается явными флагами, вычисленными на этапе анализа prompt.
        Нужен как каркас для протокольной совместимости и тестов.

        Пример использования:
            updates = protocol._build_tool_call_updates(
                session=state,
                session_id="sess_1",
                prompt_requests_tool=True,
                leave_running=False,
            )
        """

        # Если turn не требует вызова инструмента, update-события не генерируем.
        if not prompt_requests_tool:
            return []

        tool_call_id = self._create_tool_call(
            session=session,
            title=self._resolve_demo_tool_title(tool_kind),
            kind=tool_kind,
        )

        created = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCallId": tool_call_id,
                    "title": self._resolve_demo_tool_title(tool_kind),
                    "kind": tool_kind,
                    "status": "pending",
                },
            },
        )

        in_progress = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": tool_call_id,
                    "status": "in_progress",
                },
            },
        )
        self._update_tool_call_status(session, tool_call_id, "in_progress")

        if leave_running:
            return [created, in_progress]

        completed_content = [
            {
                "type": "content",
                "content": {
                    "type": "text",
                    "text": "Demo tool completed successfully.",
                },
            }
        ]
        self._update_tool_call_status(
            session,
            tool_call_id,
            "completed",
            content=completed_content,
        )
        completed = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": tool_call_id,
                    "status": "completed",
                    "content": completed_content,
                },
            },
        )
        return [created, in_progress, completed]

    def _create_tool_call(self, session: SessionState, *, title: str, kind: str) -> str:
        """Создает запись нового tool call в состоянии сессии.

        Пример использования:
            tool_call_id = protocol._create_tool_call(state, title="Demo", kind="other")
        """

        # Локально монотонный ID делает тесты предсказуемыми и читабельными.
        session.tool_call_counter += 1
        tool_call_id = f"call_{session.tool_call_counter:03d}"
        session.tool_calls[tool_call_id] = ToolCallState(
            tool_call_id=tool_call_id,
            title=title,
            kind=kind,
            status="pending",
        )
        return tool_call_id

    def _update_tool_call_status(
        self,
        session: SessionState,
        tool_call_id: str,
        status: str,
        *,
        content: list[dict[str, Any]] | None = None,
    ) -> None:
        """Обновляет статус tool call с проверкой допустимых переходов.

        Пример использования:
            protocol._update_tool_call_status(state, "call_001", "in_progress")
        """

        state = session.tool_calls.get(tool_call_id)
        if state is None:
            return

        # Явная матрица переходов защищает от нелегальных смен статуса.
        allowed_transitions: dict[str, set[str]] = {
            "pending": {"in_progress", "cancelled", "failed"},
            "in_progress": {"completed", "cancelled", "failed"},
            "completed": set(),
            "cancelled": set(),
            "failed": set(),
        }
        next_states = allowed_transitions.get(state.status, set())
        if status not in next_states and status != state.status:
            return

        state.status = status
        if content is not None:
            state.content = content

    def _cancel_active_tool_calls(self, session: SessionState, session_id: str) -> list[ACPMessage]:
        """Отменяет все незавершенные tool calls и формирует update-события.

        Пример использования:
            updates = protocol._cancel_active_tool_calls(state, "sess_1")
        """

        # Финальные статусы не трогаем, отменяем только активные вызовы.
        notifications: list[ACPMessage] = []
        for tool_call in session.tool_calls.values():
            if tool_call.status not in {"pending", "in_progress"}:
                continue
            self._update_tool_call_status(session, tool_call.tool_call_id, "cancelled")
            notifications.append(
                ACPMessage.notification(
                    "session/update",
                    {
                        "sessionId": session_id,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": tool_call.tool_call_id,
                            "status": "cancelled",
                        },
                    },
                )
            )
        return notifications

    def _session_info_notification(
        self,
        *,
        session_id: str,
        title: str | None,
        updated_at: str,
    ) -> ACPMessage:
        """Создает notification `session_info_update` для `session/update`.

        Пример использования:
            note = protocol._session_info_notification(
                session_id="sess_1",
                title="My session",
                updated_at="2026-04-07T00:00:00Z",
            )
        """

        return ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "session_info_update",
                    "title": title,
                    "updatedAt": updated_at,
                },
            },
        )

    def _build_default_commands(self) -> list[dict[str, Any]]:
        """Возвращает базовый набор команд для demo-сессий.

        Пример использования:
            commands = protocol._build_default_commands()
        """

        # Базовый список slash-команд для демонстрации протокольного update.
        return [
            {
                "name": "status",
                "description": "Показать состояние текущей сессии",
            },
            {
                "name": "mode",
                "description": "Показать и изменить режим сессии",
            },
        ]
