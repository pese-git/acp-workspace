from __future__ import annotations

import asyncio
import socket
from typing import Any

import pytest
from aiohttp import ClientSession, web

from acp_server.http_server import ACPHttpServer


def _get_free_port() -> int:
    """Возвращает свободный локальный TCP-порт для тестового сервера."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _start_test_server() -> tuple[web.AppRunner, int]:
    """Поднимает aiohttp-приложение с ACP HTTP/WS handlers."""

    port = _get_free_port()
    server = ACPHttpServer(host="127.0.0.1", port=port)
    app = web.Application()
    app.router.add_post("/acp", server.handle_http_request)
    app.router.add_get("/acp/ws", server.handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()
    return runner, port


async def _ws_initialize(ws: Any) -> None:
    """Выполняет обязательный ACP initialize в рамках WS-соединения."""

    await ws.send_json(
        {
            "jsonrpc": "2.0",
            "id": "init_1",
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {},
            },
        }
    )
    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
    assert payload["id"] == "init_1"
    assert payload.get("error") is None


@pytest.mark.asyncio
async def test_http_prompt_with_pending_tool_returns_end_turn() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            new_response = await session.post(
                f"http://127.0.0.1:{port}/acp",
                json={
                    "jsonrpc": "2.0",
                    "id": "new_1",
                    "method": "session/new",
                    "params": {"cwd": "/tmp", "mcpServers": []},
                },
            )
            new_payload = await new_response.json()
            session_id = new_payload["result"]["sessionId"]

            prompt_response = await session.post(
                f"http://127.0.0.1:{port}/acp",
                json={
                    "jsonrpc": "2.0",
                    "id": "prompt_1",
                    "method": "session/prompt",
                    "params": {
                        "sessionId": session_id,
                        "prompt": [{"type": "text", "text": "run [tool] with [tool-pending]"}],
                    },
                },
            )
            prompt_payload = await prompt_response.json()

            assert prompt_response.status == 200
            assert prompt_payload["id"] == "prompt_1"
            assert prompt_payload["result"] == {"stopReason": "end_turn"}
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_prompt_with_permission_selection_finishes_with_end_turn() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            ws = await session.ws_connect(f"http://127.0.0.1:{port}/acp/ws")
            try:
                await _ws_initialize(ws)
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "new_1",
                        "method": "session/new",
                        "params": {"cwd": "/tmp", "mcpServers": []},
                    }
                )
                new_payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                session_id = new_payload["result"]["sessionId"]

                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "prompt_1",
                        "method": "session/prompt",
                        "params": {
                            "sessionId": session_id,
                            "prompt": [{"type": "text", "text": "run [tool] with [tool-pending]"}],
                        },
                    }
                )

                received_prompt_response: dict | None = None
                for _ in range(12):
                    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    if payload.get("method") == "session/request_permission":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {
                                    "outcome": {
                                        "outcome": "selected",
                                        "optionId": "allow_once",
                                    },
                                },
                            }
                        )
                        continue
                    if payload.get("id") == "prompt_1":
                        received_prompt_response = payload
                        break

                assert received_prompt_response is not None
                assert received_prompt_response["result"] == {"stopReason": "end_turn"}
            finally:
                await ws.close()
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_cancel_finishes_deferred_prompt_with_cancelled() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            ws = await session.ws_connect(f"http://127.0.0.1:{port}/acp/ws")
            try:
                await _ws_initialize(ws)
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "new_1",
                        "method": "session/new",
                        "params": {"cwd": "/tmp", "mcpServers": []},
                    }
                )
                new_payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                session_id = new_payload["result"]["sessionId"]

                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "prompt_1",
                        "method": "session/prompt",
                        "params": {
                            "sessionId": session_id,
                            "prompt": [{"type": "text", "text": "run [tool] with [tool-pending]"}],
                        },
                    }
                )
                permission_request_seen = False
                for _ in range(8):
                    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    if payload.get("method") == "session/request_permission":
                        permission_request_seen = True
                        break
                assert permission_request_seen

                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "cancel_1",
                        "method": "session/cancel",
                        "params": {"sessionId": session_id},
                    }
                )

                responses: dict[str, dict] = {}
                for _ in range(12):
                    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    response_id = payload.get("id")
                    if isinstance(response_id, str):
                        responses[response_id] = payload
                    if "prompt_1" in responses and "cancel_1" in responses:
                        break

                assert responses["cancel_1"]["result"] is None
                assert responses["prompt_1"]["result"] == {"stopReason": "cancelled"}
            finally:
                await ws.close()
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_rejects_session_methods_before_initialize() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            ws = await session.ws_connect(f"http://127.0.0.1:{port}/acp/ws")
            try:
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "new_1",
                        "method": "session/new",
                        "params": {"cwd": "/tmp", "mcpServers": []},
                    }
                )
                payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

                assert payload["id"] == "new_1"
                assert payload["error"]["code"] == -32000
            finally:
                await ws.close()
    finally:
        await runner.cleanup()
