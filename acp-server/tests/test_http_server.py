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


async def _start_test_server(*, require_auth: bool = False) -> tuple[web.AppRunner, int]:
    """Поднимает aiohttp-приложение с ACP WS handler."""

    port = _get_free_port()
    server = ACPHttpServer(host="127.0.0.1", port=port, require_auth=require_auth)
    app = web.Application()
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
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": True,
                },
            },
        }
    )
    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
    assert payload["id"] == "init_1"
    assert payload.get("error") is None


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
                            "prompt": [{"type": "text", "text": "/tool-pending run"}],
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
                            "prompt": [{"type": "text", "text": "/tool-pending run"}],
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


@pytest.mark.asyncio
async def test_ws_requires_authenticate_when_server_auth_enabled() -> None:
    runner, port = await _start_test_server(require_auth=True)

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
                unauthorized = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                assert unauthorized["id"] == "new_1"
                assert unauthorized["error"]["message"] == "auth_required"

                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "auth_1",
                        "method": "authenticate",
                        "params": {"methodId": "local"},
                    }
                )
                authenticated = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                assert authenticated["id"] == "auth_1"
                assert authenticated["result"] == {}

                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "new_2",
                        "method": "session/new",
                        "params": {"cwd": "/tmp", "mcpServers": []},
                    }
                )
                authorized = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                assert authorized["id"] == "new_2"
                assert isinstance(authorized.get("result", {}).get("sessionId"), str)
            finally:
                await ws.close()
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_prompt_fs_read_roundtrip_finishes_with_end_turn() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            ws = await session.ws_connect(f"http://127.0.0.1:{port}/acp/ws")
            try:
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "init_1",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": 1,
                            "clientCapabilities": {
                                "fs": {"readTextFile": True, "writeTextFile": False},
                                "terminal": False,
                            },
                        },
                    }
                )
                _ = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

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
                            "prompt": [{"type": "text", "text": "/fs-read README.md"}],
                        },
                    }
                )

                received_prompt_response: dict | None = None
                for _ in range(12):
                    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    if payload.get("method") == "fs/read_text_file":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {"content": "hello"},
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
async def test_ws_prompt_terminal_roundtrip_finishes_with_end_turn() -> None:
    runner, port = await _start_test_server()

    try:
        async with ClientSession() as session:
            ws = await session.ws_connect(f"http://127.0.0.1:{port}/acp/ws")
            try:
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": "init_1",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": 1,
                            "clientCapabilities": {
                                "fs": {"readTextFile": False, "writeTextFile": False},
                                "terminal": True,
                            },
                        },
                    }
                )
                _ = await asyncio.wait_for(ws.receive_json(), timeout=1.0)

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
                            "prompt": [{"type": "text", "text": "/term-run ls"}],
                        },
                    }
                )

                received_prompt_response: dict | None = None
                for _ in range(20):
                    payload = await asyncio.wait_for(ws.receive_json(), timeout=1.0)
                    method = payload.get("method")
                    if method == "terminal/create":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {"terminalId": "term_1"},
                            }
                        )
                        continue
                    if method == "terminal/output":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {"output": "ok"},
                            }
                        )
                        continue
                    if method == "terminal/wait_for_exit":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {"exitCode": 0},
                            }
                        )
                        continue
                    if method == "terminal/release":
                        await ws.send_json(
                            {
                                "jsonrpc": "2.0",
                                "id": payload["id"],
                                "result": {"ok": True},
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
