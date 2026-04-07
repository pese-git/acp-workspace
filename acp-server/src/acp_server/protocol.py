from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .messages import ACPMessage, JsonRpcId


@dataclass(slots=True)
class SessionState:
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
    # Кооперативная отмена текущего prompt-turn.
    cancelled: bool = False
    # Локальный счетчик для стабильной генерации toolCallId.
    tool_call_counter: int = 0
    # Реестр созданных tool calls и их состояний.
    tool_calls: dict[str, ToolCallState] = field(default_factory=dict)
    # Набор доступных slash-команд для `available_commands_update`.
    available_commands: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ToolCallState:
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
class ProtocolOutcome:
    response: ACPMessage | None = None
    notifications: list[ACPMessage] = field(default_factory=list)


class ACPProtocol:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

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

    def handle(self, message: ACPMessage) -> ProtocolOutcome:
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
            return ProtocolOutcome(response=self._initialize(message.id))
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

    def _initialize(self, request_id: JsonRpcId | None) -> ACPMessage:
        # Инициализация capability negotiation для ACP v1.
        result = {
            "protocolVersion": 1,
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
            "authMethods": [],
        }
        result["agentCapabilities"]["sessionCapabilities"] = {
            "list": {},
        }
        return ACPMessage.response(request_id, result)

    def _session_new(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
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
        )
        return ACPMessage.response(
            request_id,
            {
                "sessionId": session_id,
                "configOptions": self._build_config_options(config_values),
            },
        )

    def _session_load(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
    ) -> ProtocolOutcome:
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
            response=ACPMessage.response(request_id, None),
            notifications=notifications,
        )

    def _session_list(self, request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
        # Поддерживаем фильтрацию сессий по cwd для клиентских списков.
        cwd_filter = params.get("cwd")
        if cwd_filter is not None and (
            not isinstance(cwd_filter, str) or not Path(cwd_filter).is_absolute()
        ):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: cwd must be an absolute path",
            )

        sessions = []
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

        return ACPMessage.response(request_id, {"sessions": sessions})

    def _session_prompt(
        self, request_id: JsonRpcId | None, params: dict[str, Any]
    ) -> ProtocolOutcome:
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

        if session.cancelled:
            session.cancelled = False
            return ProtocolOutcome(
                response=ACPMessage.response(request_id, {"stopReason": "cancelled"})
            )

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

        # Демонстрационный tool-call lifecycle для совместимости с ACP-клиентами.
        tool_notifications = self._build_tool_call_updates(
            session=session,
            session_id=session_id,
            prompt_text=text_preview,
        )
        notifications.extend(tool_notifications)

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

        return ProtocolOutcome(
            response=ACPMessage.response(request_id, {"stopReason": "end_turn"}),
            notifications=notifications,
        )

    def _session_cancel(
        self, request_id: JsonRpcId | None, params: dict[str, Any]
    ) -> ProtocolOutcome:
        session_id = params.get("sessionId")
        notifications: list[ACPMessage] = []
        if isinstance(session_id, str) and session_id in self._sessions:
            session = self._sessions[session_id]
            session.cancelled = True
            # При отмене переводим все незавершенные tool calls в `cancelled`.
            notifications = self._cancel_active_tool_calls(session=session, session_id=session_id)
            session.updated_at = datetime.now(UTC).isoformat()
            notifications.append(
                self._session_info_notification(
                    session_id=session_id,
                    title=None,
                    updated_at=session.updated_at,
                )
            )

        if request_id is None:
            return ProtocolOutcome(response=None, notifications=notifications)

        return ProtocolOutcome(
            response=ACPMessage.response(request_id, None),
            notifications=notifications,
        )

    def _session_set_config_option(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
    ) -> ProtocolOutcome:
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
                {"configOptions": config_options},
            ),
            notifications=[
                config_notification,
                self._session_info_notification(
                    session_id=session_id,
                    title=None,
                    updated_at=session.updated_at,
                ),
            ],
        )

    def _build_config_options(self, values: dict[str, str]) -> list[dict[str, Any]]:
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

    def _build_tool_call_updates(
        self,
        *,
        session: SessionState,
        session_id: str,
        prompt_text: str,
    ) -> list[ACPMessage]:
        # Демо-режим: tool-call генерируется только по явному маркеру в тексте.
        if "[tool]" not in prompt_text:
            return []

        tool_call_id = self._create_tool_call(
            session=session,
            title="Demo tool execution",
            kind="other",
        )

        created = ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call",
                    "toolCallId": tool_call_id,
                    "title": "Demo tool execution",
                    "kind": "other",
                    "status": "pending",
                },
            },
        )

        # Маркер нужен для тестирования ветки отмены незавершенного tool call.
        should_leave_running = "[tool-pending]" in prompt_text

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

        if should_leave_running:
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
