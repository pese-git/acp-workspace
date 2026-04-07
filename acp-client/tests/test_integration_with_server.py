from __future__ import annotations

import asyncio
import json
import socket

import pytest
from aiohttp import web

from acp_client import ACPClient


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _handle_tcp_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    raw = await reader.readline()
    request = json.loads(raw.decode().strip())
    response = {
        "jsonrpc": request.get("jsonrpc", "2.0"),
        "id": request["id"],
        "type": "response",
        "result": {"pong": True},
    }
    writer.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_tcp_client_server_ping() -> None:
    port = _get_free_port()
    server = await asyncio.start_server(_handle_tcp_client, host="127.0.0.1", port=port)

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response = await client.request(method="ping", transport="tcp")
        assert response.type == "response"
        assert response.jsonrpc == "2.0"
        assert response.result is not None
        assert response.result["pong"] is True
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_http_client_server_ping() -> None:
    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        response = {
            "jsonrpc": payload.get("jsonrpc", "2.0"),
            "id": payload["id"],
            "type": "response",
            "result": {"pong": True},
        }
        return web.json_response(response)

    port = _get_free_port()
    app = web.Application()
    app.router.add_post("/acp", handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response = await client.request(method="ping", transport="http")
        assert response.type == "response"
        assert response.jsonrpc == "2.0"
        assert response.result is not None
        assert response.result["pong"] is True
    finally:
        await runner.cleanup()
