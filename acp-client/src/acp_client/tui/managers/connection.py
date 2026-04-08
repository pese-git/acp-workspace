"""Менеджер сетевого взаимодействия TUI с ACP сервером."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from acp_client.client import ACPClient
from acp_client.messages import (
    InitializeResult,
    PromptResult,
    SessionListItem,
    SessionSetupResult,
    SessionUpdateNotification,
    parse_initialize_result,
    parse_prompt_result,
    parse_session_list_result,
    parse_session_setup_result,
    parse_session_update_notification,
)
from acp_client.transport import ACPClientWSSession

type PermissionHandler = Callable[[dict[str, Any]], str | None | Awaitable[str | None]]
type FsReadHandler = Callable[[str], str]
type FsWriteHandler = Callable[[str, str], None]
type ReconnectEventHandler = Callable[[str], None]


class ACPConnectionManager:
    """Тонкая обертка над ACPClient для потребностей TUI."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        on_reconnect_attempt: ReconnectEventHandler | None = None,
        on_reconnect_recovered: ReconnectEventHandler | None = None,
    ) -> None:
        """Инициализирует клиента и logger для сетевых вызовов."""

        self._client = ACPClient(host=host, port=port)
        self._logger = structlog.get_logger("acp_client.tui.connection")
        self._ws_session: ACPClientWSSession | None = None
        self._initialized = False
        self._on_reconnect_attempt = on_reconnect_attempt
        self._on_reconnect_recovered = on_reconnect_recovered

    async def _ensure_ws_session(self) -> ACPClientWSSession:
        """Открывает persistent WS при первом запросе и возвращает session-object."""

        if self._ws_session is not None:
            return self._ws_session

        self._ws_session = self._client.open_ws_session()
        await self._ws_session.__aenter__()
        self._initialized = False
        self._logger.debug("tui_ws_session_opened")
        return self._ws_session

    async def _request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        on_update: Callable[[dict[str, Any]], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
    ) -> Any:
        """Отправляет ACP-запрос через persistent WS с одним retry после reconnect."""

        for attempt in range(2):
            ws_session = await self._ensure_ws_session()
            try:
                response = await ws_session.request(
                    method=method,
                    params=params,
                    on_update=on_update,
                    on_permission=on_permission,
                    on_fs_read=on_fs_read,
                    on_fs_write=on_fs_write,
                )
                if attempt > 0 and self._on_reconnect_recovered is not None:
                    self._on_reconnect_recovered(method)
                return response
            except Exception as error:
                # При транспортной ошибке закрываем сокет и даем один retry,
                # чтобы клиент автоматически восстановил соединение.
                await self.close()
                if attempt == 0:
                    if self._on_reconnect_attempt is not None:
                        self._on_reconnect_attempt(method)
                    self._logger.warning(
                        "tui_request_retry_after_reconnect",
                        method=method,
                        error=str(error),
                    )
                    continue
                raise

        msg = "Unreachable retry state"
        raise RuntimeError(msg)

    async def _ensure_initialized(self) -> None:
        """Гарантирует ACP initialize перед вызовом session/* методов."""

        if self._initialized:
            return
        await self.initialize()

    async def close(self) -> None:
        """Закрывает persistent WS-сессию TUI-клиента."""

        if self._ws_session is None:
            return
        await self._ws_session.__aexit__(None, None, None)
        self._ws_session = None
        self._initialized = False
        self._logger.debug("tui_ws_session_closed")

    def is_ready(self) -> bool:
        """Возвращает True, когда соединение открыто и initialize уже выполнен."""

        return self._ws_session is not None and self._initialized

    async def initialize(self) -> InitializeResult:
        """Выполняет initialize handshake и возвращает negotiated capabilities."""

        self._logger.info("tui_initialize_started")
        response = await self._request(
            method="initialize",
            params={
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": True},
                    "terminal": False,
                },
                "clientInfo": {
                    "name": "acp-client",
                    "title": "ACP-Client TUI",
                    "version": "0.1.0",
                },
            },
        )
        result = parse_initialize_result(response)
        self._initialized = True
        self._logger.info("tui_initialize_completed")
        return result

    async def list_sessions(self) -> list[SessionListItem]:
        """Возвращает полный список сессий через helper пагинации."""

        await self._ensure_initialized()

        sessions: list[SessionListItem] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {}
            if cursor is not None:
                params["cursor"] = cursor
            response = await self._request(method="session/list", params=params)
            page = parse_session_list_result(response)
            sessions.extend(page.sessions)
            if page.nextCursor is None:
                break
            cursor = page.nextCursor

        return sessions

    async def create_session(self, cwd: str) -> SessionSetupResult:
        """Создает новую сессию с указанной рабочей директорией."""

        await self._ensure_initialized()
        response = await self._request(
            method="session/new",
            params={"cwd": cwd, "mcpServers": []},
        )
        return parse_session_setup_result(response, method_name="session/new")

    async def load_session(
        self,
        session_id: str,
        cwd: str,
    ) -> tuple[SessionSetupResult, list[SessionUpdateNotification]]:
        """Загружает сессию и возвращает state вместе с replay updates."""

        await self._ensure_initialized()
        raw_updates: list[dict[str, Any]] = []
        response = await self._request(
            method="session/load",
            params={
                "sessionId": session_id,
                "cwd": cwd,
                "mcpServers": [],
            },
            on_update=raw_updates.append,
        )
        parsed_response = parse_session_setup_result(response, method_name="session/load")
        parsed_updates: list[SessionUpdateNotification] = []
        for raw_update in raw_updates:
            parsed = parse_session_update_notification(raw_update)
            if parsed is not None:
                parsed_updates.append(parsed)
        return parsed_response, parsed_updates

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Callable[[dict[str, Any]], None] | None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
    ) -> PromptResult:
        """Отправляет текстовый prompt в активную сессию."""

        await self._ensure_initialized()
        response = await self._request(
            method="session/prompt",
            params={
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}],
            },
            on_update=on_update,
            on_permission=on_permission,
            on_fs_read=on_fs_read,
            on_fs_write=on_fs_write,
        )
        return parse_prompt_result(response)

    async def cancel_prompt(self, session_id: str) -> None:
        """Отправляет уведомление отмены выполнения для активной сессии."""

        await self._ensure_initialized()
        await self._request("session/cancel", {"sessionId": session_id})
