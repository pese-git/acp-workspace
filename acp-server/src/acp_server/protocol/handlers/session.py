"""Обработчики методов управления сессиями.

Содержит логику обработки session/new, session/load, session/list.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from ...messages import ACPMessage, JsonRpcId
from ..session_factory import SessionFactory
from ..state import ClientRuntimeCapabilities, ProtocolOutcome, SessionState


def _serialize_available_commands(
    commands: list,
) -> list[dict[str, Any]]:
    """Сериализует список available_commands для JSON.
    
    Преобразует Pydantic модели в dict для JSON сериализации.
    """
    result: list[dict[str, Any]] = []
    for cmd in commands:
        if isinstance(cmd, dict):
            result.append(cmd)
        elif hasattr(cmd, "model_dump"):
            result.append(cmd.model_dump(exclude_none=False))
        else:
            result.append(cmd)
    return result


def session_new(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    require_auth: bool,
    authenticated: bool,
    config_specs: dict[str, dict[str, Any]],
    auth_methods: list[dict[str, Any]],
    runtime_capabilities: ClientRuntimeCapabilities | None,
) -> ACPMessage:
    """Создает новую in-memory сессию и возвращает ее идентификатор.

    Метод валидирует `cwd`, инициализирует config options и дефолтные
    slash-команды.

    Пример использования:
        response = session_new(
            "req_1", {"cwd": "/tmp", "mcpServers": []}, False, True, {}, [], None
        )
    """

    if require_auth and not authenticated:
        return ACPMessage.error_response(
            request_id,
            code=-32010,
            message="auth_required",
            data={"authMethods": auth_methods},
        )

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

    # Создаем сессию через фабрику
    config_values = {
        config_id: str(spec["default"]) for config_id, spec in config_specs.items()
    }

    session_state = SessionFactory.create_session(
        cwd=cwd,
        mcp_servers=mcp_servers,
        config_values=config_values,
        available_commands=build_default_commands(),
        runtime_capabilities=runtime_capabilities,
    )

    return ACPMessage.response(
        request_id,
        {
            "sessionId": session_state.session_id,
            "configOptions": build_config_options(config_values, config_specs),
            "modes": build_modes_state(config_values, config_specs),
        },
    )


def session_load(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    require_auth: bool,
    authenticated: bool,
    config_specs: dict[str, dict[str, Any]],
    auth_methods: list[dict[str, Any]],
    sessions: dict[str, SessionState],
) -> ProtocolOutcome:
    """Загружает существующую сессию и реплеит состояние через updates.

    Возвращает `result: null` и набор `session/update` уведомлений:
    история сообщений, config options, команды и session info.

    Пример использования:
        outcome = session_load(
            "req_1",
            {"sessionId": "sess_1", "cwd": "/tmp", "mcpServers": []},
            False,
            True,
            {},
            [],
            {},
        )
    """

    if require_auth and not authenticated:
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32010,
                message="auth_required",
                data={"authMethods": auth_methods},
            )
        )

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

    session = sessions.get(session_id)
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
                    "configOptions": build_config_options(session.config_values, config_specs),
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
                    "availableCommands": _serialize_available_commands(
                        session.available_commands
                    ),
                },
            },
        )
    )
    notifications.append(
        session_info_notification(
            session_id=session_id,
            title=session.title,
            updated_at=session.updated_at,
        )
    )

    return ProtocolOutcome(
        response=ACPMessage.response(
            request_id,
            {
                "configOptions": build_config_options(session.config_values, config_specs),
                "modes": build_modes_state(session.config_values, config_specs),
            },
        ),
        notifications=notifications,
    )


def session_list(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    sessions: dict[str, SessionState],
    session_list_page_size: int = 50,
) -> ACPMessage:
    """Возвращает список сессий с опциональной фильтрацией по `cwd`.

    Пример использования:
        response = session_list("req_1", {"cwd": "/tmp"}, {})
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
        decoded = decode_session_cursor(cursor)
        if decoded is None:
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: cursor is invalid",
            )
        start_index = decoded

    sessions_list: list[dict[str, Any]] = []
    for session in sessions.values():
        if isinstance(cwd_filter, str) and session.cwd != cwd_filter:
            continue
        sessions_list.append(
            {
                "sessionId": session.session_id,
                "cwd": session.cwd,
                "title": session.title,
                "updatedAt": session.updated_at,
            }
        )

    sorted_sessions = sorted(
        sessions_list, key=lambda item: str(item.get("updatedAt") or ""), reverse=True
    )
    page_end = start_index + session_list_page_size
    page = sorted_sessions[start_index:page_end]
    next_cursor: str | None = None
    if page_end < len(sorted_sessions):
        next_cursor = encode_session_cursor(page_end)

    return ACPMessage.response(request_id, {"sessions": page, "nextCursor": next_cursor})


def encode_session_cursor(index: int) -> str:
    """Кодирует индекс страницы в opaque cursor для `session/list`.

    Пример использования:
        cursor = encode_session_cursor(50)
    """

    payload = json.dumps({"index": index}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_session_cursor(cursor: str) -> int | None:
    """Декодирует opaque cursor `session/list` в индекс начала страницы.

    Возвращает `None`, если cursor поврежден или невалиден.

    Пример использования:
        index = decode_session_cursor(cursor)
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


def build_modes_state(
    values: dict[str, str],
    config_specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Строит legacy-состояние modes для совместимых клиентов ACP.

    Пример использования:
        modes = build_modes_state({"mode": "ask", "model": "baseline"}, specs)
    """

    mode_option = config_specs.get("mode", {})
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


def build_config_options(
    values: dict[str, str],
    config_specs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Строит wire-представление списка config options для клиента.

    Пример использования:
        options = build_config_options({"mode": "ask", "model": "baseline"}, specs)
    """

    options: list[dict[str, Any]] = []
    for config_id, spec in config_specs.items():
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


def session_info_notification(
    *,
    session_id: str,
    title: str | None,
    updated_at: str,
) -> ACPMessage:
    """Создает notification `session_info_update` для `session/update`.

    Пример использования:
        note = session_info_notification(
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


def build_default_commands() -> list[dict[str, Any]]:
    """Возвращает базовый набор команд для demo-сессий.

    Пример использования:
        commands = build_default_commands()
    """

    # Базовый список slash-команд для демонстрации протокольного update.
    # Возвращаем list[dict[str, Any]] которая совместима с list[AvailableCommand | dict[str, Any]]
    return [
        {
            "name": "status",
            "description": "Показать состояние текущей сессии",
        },
        {
            "name": "mode",
            "description": "Показать и изменить режим сессии",
        },
    ]  # type: ignore[return-value]
