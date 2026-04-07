from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

import structlog

from .helpers import (
    extract_plan_updates,
    extract_structured_updates,
    extract_tool_call_updates,
    pick_auth_method_id,
)
from .messages import (
    ACPMessage,
    AuthenticateResult,
    InitializeResult,
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
    parse_prompt_result,
    parse_session_list_result,
    parse_session_setup_result,
    parse_session_update_notification,
)
from .transport import ACPClientWSSession

from typing import TypeAlias

PermissionHandler: TypeAlias = Callable[[dict[str, Any]], str | None]
FsReadHandler: TypeAlias = Callable[[str], str]
FsWriteHandler: TypeAlias = Callable[[str, str], str | None]
TerminalCreateHandler: TypeAlias = Callable[[str], str]
TerminalOutputHandler: TypeAlias = Callable[[str], str]
TerminalWaitHandler: TypeAlias = Callable[[str], int | tuple[int | None, str | None]]
TerminalReleaseHandler: TypeAlias = Callable[[str], None]
TerminalKillHandler: TypeAlias = Callable[[str], bool]


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

        # Фильтруем и парсим updates в SessionUpdateNotification
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

        response, raw_updates = await self.load_session(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
        )
        # Выделяем только tool-call updates из raw списка
        tool_updates = extract_tool_call_updates(raw_updates)
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

        response, raw_updates = await self.load_session(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
        )
        # Выделяем только plan updates из raw списка
        plan_updates = extract_plan_updates(raw_updates)
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

        response, raw_updates = await self.load_session(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=mcp_servers,
        )
        # Выделяем только известные typed updates из raw списка
        structured = extract_structured_updates(raw_updates)
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

        # Выделяем только известные typed updates из WS-потока
        parsed_updates = extract_structured_updates(raw_updates)

        return response, parsed_updates

