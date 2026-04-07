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
async def test_initialize_helper_parses_response() -> None:
    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        assert payload["method"] == "initialize"
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "protocolVersion": 1,
                    "agentCapabilities": {
                        "loadSession": True,
                        "promptCapabilities": {
                            "image": False,
                            "audio": False,
                            "embeddedContext": False,
                        },
                        "mcpCapabilities": {"http": False, "sse": False},
                        "sessionCapabilities": {"list": {}},
                    },
                    "agentInfo": {"name": "acp-server", "version": "0.1.0"},
                    "authMethods": [],
                },
            }
        )

    port = _get_free_port()
    app = web.Application()
    app.router.add_post("/acp", handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        result = await client.initialize(transport="http")
        assert result.protocolVersion == 1
        assert result.agentCapabilities.loadSession is True
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_create_session_parsed_helper() -> None:
    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        assert payload["method"] == "session/new"
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "sessionId": "sess_42",
                    "configOptions": [
                        {
                            "id": "mode",
                            "name": "Mode",
                            "category": "mode",
                            "type": "select",
                            "currentValue": "ask",
                            "options": [{"value": "ask", "name": "Ask"}],
                        }
                    ],
                    "modes": {
                        "availableModes": [{"id": "ask", "name": "Ask"}],
                        "currentModeId": "ask",
                    },
                },
            }
        )

    port = _get_free_port()
    app = web.Application()
    app.router.add_post("/acp", handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        created = await client.create_session_parsed(cwd="/tmp", mcp_servers=[], transport="http")
        assert created.sessionId == "sess_42"
        assert created.configOptions[0].id == "mode"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_list_all_sessions_walks_http_pagination() -> None:
    pages = [
        {
            "sessions": [
                {
                    "sessionId": "sess_1",
                    "cwd": "/tmp",
                    "updatedAt": "2026-04-07T00:00:00Z",
                }
            ],
            "nextCursor": "cursor_2",
        },
        {
            "sessions": [
                {
                    "sessionId": "sess_2",
                    "cwd": "/tmp",
                    "updatedAt": "2026-04-07T00:01:00Z",
                }
            ],
            "nextCursor": None,
        },
    ]

    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        assert payload["method"] == "session/list"
        params = payload.get("params", {})
        cursor = params.get("cursor")
        page = pages[0] if cursor is None else pages[1]
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": page,
            }
        )

    port = _get_free_port()
    app = web.Application()
    app.router.add_post("/acp", handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        sessions = await client.list_all_sessions(cwd="/tmp", transport="http")
        assert len(sessions) == 2
        assert sessions[0]["sessionId"] == "sess_1"
        assert sessions[1]["sessionId"] == "sess_2"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_list_all_sessions_parsed_walks_http_pagination() -> None:
    pages = [
        {
            "sessions": [
                {
                    "sessionId": "sess_10",
                    "cwd": "/tmp",
                    "title": "First",
                    "updatedAt": "2026-04-07T00:00:00Z",
                }
            ],
            "nextCursor": "cursor_2",
        },
        {
            "sessions": [
                {
                    "sessionId": "sess_20",
                    "cwd": "/tmp",
                    "title": "Second",
                    "updatedAt": "2026-04-07T00:01:00Z",
                }
            ],
            "nextCursor": None,
        },
    ]

    async def handle_http_request(request: web.Request) -> web.Response:
        payload = await request.json()
        assert payload["method"] == "session/list"
        params = payload.get("params", {})
        cursor = params.get("cursor")
        page = pages[0] if cursor is None else pages[1]
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": page,
            }
        )

    port = _get_free_port()
    app = web.Application()
    app.router.add_post("/acp", handle_http_request)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=port)
    await site.start()

    try:
        client = ACPClient(host="127.0.0.1", port=port)
        sessions = await client.list_all_sessions_parsed(cwd="/tmp", transport="http")
        assert len(sessions) == 2
        assert sessions[0].sessionId == "sess_10"
        assert sessions[1].sessionId == "sess_20"
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
async def test_load_session_plan_updates_filters_non_plan_events() -> None:
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
                        "sessionId": "sess_4",
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
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_4",
                        "update": {
                            "sessionUpdate": "plan",
                            "entries": [
                                {
                                    "content": "Проверить входные данные",
                                    "priority": "high",
                                    "status": "in_progress",
                                }
                            ],
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
        response, plan_updates = await client.load_session_plan_updates(
            session_id="sess_4",
            cwd="/tmp",
            mcp_servers=[],
            transport="ws",
        )
        assert isinstance(response.result, dict)
        assert len(plan_updates) == 1
        assert plan_updates[0].entries[0].priority == "high"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_load_session_structured_updates_filters_known_payloads() -> None:
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
                        "sessionId": "sess_5",
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
                        "sessionId": "sess_5",
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
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_5",
                        "update": {
                            "sessionUpdate": "unknown_extension_update",
                            "value": "ignored",
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
        response, structured = await client.load_session_structured_updates(
            session_id="sess_5",
            cwd="/tmp",
            mcp_servers=[],
            transport="ws",
        )
        assert isinstance(response.result, dict)
        assert len(structured) == 2
        update_types = [update.sessionUpdate for update in structured]
        assert "session_info_update" in update_types
        assert "agent_message_chunk" in update_types
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
async def test_set_config_option_with_updates_returns_structured_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            assert payload["method"] == "session/set_config_option"
            assert payload["params"]["configId"] == "mode"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "sess_1",
                        "update": {
                            "sessionUpdate": "config_option_update",
                            "configOptions": [
                                {
                                    "id": "mode",
                                    "name": "Mode",
                                    "category": "mode",
                                    "type": "select",
                                    "currentValue": "code",
                                    "options": [{"value": "ask", "name": "Ask"}],
                                }
                            ],
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
                            "sessionUpdate": "current_mode_update",
                            "currentModeId": "code",
                        },
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {},
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
        response, updates = await client.set_config_option_with_updates(
            session_id="sess_1",
            config_id="mode",
            value="code",
            transport="ws",
        )
        assert isinstance(response.result, dict)
        update_types = [update.sessionUpdate for update in updates]
        assert "config_option_update" in update_types
        assert "current_mode_update" in update_types
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
