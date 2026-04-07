from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

from aiohttp import ClientSession, WSMsgType

from .messages import ACPMessage


class ACPClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port

    async def request(
        self,
        method: str,
        params: dict | None = None,
        transport: Literal["http", "ws"] = "http",
        on_update: Callable[[dict], None] | None = None,
    ) -> ACPMessage:
        if transport == "http":
            return await self._request_http(method=method, params=params)
        return await self._request_ws(method=method, params=params, on_update=on_update)

    async def _request_http(self, method: str, params: dict | None = None) -> ACPMessage:
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
        # Для `session/load` удобно вернуть и финальный ответ, и replay-обновления.
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
