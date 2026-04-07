from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from aiohttp import ClientSession, WSMsgType

from .messages import (
    ACPMessage,
    SessionUpdateNotification,
    ToolCallUpdate,
    parse_session_update_notification,
    parse_tool_call_update,
)


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

    async def request(
        self,
        method: str,
        params: dict | None = None,
        transport: Literal["http", "ws"] = "http",
        on_update: Callable[[dict], None] | None = None,
    ) -> ACPMessage:
        """Выполняет ACP-запрос через выбранный транспорт.

        Для WS может принимать `on_update`, который вызывается на каждый
        `session/update` до финального response.

        Пример использования:
            await client.request("session/list", transport="http")
        """

        if transport == "http":
            return await self._request_http(method=method, params=params)
        return await self._request_ws(method=method, params=params, on_update=on_update)

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
    ) -> ACPMessage:
        """Отправляет request через WebSocket и слушает updates до финала.

        Метод возвращает только финальный JSON-RPC response. Промежуточные
        `session/update` события передаются в callback `on_update`.

        Пример использования:
            await client._request_ws("session/prompt", params, updates.append)
        """

        request = ACPMessage.request(method=method, params=params)
        url = f"ws://{self.host}:{self.port}/acp/ws"

        async with ClientSession() as session, session.ws_connect(url) as ws:
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

                return ACPMessage.from_dict(payload)

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
