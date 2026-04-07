from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import structlog
from aiohttp import ClientSession, WSMsgType

from .messages import (
    ACPMessage,
    AuthenticateResult,
    InitializeResult,
    JsonRpcError,
    PlanUpdate,
    PromptResult,
    SessionListItem,
    SessionListResult,
    SessionSetupResult,
    SessionUpdateNotification,
    StructuredSessionUpdate,
    ToolCallUpdate,
    parse_authenticate_result,
    parse_initialize_result,
    parse_plan_update,
    parse_prompt_result,
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
type TerminalWaitHandler = Callable[[str], int | tuple[int | None, str | None]]
type TerminalReleaseHandler = Callable[[str], None]
type TerminalKillHandler = Callable[[str], bool]


class ACPClient:
    """Асинхронный ACP-клиент с WebSocket транспортом.

    Класс предоставляет:
    - универсальный метод `request`,
    - helper для `session/load` и replay-обновлений,
    - типизированный helper `load_session_parsed`.

    Пример использования:
        client = ACPClient(host="127.0.0.1", port=8080)
        response = await client.request("initialize")
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        *,
        preferred_auth_method_id: str | None = None,
        auth_api_key: str | None = None,
        auto_authenticate: bool = True,
    ) -> None:
        """Создает клиент с адресом ACP-сервера.

        Пример использования:
            client = ACPClient(host="127.0.0.1", port=8080)
        """

        self.host = host
        self.port = port
        self.preferred_auth_method_id = preferred_auth_method_id
        self.auth_api_key = auth_api_key
        self.auto_authenticate = auto_authenticate
        self.logger = structlog.get_logger("acp_client")

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
        """Выполняет ACP-запрос через WebSocket транспорт.

        Для WS может принимать `on_update`, который вызывается на каждый
        `session/update` до финального response. Также может принимать
        `on_permission` для обработки `session/request_permission`.

        Пример использования:
            await client.request("session/list")
        """

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

    def open_ws_session(self) -> ACPClientWSSession:
        """Создает persistent WS-сессию для нескольких ACP запросов.

        Пример использования:
            async with client.open_ws_session() as ws_session:
                await ws_session.request("session/list", params={})
        """

        return ACPClientWSSession(self)

    async def initialize(
        self,
        *,
        protocol_version: int = 1,
        client_capabilities: dict[str, Any] | None = None,
        client_info: dict[str, Any] | None = None,
    ) -> InitializeResult:
        """Выполняет `initialize` и возвращает типизированный negotiated result.

        Пример использования:
            result = await client.initialize()
        """

        self.logger.info("initialize_started", protocol_version=protocol_version)

        params: dict[str, Any] = {
            "protocolVersion": protocol_version,
            "clientCapabilities": client_capabilities or self._default_client_capabilities(),
        }
        if client_info is not None:
            params["clientInfo"] = client_info

        response = await self.request(
            method="initialize",
            params=params,
        )
        result = parse_initialize_result(response)
        
        self.logger.info(
            "initialize_completed",
            server_version=result.protocolVersion,
            has_auth=len(result.authMethods) > 0 if result.authMethods else False,
        )
        return result

    async def authenticate(
        self, *, method_id: str, api_key: str | None = None
    ) -> AuthenticateResult:
        """Выполняет `authenticate` для указанного auth method id.

        Пример использования:
            result = await client.authenticate(method_id="local")
        """

        self.logger.info("authenticate_started", method_id=method_id)

        resolved_api_key = api_key if isinstance(api_key, str) and api_key else self.auth_api_key
        auth_params: dict[str, Any] = {
            "methodId": method_id,
        }
        if isinstance(resolved_api_key, str) and resolved_api_key:
            auth_params["apiKey"] = resolved_api_key

        response = await self.request(
            method="authenticate",
            params=auth_params,
        )
        result = parse_authenticate_result(response)
        
        self.logger.info("authenticate_completed", method_id=method_id)
        return result

    async def prompt(
        self,
        *,
        session_id: str,
        prompt: list[dict[str, Any]],
        prompt_directives: dict[str, Any] | None = None,
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> PromptResult:
        """Выполняет `session/prompt` и возвращает типизированный stop reason.

        При передаче `prompt_directives` клиент добавляет structured-overrides в
        `_meta.promptDirectives`, что позволяет управлять demo-flow без slash-команд.

        Пример использования:
            result = await client.prompt(
                session_id="sess_1",
                prompt=[{"type": "text", "text": "build plan"}],
                prompt_directives={"publishPlan": True},
            )
        """

        self.logger.info("prompt_started", session_id=session_id, prompt_items=len(prompt))

        params: dict[str, Any] = {
            "sessionId": session_id,
            "prompt": prompt,
        }
        if isinstance(prompt_directives, dict) and prompt_directives:
            params["_meta"] = {
                "promptDirectives": prompt_directives,
            }

        response = await self.request(
            method="session/prompt",
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
        result = parse_prompt_result(response)
        
        self.logger.info("prompt_completed", session_id=session_id, stop_reason=result.stopReason)
        return result

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

        self.logger.debug("ws_request_sent", method=method, has_params=params is not None)

        async with self.open_ws_session() as ws_session:
            response = await ws_session.request(
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
            
            self.logger.debug(
                "ws_response_received",
                method=method,
                has_result=response.result is not None,
                has_error=response.error is not None,
            )
            return response

    async def _await_ws_response(
        self,
        *,
        ws: Any,
        request_id: Any,
        on_update: Callable[[dict], None] | None,
        on_permission: PermissionHandler | None,
        on_fs_read: FsReadHandler | None,
        on_fs_write: FsWriteHandler | None,
        on_terminal_create: TerminalCreateHandler | None,
        on_terminal_output: TerminalOutputHandler | None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None,
        on_terminal_release: TerminalReleaseHandler | None,
        on_terminal_kill: TerminalKillHandler | None,
    ) -> ACPMessage:
        """Ждет финальный response для request ID и обрабатывает server RPC.

        Пример использования:
            response = await client._await_ws_response(ws=ws, request_id="req_1", ...)
        """

        while True:
            message = await ws.receive()
            if message.type != WSMsgType.TEXT:
                msg = f"Unexpected WebSocket response type: {message.type}"
                raise RuntimeError(msg)

            payload = json.loads(message.data)
            raw_method = payload.get("method") if isinstance(payload, dict) else None
            if raw_method == "session/update":
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
            if response.id != request_id:
                continue
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
            _ = on_fs_write(path, content)
            return ACPMessage.response(request_id, {})

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
            return ACPMessage.response(
                request_id,
                {
                    "output": on_terminal_output(terminal_id),
                    "truncated": False,
                    "exitStatus": None,
                },
            )

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
            wait_result = on_terminal_wait_for_exit(terminal_id)
            exit_code: int | None
            signal: str | None
            if isinstance(wait_result, tuple):
                tuple_exit_code, tuple_signal = wait_result
                exit_code = tuple_exit_code if isinstance(tuple_exit_code, int) else None
                signal = tuple_signal if isinstance(tuple_signal, str) else None
            else:
                exit_code = wait_result if isinstance(wait_result, int) else None
                signal = None
            return ACPMessage.response(
                request_id,
                {
                    "exitCode": exit_code,
                    "signal": signal,
                },
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
            return ACPMessage.response(request_id, {})

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
            _ = on_terminal_kill(terminal_id)
            return ACPMessage.response(request_id, {})

        return None

    async def _perform_ws_initialize(self, ws: Any) -> InitializeResult:
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
            return parse_initialize_result(response)

    async def _perform_ws_authenticate(
        self,
        ws: Any,
        *,
        method_id: str,
        api_key: str | None = None,
    ) -> AuthenticateResult:
        """Выполняет ACP `authenticate` в открытом WS-соединении.

        Пример использования:
            await client._perform_ws_authenticate(ws, method_id="local")
        """

        resolved_api_key = api_key if isinstance(api_key, str) and api_key else self.auth_api_key
        auth_params: dict[str, Any] = {"methodId": method_id}
        if isinstance(resolved_api_key, str) and resolved_api_key:
            auth_params["apiKey"] = resolved_api_key

        auth_request = ACPMessage.request(
            method="authenticate",
            params=auth_params,
        )
        await ws.send_str(auth_request.to_json())

        while True:
            message = await ws.receive()
            if message.type != WSMsgType.TEXT:
                msg = f"Unexpected WebSocket response type during authenticate: {message.type}"
                raise RuntimeError(msg)

            payload = json.loads(message.data)
            raw_method = payload.get("method") if isinstance(payload, dict) else None
            if raw_method == "session/update":
                continue
            response = ACPMessage.from_dict(payload)
            if response.id != auth_request.id:
                continue
            if response.error is not None:
                msg = (
                    f"WebSocket authenticate failed: {response.error.code} {response.error.message}"
                )
                raise RuntimeError(msg)
            return parse_authenticate_result(response)

    def _pick_auth_method_id(self, init_result: InitializeResult) -> str | None:
        """Выбирает auth method id из negotiated `authMethods`.

        Пример использования:
            method_id = client._pick_auth_method_id(init_result)
        """

        auth_methods = init_result.authMethods
        if not auth_methods:
            return None
        if self.preferred_auth_method_id is not None:
            for auth_method in auth_methods:
                if auth_method.id == self.preferred_auth_method_id:
                    return auth_method.id
            msg = f"Preferred auth method not advertised: {self.preferred_auth_method_id}"
            raise RuntimeError(msg)
        return auth_methods[0].id

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
    ) -> tuple[ACPMessage, list[dict[str, Any]]]:
        """Выполняет `session/load` и возвращает response вместе с raw updates.

        Helper упрощает сценарий восстановления контекста: клиент получает
        финальный ответ и весь replay update-поток в одном вызове.

        Пример использования:
            response, updates = await client.load_session(
                session_id="sess_1",
                cwd="/tmp",
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
            on_update=updates.append,
        )
        return response, updates

    async def load_session_parsed(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> tuple[ACPMessage, list[SessionUpdateNotification]]:
        """Выполняет `session/load` и возвращает типизированные update-события.

        В отличие от `load_session`, этот метод фильтрует и валидирует только
        корректные notifications `session/update`.

        Пример использования:
            response, updates = await client.load_session_parsed(
                session_id="sess_1",
                cwd="/tmp",
            )
        """

        self.logger.info(
            "load_session_started",
            session_id=session_id,
            cwd=cwd,
            mcp_servers_count=len(mcp_servers) if mcp_servers else 0,
        )

        raw_response, raw_updates = await self.load_session(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
        )

        parsed_updates: list[SessionUpdateNotification] = []
        for raw_update in raw_updates:
            if not isinstance(raw_update, dict):
                continue
            parsed = parse_session_update_notification(raw_update)
            if parsed is None:
                continue
            parsed_updates.append(parsed)

        self.logger.info(
            "load_session_completed",
            session_id=session_id,
            updates_count=len(parsed_updates),
        )
        return raw_response, parsed_updates

    async def load_session_tool_updates(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> tuple[ACPMessage, list[ToolCallUpdate]]:
        """Выполняет `session/load` и выделяет только tool-call update-события.

        Метод удобен для UI/логики, которым важны только статусы инструментов,
        без разбора остальных событий `session/update`.

        Пример использования:
            response, tool_updates = await client.load_session_tool_updates(
                session_id="sess_1",
                cwd="/tmp",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
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
    ) -> tuple[ACPMessage, list[PlanUpdate]]:
        """Выполняет `session/load` и выделяет только plan update-события.

        Метод полезен клиентам, которые показывают пользователю только текущий
        план выполнения без остальных `session/update` событий.

        Пример использования:
            response, plans = await client.load_session_plan_updates(
                session_id="sess_1",
                cwd="/tmp",
            )
        """

        response, updates = await self.load_session_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
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
    ) -> ACPMessage:
        """Запрашивает одну страницу `session/list` с optional фильтрами.

        Пример использования:
            response = await client.list_sessions(cwd="/tmp")
        """

        params: dict[str, Any] = {}
        if cwd is not None:
            params["cwd"] = cwd
        if cursor is not None:
            params["cursor"] = cursor
        return await self.request(method="session/list", params=params)

    async def list_all_sessions(
        self,
        *,
        cwd: str | None = None,
    ) -> list[dict[str, Any]]:
        """Возвращает все сессии, последовательно проходя cursor-пагинацию.

        Если сервер вернет невалидный формат ответа, метод аварийно завершится
        исключением `RuntimeError`, чтобы клиент явно увидел нарушение контракта.

        Пример использования:
            sessions = await client.list_all_sessions(cwd="/tmp")
        """

        collected: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            response = await self.list_sessions(cwd=cwd, cursor=cursor)
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
    ) -> SessionListResult:
        """Запрашивает страницу `session/list` и валидирует ответ.

        Пример использования:
            page = await client.list_sessions_parsed(cwd="/tmp")
        """

        response = await self.list_sessions(cwd=cwd, cursor=cursor)
        return parse_session_list_result(response)

    async def list_all_sessions_parsed(
        self,
        *,
        cwd: str | None = None,
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
    ) -> SessionSetupResult:
        """Создает сессию через `session/new` и валидирует ответ.

        Пример использования:
            created = await client.create_session_parsed(cwd="/tmp")
        """

        response = await self.request(
            method="session/new",
            params={
                "cwd": cwd,
                "mcpServers": mcp_servers or [],
            },
        )
        return parse_session_setup_result(response, method_name="session/new")

    async def load_session_setup_parsed(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
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
        )
        parsed = parse_session_setup_result(response, method_name="session/load")
        return parsed, updates

    async def load_session_structured_updates(
        self,
        *,
        session_id: str,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
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
    ) -> tuple[ACPMessage, list[StructuredSessionUpdate]]:
        """Меняет config option и возвращает typed update-события из WS-потока.

        Пример использования:
            response, updates = await client.set_config_option_with_updates(
                session_id="sess_1",
                config_id="mode",
                value="code",
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


class ACPClientWSSession:
    """Persistent WebSocket-сессия для последовательных ACP-запросов.

    Пример использования:
        async with ACPClient(host="127.0.0.1", port=8080).open_ws_session() as ws_session:
            await ws_session.request("session/list", params={})
    """

    def __init__(self, client: ACPClient) -> None:
        """Создает объект persistent-сессии поверх переданного ACPClient.

        Пример использования:
            ws_session = ACPClientWSSession(client)
        """

        self._client = client
        self._http_session: ClientSession | None = None
        self._ws: Any | None = None
        self._initialized = False

    async def __aenter__(self) -> ACPClientWSSession:
        """Открывает WS-соединение и возвращает текущий session-object.

        Пример использования:
            async with client.open_ws_session() as ws_session:
                ...
        """

        url = f"ws://{self._client.host}:{self._client.port}/acp/ws"
        self._http_session = ClientSession()
        self._ws = await self._http_session.ws_connect(url)
        return self

    async def __aexit__(self, *_: object) -> None:
        """Закрывает WS и HTTP-сессию независимо от результата операций.

        Пример использования:
            await ws_session.__aexit__(None, None, None)
        """

        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._http_session is not None:
            await self._http_session.close()
            self._http_session = None
        self._initialized = False

    async def request(
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
        """Отправляет ACP-запрос в рамках открытой persistent WS-сессии.

        Пример использования:
            response = await ws_session.request("session/list", params={})
        """

        if self._ws is None:
            raise RuntimeError("WebSocket session is not opened")

        should_initialize = method.startswith("session/") and method != "initialize"
        if should_initialize and not self._initialized:
            init_result = await self._client._perform_ws_initialize(self._ws)
            if self._client.auto_authenticate:
                selected_auth_method = self._client._pick_auth_method_id(init_result)
                if selected_auth_method is not None:
                    await self._client._perform_ws_authenticate(
                        self._ws,
                        method_id=selected_auth_method,
                        api_key=self._client.auth_api_key,
                    )
            self._initialized = True

        request = ACPMessage.request(method=method, params=params)
        await self._ws.send_str(request.to_json())
        response = await self._client._await_ws_response(
            ws=self._ws,
            request_id=request.id,
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
        if method == "initialize" and response.error is None:
            self._initialized = True
        return response

    async def authenticate(
        self, *, method_id: str, api_key: str | None = None
    ) -> AuthenticateResult:
        """Выполняет `authenticate` в рамках persistent WS-сессии.

        Пример использования:
            await ws_session.authenticate(method_id="local")
        """

        response = await self.request(
            method="authenticate",
            params={
                "methodId": method_id,
                **(
                    {"apiKey": api_key}
                    if isinstance(api_key, str) and api_key
                    else (
                        {"apiKey": self._client.auth_api_key}
                        if isinstance(self._client.auth_api_key, str) and self._client.auth_api_key
                        else {}
                    )
                ),
            },
        )
        return parse_authenticate_result(response)

    async def prompt(
        self,
        *,
        session_id: str,
        prompt: list[dict[str, Any]],
        prompt_directives: dict[str, Any] | None = None,
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> PromptResult:
        """Выполняет `session/prompt` в persistent WS и парсит stop reason.

        Пример использования:
            result = await ws_session.prompt(
                session_id="sess_1",
                prompt=[{"type": "text", "text": "build plan"}],
                prompt_directives={"publishPlan": True},
            )
        """

        params: dict[str, Any] = {
            "sessionId": session_id,
            "prompt": prompt,
        }
        if isinstance(prompt_directives, dict) and prompt_directives:
            params["_meta"] = {
                "promptDirectives": prompt_directives,
            }

        response = await self.request(
            method="session/prompt",
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
        return parse_prompt_result(response)
