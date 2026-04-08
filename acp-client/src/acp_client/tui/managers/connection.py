"""Менеджер сетевого взаимодействия TUI с ACP сервером."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from acp_client.client import ACPClient
from acp_client.messages import InitializeResult, PromptResult, SessionListItem, SessionSetupResult


class ACPConnectionManager:
    """Тонкая обертка над ACPClient для потребностей TUI."""

    def __init__(self, host: str, port: int) -> None:
        """Инициализирует клиента и logger для сетевых вызовов."""

        self._client = ACPClient(host=host, port=port)
        self._logger = structlog.get_logger("acp_client.tui.connection")

    async def initialize(self) -> InitializeResult:
        """Выполняет initialize handshake и возвращает negotiated capabilities."""

        self._logger.info("tui_initialize_started")
        result = await self._client.initialize(
            client_capabilities={
                "fs": {"readTextFile": False, "writeTextFile": False},
                "terminal": False,
            },
            client_info={
                "name": "acp-client",
                "title": "ACP-Client TUI",
                "version": "0.1.0",
            },
        )
        self._logger.info("tui_initialize_completed")
        return result

    async def list_sessions(self) -> list[SessionListItem]:
        """Возвращает полный список сессий через helper пагинации."""

        return await self._client.list_all_sessions_parsed()

    async def create_session(self, cwd: str) -> SessionSetupResult:
        """Создает новую сессию с указанной рабочей директорией."""

        return await self._client.create_session_parsed(cwd=cwd, mcp_servers=[])

    async def load_session(self, session_id: str, cwd: str) -> SessionSetupResult:
        """Загружает существующую сессию и возвращает ее состояние."""

        state, _updates = await self._client.load_session_setup_parsed(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=[],
        )
        return state

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Callable[[dict[str, Any]], None] | None,
    ) -> PromptResult:
        """Отправляет текстовый prompt в активную сессию."""

        return await self._client.prompt(
            session_id=session_id,
            prompt=[{"type": "text", "text": text}],
            on_update=on_update,
        )

    async def cancel_prompt(self, session_id: str) -> None:
        """Отправляет уведомление отмены выполнения для активной сессии."""

        await self._client.request("session/cancel", {"sessionId": session_id})
