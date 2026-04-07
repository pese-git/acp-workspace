from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from aiohttp import ClientSession, WSMsgType

from .messages import (
    ACPMessage,
    InitializeResult,
    JsonRpcError,
    PlanUpdate,
    SessionListItem,
    SessionListResult,
    SessionSetupResult,
    SessionUpdateNotification,
    StructuredSessionUpdate,
    ToolCallUpdate,
    parse_initialize_result,
    parse_plan_update,
    parse_request_permission_request,
    parse_session_list_result,
    parse_session_setup_result,
    parse_session_update_notification,
    parse_structured_session_update,
    parse_tool_call_update,
)

type PermissionHandler = Callable[[dict[str, Any]], str | None]
type FsReadHandler = Callable[[str], str]
type FsWriteHandler = Callable[[str, str], str | None]
type TerminalCreateHandler = Callable[[str], str]
type TerminalOutputHandler = Callable[[str], str]
type TerminalWaitHandler = Callable[[str], int]
type TerminalReleaseHandler = Callable[[str], None]
type TerminalKillHandler = Callable[[str], bool]


class ACPClient:
    """Асинхронный ACP-клиент с поддержкой HTTP и WebSocket транспорта.

    Класс предоставляет:
    - универсальный метод `request`,
    - helper для `session/load` и replay-обновлений,
    - типизированный helper `load_session_parsed`.

    Пример использования:
        client = ACPClient(host="127.0.0.1", port=8080)
        response = await client.request("initialize", transport="http")
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        """Создает клиент с адресом ACP-сервера.

        Пример использования:
            client = ACPClient(host="127.0.0.1", port=8080)
        """

        self.host = host
        self.port = port

    @staticmethod
    def _default_client_capabilities() -> dict[str, Any]:
        """Возвращает baseline-capabilities клиента для `initialize`.

        Базовые значения соответствуют схеме ACP и явно сигнализируют агенту,
        что клиент пока не поддерживает FS/terminal RPC-методы.

        Пример использования:
            caps = ACPClient._default_client_capabilities()
        """

        return {
            "fs": {
                "readTextFile": False,
                "writeTextFile": False,
            },
            "terminal": False,
        }

    async def request(
        self,
        method: str,
        params: dict | None = None,
        transport: Literal["http", "ws"] = "http",
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> ACPMessage:
        """Выполняет ACP-запрос через выбранный транспорт.

        Для WS может принимать `on_update`, который вызывается на каждый
        `session/update` до финального response. Также может принимать
        `on_permission` для обработки `session/request_permission`.

        Пример использования:
            await client.request("session/list", transport="http")
        """

        if transport == "http":
            return await self._request_http(method=method, params=params)
        return await self._request_ws(
            method=method,
            params=params,
            on_update=on_update,
            on_permission=on_permission,
            on_fs_read=on_fs_read,
            on_fs_write=on_fs_write,
            on_terminal_create=on_terminal_create,
            on_terminal_output=on_terminal_output,
            on_terminal_wait_for_exit=on_terminal_wait_for_exit,
            on_terminal_release=on_terminal_release,
            on_terminal_kill=on_terminal_kill,
        )

    async def initialize(
        self,
        *,
        protocol_version: int = 1,
        client_capabilities: dict[str, Any] | None = None,
        client_info: dict[str, Any] | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> InitializeResult:
        """Выполняет `initialize` и возвращает типизированный negotiated result.

        Пример использования:
            result = await client.initialize(transport="ws")
        """

        params: dict[str, Any] = {
            "protocolVersion": protocol_version,
            "clientCapabilities": client_capabilities or self._default_client_capabilities(),
        }
        if client_info is not None:
            params["clientInfo"] = client_info

        response = await self.request(
            method="initialize",
            params=params,
            transport=transport,
        )
        return parse_initialize_result(response)

    async def _request_http(self, method: str, params: dict | None = None) -> ACPMessage:
        """Отправляет одиночный JSON-RPC request через HTTP endpoint `/acp`.

        Пример использования:
            response = await client._request_http("ping", {})
        """

        request = ACPMessage.request(method=method, params=params)
        url = f"http://{self.host}:{self.port}/acp"

        async with (
            ClientSession() as session,
            session.post(url, json=request.to_dict()) as response,
        ):
            payload = await response.json()
            return ACPMessage.from_dict(payload)

    async def _request_ws(
        self,
        method: str,
        params: dict | None = None,
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> ACPMessage:
        """Отправляет request через WebSocket и слушает updates до финала.

        Метод возвращает только финальный JSON-RPC response. Промежуточные
        `session/update` события передаются в callback `on_update`.

        Пример использования:
            await client._request_ws("session/prompt", params, updates.append)
        """

        request = ACPMessage.request(method=method, params=params)
        url = f"ws://{self.host}:{self.port}/acp/ws"
        should_initialize = method.startswith("session/") and method != "initialize"

        async with ClientSession() as session, session.ws_connect(url) as ws:
            if should_initialize:
                await self._perform_ws_initialize(ws)
            await ws.send_str(request.to_json())

            while True:
                message = await ws.receive()

                if message.type != WSMsgType.TEXT:
                    msg = f"Unexpected WebSocket response type: {message.type}"
                    raise RuntimeError(msg)

                payload = json.loads(message.data)
                raw_method = payload.get("method")
                if raw_method == "session/update":
                    # Промежуточные обновления отдаем в callback.
                    # Финальный JSON-RPC response продолжаем ждать дальше.
                    if on_update is not None:
                        on_update(payload)
                    continue

                permission_request = None
                if isinstance(payload, dict):
                    permission_request = parse_request_permission_request(payload)
                if permission_request is not None:
                    permission_result = self._build_permission_result(
                        payload=payload,
                        on_permission=on_permission,
                    )
                    await ws.send_str(
                        ACPMessage.response(permission_request.id, permission_result).to_json()
                    )
                    continue

                handled_fs_request = self._handle_server_fs_request(
                    payload=payload,
                    on_fs_read=on_fs_read,
                    on_fs_write=on_fs_write,
                )
                if handled_fs_request is not None:
                    await ws.send_str(handled_fs_request.to_json())
                    continue

                handled_terminal_request = self._handle_server_terminal_request(
                    payload=payload,
                    on_terminal_create=on_terminal_create,
                    on_terminal_output=on_terminal_output,
                    on_terminal_wait_for_exit=on_terminal_wait_for_exit,
                    on_terminal_release=on_terminal_release,
                    on_terminal_kill=on_terminal_kill,
                )
                if handled_terminal_request is not None:
                    await ws.send_str(handled_terminal_request.to_json())
                    continue

                response = ACPMessage.from_dict(payload)
                return response

    def _handle_server_fs_request(
        self,
        *,
        payload: dict[str, Any],
        on_fs_read: FsReadHandler | None,
        on_fs_write: FsWriteHandler | None,
    ) -> ACPMessage | None:
        """Обрабатывает server-originated `fs/*` запрос и строит response.

        Пример использования:
            response = client._handle_server_fs_request(payload=data, ...)
        """

        method = payload.get("method")
        request_id = payload.get("id")
        params = payload.get("params")

        if method == "fs/read_text_file":
            if on_fs_read is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support fs/read_text_file",
                    ),
                )
            path = params.get("path") if isinstance(params, dict) else None
            if not isinstance(path, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: path must be a string",
                    ),
                )
            return ACPMessage.response(request_id, {"content": on_fs_read(path)})

        if method == "fs/write_text_file":
            if on_fs_write is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support fs/write_text_file",
                    ),
                )
            path = params.get("path") if isinstance(params, dict) else None
            content = params.get("content") if isinstance(params, dict) else None
            if not isinstance(path, str) or not isinstance(content, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: path and content must be strings",
                    ),
                )
            old_text = on_fs_write(path, content)
            return ACPMessage.response(
                request_id,
                {
                    "ok": True,
                    "oldText": old_text,
                    "newText": content,
                },
            )

        return None

    def _handle_server_terminal_request(
        self,
        *,
        payload: dict[str, Any],
        on_terminal_create: TerminalCreateHandler | None,
        on_terminal_output: TerminalOutputHandler | None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None,
        on_terminal_release: TerminalReleaseHandler | None,
        on_terminal_kill: TerminalKillHandler | None,
    ) -> ACPMessage | None:
        """Обрабатывает server-originated `terminal/*` запрос и строит response.

        Пример использования:
            response = client._handle_server_terminal_request(payload=data, ...)
        """

        method = payload.get("method")
        request_id = payload.get("id")
        raw_params = payload.get("params")
        params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}

        if method == "terminal/create":
            if on_terminal_create is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support terminal/create",
                    ),
                )
            command = params.get("command")
            if not isinstance(command, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: command must be a string",
                    ),
                )
            return ACPMessage.response(request_id, {"terminalId": on_terminal_create(command)})

        if method == "terminal/output":
            if on_terminal_output is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support terminal/output",
                    ),
                )
            terminal_id = params.get("terminalId")
            if not isinstance(terminal_id, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: terminalId must be a string",
                    ),
                )
            return ACPMessage.response(request_id, {"output": on_terminal_output(terminal_id)})

        if method == "terminal/wait_for_exit":
            if on_terminal_wait_for_exit is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support terminal/wait_for_exit",
                    ),
                )
            terminal_id = params.get("terminalId")
            if not isinstance(terminal_id, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: terminalId must be a string",
                    ),
                )
            return ACPMessage.response(
                request_id,
                {"exitCode": on_terminal_wait_for_exit(terminal_id)},
            )

        if method == "terminal/release":
            if on_terminal_release is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support terminal/release",
                    ),
                )
            terminal_id = params.get("terminalId")
            if not isinstance(terminal_id, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: terminalId must be a string",
                    ),
                )
            on_terminal_release(terminal_id)
            return ACPMessage.response(request_id, {"ok": True})

        if method == "terminal/kill":
            if on_terminal_kill is None:
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32601,
                        message="Client does not support terminal/kill",
                    ),
                )
            terminal_id = params.get("terminalId")
            if not isinstance(terminal_id, str):
                return ACPMessage(
                    id=request_id,
                    error=JsonRpcError(
                        code=-32602,
                        message="Invalid params: terminalId must be a string",
                    ),
                )
            return ACPMessage.response(request_id, {"killed": on_terminal_kill(terminal_id)})

        return None

    async def _perform_ws_initialize(self, ws: Any) -> None:
        """Выполняет ACP initialize в открытом WS-соединении.

        Метод нужен для соблюдения handshake-фазы протокола перед вызовом
        `session/*` методов в рамках того же WS-канала.

        Пример использования:
            await client._perform_ws_initialize(ws)
        """

        init_request = ACPMessage.request(
            method="initialize",
            params={
                "protocolVersion": 1,
                "clientCapabilities": self._default_client_capabilities(),
            },
        )
        await ws.send_str(init_request.to_json())

        while True:
            message = await ws.receive()
            if message.type != WSMsgType.TEXT:
                msg = f"Unexpected WebSocket response type during initialize: {message.type}"
                raise RuntimeError(msg)

            payload = json.loads(message.data)
            raw_method = payload.get("method") if isinstance(payload, dict) else None
            if raw_method == "session/update":
                # Инициализация не должна блокироваться на update-событиях.
                continue
            response = ACPMessage.from_dict(payload)
            if response.id != init_request.id:
                continue
            if response.error is not None:
                msg = f"WebSocket initialize failed: {response.error.code} {response.error.message}"
                raise RuntimeError(msg)
            return

    def _build_permission_result(
        self,
        *,
        payload: dict[str, Any],
        on_permission: PermissionHandler | None,
    ) -> dict[str, Any]:
        """Формирует результат `session/request_permission` для ответа агенту.

        Если callback не передан или вернул `None`, возвращается `cancelled`.

        Пример использования:
            result = client._build_permission_result(payload=data, on_permission=None)
        """

        selected_option_id = on_permission(payload) if on_permission is not None else None
        if selected_option_id is None:
            return {
                "outcome": {
                    "outcome": "cancelled",
                }
            }
        return {
            "outcome": {
                "outcome": "selected",
                "optionId": selected_option_id,
            }
        }

    async def load_session(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[dict[str, Any]]]:
        """Выполняет `session/load` и возвращает response вместе с raw updates.

        Helper упрощает сценарий восстановления контекста: клиент получает
        финальный ответ и весь replay update-поток в одном вызове.

        Пример использования:
            response, updates = await client.load_session(
                session_id="sess_1",
                cwd="/tmp",
                transport="ws",
            )
        """

        updates: list[dict[str, Any]] = []
        params = {
            "sessionId": session_id,
            "cwd": cwd,
            "mcpServers": mcp_servers or [],
        }
        response = await self.request(
            method="session/load",
            params=params,
            transport=transport,
            on_update=updates.append,
        )
        return response, updates

    async def load_session_parsed(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[SessionUpdateNotification]]:
        """Выполняет `session/load` и возвращает типизированные update-события.

        В отличие от `load_session`, этот метод фильтрует и валидирует только
        корректные notifications `session/update`.

        Пример использования:
            response, updates = await client.load_session_parsed(
                session_id="sess_1",
                cwd="/tmp",
                transport="ws",
            )
        """

        raw_response, raw_updates = await self.load_session(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
            transport=transport,
        )

        parsed_updates: list[SessionUpdateNotification] = []
        for raw_update in raw_updates:
            if not isinstance(raw_update, dict):
                continue
            parsed = parse_session_update_notification(raw_update)
            if parsed is None:
                continue
            parsed_updates.append(parsed)

        return raw_response, parsed_updates

    async def load_session_tool_updates(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[ToolCallUpdate]]:
        """Выполняет `session/load` и выделяет только tool-call update-события.

        Метод удобен для UI/логики, которым важны только статусы инструментов,
        без разбора остальных событий `session/update`.

        Пример использования:
            response, tool_updates = await client.load_session_tool_updates(
                session_id="sess_1",
                cwd="/tmp",
                transport="ws",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
            transport=transport,
        )
        tool_updates: list[ToolCallUpdate] = []
        for update in updates:
            parsed = parse_tool_call_update(update)
            if parsed is None:
                continue
            tool_updates.append(parsed)
        return response, tool_updates

    async def load_session_plan_updates(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[PlanUpdate]]:
        """Выполняет `session/load` и выделяет только plan update-события.

        Метод полезен клиентам, которые показывают пользователю только текущий
        план выполнения без остальных `session/update` событий.

        Пример использования:
            response, plans = await client.load_session_plan_updates(
                session_id="sess_1",
                cwd="/tmp",
                transport="ws",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
            transport=transport,
        )
        plan_updates: list[PlanUpdate] = []
        for update in updates:
            parsed = parse_plan_update(update)
            if parsed is None:
                continue
            plan_updates.append(parsed)
        return response, plan_updates

    async def list_sessions(
        self,
        *,
        cwd: str | None = None,
        cursor: str | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> ACPMessage:
        """Запрашивает одну страницу `session/list` с optional фильтрами.

        Пример использования:
            response = await client.list_sessions(cwd="/tmp", transport="http")
        """

        params: dict[str, Any] = {}
        if cwd is not None:
            params["cwd"] = cwd
        if cursor is not None:
            params["cursor"] = cursor
        return await self.request(method="session/list", params=params, transport=transport)

    async def list_all_sessions(
        self,
        *,
        cwd: str | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> list[dict[str, Any]]:
        """Возвращает все сессии, последовательно проходя cursor-пагинацию.

        Если сервер вернет невалидный формат ответа, метод аварийно завершится
        исключением `RuntimeError`, чтобы клиент явно увидел нарушение контракта.

        Пример использования:
            sessions = await client.list_all_sessions(cwd="/tmp", transport="http")
        """

        collected: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = await self.list_sessions(cwd=cwd, cursor=cursor, transport=transport)
            if not isinstance(response.result, dict):
                msg = "Invalid session/list result: expected object"
                raise RuntimeError(msg)

            page_sessions = response.result.get("sessions")
            if not isinstance(page_sessions, list):
                msg = "Invalid session/list result: sessions must be array"
                raise RuntimeError(msg)
            for session in page_sessions:
                if isinstance(session, dict):
                    collected.append(session)

            next_cursor = response.result.get("nextCursor")
            if next_cursor is None:
                break
            if not isinstance(next_cursor, str):
                msg = "Invalid session/list result: nextCursor must be string or null"
                raise RuntimeError(msg)
            cursor = next_cursor

        return collected

    async def list_sessions_parsed(
        self,
        *,
        cwd: str | None = None,
        cursor: str | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> SessionListResult:
        """Запрашивает страницу `session/list` и валидирует ответ.

        Пример использования:
            page = await client.list_sessions_parsed(cwd="/tmp")
        """

        response = await self.list_sessions(cwd=cwd, cursor=cursor, transport=transport)
        return parse_session_list_result(response)

    async def list_all_sessions_parsed(
        self,
        *,
        cwd: str | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> list[SessionListItem]:
        """Возвращает все сессии как типизированные элементы `SessionListItem`.

        Пример использования:
            sessions = await client.list_all_sessions_parsed(cwd="/tmp")
        """

        collected: list[SessionListItem] = []
        cursor: str | None = None

        while True:
            page = await self.list_sessions_parsed(
                cwd=cwd,
                cursor=cursor,
                transport=transport,
            )
            collected.extend(page.sessions)
            if page.nextCursor is None:
                break
            cursor = page.nextCursor

        return collected

    async def create_session_parsed(
        self,
        *,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "http",
    ) -> SessionSetupResult:
        """Создает сессию через `session/new` и валидирует ответ.

        Пример использования:
            created = await client.create_session_parsed(cwd="/tmp", transport="http")
        """

        response = await self.request(
            method="session/new",
            params={
                "cwd": cwd,
                "mcpServers": mcp_servers or [],
            },
            transport=transport,
        )
        return parse_session_setup_result(response, method_name="session/new")

    async def load_session_setup_parsed(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[SessionSetupResult, list[SessionUpdateNotification]]:
        """Загружает сессию и возвращает typed state + typed replay updates.

        Пример использования:
            state, updates = await client.load_session_setup_parsed(
                session_id="sess_1",
                cwd="/tmp",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
            transport=transport,
        )
        parsed = parse_session_setup_result(response, method_name="session/load")
        return parsed, updates

    async def load_session_structured_updates(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[StructuredSessionUpdate]]:
        """Загружает сессию и возвращает только известные typed update payload.

        Пример использования:
            response, updates = await client.load_session_structured_updates(
                session_id="sess_1",
                cwd="/tmp",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
            transport=transport,
        )
        structured: list[StructuredSessionUpdate] = []
        for update in updates:
            parsed = parse_structured_session_update(update)
            if parsed is None:
                continue
            structured.append(parsed)
        return response, structured

    async def set_config_option_with_updates(
        self,
        *,
        session_id: str,
        config_id: str,
        value: str,
        transport: Literal["http", "ws"] = "ws",
    ) -> tuple[ACPMessage, list[StructuredSessionUpdate]]:
        """Меняет config option и возвращает typed update-события из WS-потока.

        Для HTTP-транспорта список updates обычно пустой, так как notification-
        поток в этом режиме не передается отдельными сообщениями.

        Пример использования:
            response, updates = await client.set_config_option_with_updates(
                session_id="sess_1",
                config_id="mode",
                value="code",
                transport="ws",
            )
        """

        raw_updates: list[dict[str, Any]] = []
        response = await self.request(
            method="session/set_config_option",
            params={
                "sessionId": session_id,
                "configId": config_id,
                "value": value,
            },
            transport=transport,
            on_update=raw_updates.append,
        )

        parsed_updates: list[StructuredSessionUpdate] = []
        for raw in raw_updates:
            if not isinstance(raw, dict):
                continue
            notification = parse_session_update_notification(raw)
            if notification is None:
                continue
            parsed = parse_structured_session_update(notification)
            if parsed is None:
                continue
            parsed_updates.append(parsed)

        return response, parsed_updates
