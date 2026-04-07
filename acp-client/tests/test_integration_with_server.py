from __future__ import annotations

import json
import socket

import pytest
from aiohttp import web

from acp_client import ACPClient


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_http_client_server_ping() -> None:
    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        response = {
            "jsonrpc": payload.get("jsonrpc", "2.0"),
            "id": payload["id"],
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
        assert response.jsonrpc == "2.0"
        assert response.result is not None
        assert response.result["pong"] is True
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_load_session_helper_collects_replay_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            assert payload["method"] == "session/load"
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_1",
                        "update": {
                            "sessionUpdate": "user_message_chunk",
                            "content": {"type": "text", "text": "hello"},
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_1",
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "world"},
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "configOptions": [],
                        "modes": {"availableModes": [], "currentModeId": "ask"},
                    },
                }
            )
            break
        return ws

    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response, updates = await client.load_session(
            session_id="sess_1",
            cwd="/tmp",
            mcp_servers=[],
            transport="ws",
        )
        assert isinstance(response.result, dict)
        assert len(updates) == 2
        update_types: list[str | None] = [
            update.get("params", {}).get("update", {}).get("sessionUpdate")
            for update in updates
            if isinstance(update, dict)
        ]
        assert "user_message_chunk" in update_types
        assert "agent_message_chunk" in update_types
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_load_session_parsed_returns_typed_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            assert payload["method"] == "session/load"
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_2",
                        "update": {
                            "sessionUpdate": "session_info_update",
                            "updatedAt": "2026-04-07T00:00:00Z",
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "configOptions": [],
                        "modes": {"availableModes": [], "currentModeId": "ask"},
                    },
                }
            )
            break
        return ws

    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response, updates = await client.load_session_parsed(
            session_id="sess_2",
            cwd="/tmp",
            mcp_servers=[],
            transport="ws",
        )
        assert isinstance(response.result, dict)
        assert len(updates) == 1
        assert updates[0].params.sessionId == "sess_2"
        assert updates[0].params.update.sessionUpdate == "session_info_update"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_load_session_tool_updates_filters_non_tool_events() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            assert payload["method"] == "session/load"
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_3",
                        "update": {
                            "sessionUpdate": "session_info_update",
                            "updatedAt": "2026-04-07T00:00:00Z",
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_3",
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": "call_001",
                            "title": "Demo tool",
                            "kind": "other",
                            "status": "pending",
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_3",
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": "call_001",
                            "status": "completed",
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "configOptions": [],
                        "modes": {"availableModes": [], "currentModeId": "ask"},
                    },
                }
            )
            break
        return ws

    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response, tool_updates = await client.load_session_tool_updates(
            session_id="sess_3",
            cwd="/tmp",
            mcp_servers=[],
            transport="ws",
        )
        assert isinstance(response.result, dict)
        assert len(tool_updates) == 2
        assert tool_updates[0].sessionUpdate == "tool_call"
        assert tool_updates[1].sessionUpdate == "tool_call_update"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_receives_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_1",
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "hello"},
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"stopReason": "end_turn"},
                }
            )
            break
        return ws

    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    updates: list[dict] = []
    try:
        client = ACPClient(host="127.0.0.1", port=port)
        response = await client.request(
            method="session/prompt",
            params={"sessionId": "sess_1", "prompt": [{"type": "text", "text": "hi"}]},
            transport="ws",
            on_update=updates.append,
        )
        assert response.result == {"stopReason": "end_turn"}
        assert len(updates) == 1
        assert updates[0]["method"] == "session/update"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_handles_permission_request() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            prompt_payload = json.loads(message.data)
            assert prompt_payload["method"] == "session/prompt"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "perm_1",
                    "method": "session/request_permission",
                    "params": {
                        "sessionId": "sess_1",
                        "toolCall": {"toolCallId": "call_001"},
                        "options": [
                            {
                                "optionId": "allow_once",
                                "name": "Allow once",
                                "kind": "allow_once",
                            }
                        ],
                    },
                }
            )

            permission_response = await ws.receive_json()
            assert permission_response["id"] == "perm_1"
            assert permission_response["result"]["outcome"] == "selected"
            assert permission_response["result"]["optionId"] == "allow_once"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": prompt_payload["id"],
                    "result": {"stopReason": "end_turn"},
                }
            )
            break
        return ws

    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)

        def choose_permission(payload: dict) -> str | None:
            options = payload.get("params", {}).get("options", [])
            if options and isinstance(options[0], dict):
                option_id = options[0].get("optionId")
                if isinstance(option_id, str):
                    return option_id
            return None

        response = await client.request(
            method="session/prompt",
            params={"sessionId": "sess_1", "prompt": [{"type": "text", "text": "run"}]},
            transport="ws",
            on_permission=choose_permission,
        )

        assert response.result == {"stopReason": "end_turn"}
    finally:
        await runner.cleanup()
