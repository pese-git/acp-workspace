from __future__ import annotations

import asyncio
from typing import Literal

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
        transport: Literal["tcp", "http", "ws"] = "tcp",
    ) -> ACPMessage:
        if transport == "tcp":
            return await self._request_tcp(method=method, params=params)
        if transport == "http":
            return await self._request_http(method=method, params=params)
        return await self._request_ws(method=method, params=params)

    async def _request_tcp(self, method: str, params: dict | None = None) -> ACPMessage:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            request = ACPMessage.request(method=method, params=params)
            writer.write((request.to_json() + "\n").encode())
            await writer.drain()

            raw = await reader.readline()
            if not raw:
                msg = "No response from server"
                raise RuntimeError(msg)

            return ACPMessage.from_json(raw.decode().strip())
        finally:
            writer.close()
            await writer.wait_closed()

    async def _request_http(self, method: str, params: dict | None = None) -> ACPMessage:
        request = ACPMessage.request(method=method, params=params)
        url = f"http://{self.host}:{self.port}/acp"

        async with (
            ClientSession() as session,
            session.post(url, json=request.to_dict()) as response,
        ):
            payload = await response.json()
            return ACPMessage.from_dict(payload)

    async def _request_ws(self, method: str, params: dict | None = None) -> ACPMessage:
        request = ACPMessage.request(method=method, params=params)
        url = f"ws://{self.host}:{self.port}/acp/ws"

        async with ClientSession() as session, session.ws_connect(url) as ws:
            await ws.send_str(request.to_json())
            message = await ws.receive()

            if message.type != WSMsgType.TEXT:
                msg = f"Unexpected WebSocket response type: {message.type}"
                raise RuntimeError(msg)

            return ACPMessage.from_json(message.data)
