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


async def _maybe_reply_initialize(ws: web.WebSocketResponse, payload: dict) -> bool:
    """Отвечает на `initialize` в mock WS-сервере, если запрос пришел.

    Возвращает `True`, если payload обработан как initialize.
    """

    if payload.get("method") != "initialize":
        return False
    await ws.send_json(
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
    return True


@pytest.mark.asyncio
async def test_load_session_helper_collects_replay_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            on_update=updates.append,
        )
        assert response.result == {"stopReason": "end_turn"}
        assert len(updates) == 1
        assert updates[0]["method"] == "session/update"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_initializes_before_session_methods() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        step = 0
        async for message in ws:
            payload = json.loads(message.data)
            if step == 0:
                assert payload["method"] == "initialize"
                assert payload["params"]["clientCapabilities"] == {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                }
                await ws.send_json(
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
                step = 1
                continue

            assert payload["method"] == "session/list"
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "sessions": [],
                        "nextCursor": None,
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
        response = await client.request(method="session/list", params={})
        assert isinstance(response.result, dict)
        assert response.result["sessions"] == []
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_does_not_initialize_before_non_session_method() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for message in ws:
            payload = json.loads(message.data)
            assert payload["method"] == "ping"
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"pong": True},
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
        response = await client.request(method="ping")
        assert response.result == {"pong": True}
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_set_config_option_with_updates_returns_structured_updates() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            if await _maybe_reply_initialize(ws, payload):
                continue
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
            if await _maybe_reply_initialize(ws, prompt_payload):
                continue
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
            assert permission_response["result"]["outcome"]["outcome"] == "selected"
            assert permission_response["result"]["outcome"]["optionId"] == "allow_once"

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
            on_permission=choose_permission,
        )

        assert response.result == {"stopReason": "end_turn"}
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_handles_fs_read_request() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            prompt_payload = json.loads(message.data)
            if await _maybe_reply_initialize(ws, prompt_payload):
                continue
            assert prompt_payload["method"] == "session/prompt"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "fs_1",
                    "method": "fs/read_text_file",
                    "params": {
                        "sessionId": "sess_1",
                        "path": "/tmp/demo.txt",
                    },
                }
            )

            fs_response = await ws.receive_json()
            assert fs_response["id"] == "fs_1"
            assert fs_response["result"]["content"] == "demo-body"

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

        response = await client.request(
            method="session/prompt",
            params={"sessionId": "sess_1", "prompt": [{"type": "text", "text": "/fs-read"}]},
            on_fs_read=lambda _path: "demo-body",
        )

        assert response.result == {"stopReason": "end_turn"}
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_handles_fs_write_request() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            prompt_payload = json.loads(message.data)
            if await _maybe_reply_initialize(ws, prompt_payload):
                continue
            assert prompt_payload["method"] == "session/prompt"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "fs_2",
                    "method": "fs/write_text_file",
                    "params": {
                        "sessionId": "sess_1",
                        "path": "/tmp/demo.txt",
                        "content": "new-text",
                    },
                }
            )

            fs_response = await ws.receive_json()
            assert fs_response["id"] == "fs_2"
            assert fs_response["result"]["ok"] is True
            assert fs_response["result"]["oldText"] == "old-text"
            assert fs_response["result"]["newText"] == "new-text"

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

        response = await client.request(
            method="session/prompt",
            params={"sessionId": "sess_1", "prompt": [{"type": "text", "text": "/fs-write"}]},
            on_fs_write=lambda _path, _content: "old-text",
        )

        assert response.result == {"stopReason": "end_turn"}
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_ws_client_handles_terminal_requests() -> None:
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            prompt_payload = json.loads(message.data)
            if await _maybe_reply_initialize(ws, prompt_payload):
                continue
            assert prompt_payload["method"] == "session/prompt"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "term_create_1",
                    "method": "terminal/create",
                    "params": {
                        "sessionId": "sess_1",
                        "command": "ls",
                    },
                }
            )
            create_response = await ws.receive_json()
            assert create_response["id"] == "term_create_1"
            assert create_response["result"]["terminalId"] == "term_1"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "term_output_1",
                    "method": "terminal/output",
                    "params": {
                        "sessionId": "sess_1",
                        "terminalId": "term_1",
                    },
                }
            )
            output_response = await ws.receive_json()
            assert output_response["id"] == "term_output_1"
            assert output_response["result"]["output"] == "line-1"

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "term_wait_1",
                    "method": "terminal/wait_for_exit",
                    "params": {
                        "sessionId": "sess_1",
                        "terminalId": "term_1",
                    },
                }
            )
            wait_response = await ws.receive_json()
            assert wait_response["id"] == "term_wait_1"
            assert wait_response["result"]["exitCode"] == 0

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": "term_release_1",
                    "method": "terminal/release",
                    "params": {
                        "sessionId": "sess_1",
                        "terminalId": "term_1",
                    },
                }
            )
            release_response = await ws.receive_json()
            assert release_response["id"] == "term_release_1"
            assert release_response["result"]["ok"] is True

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

    released_terminal_ids: list[str] = []

    try:
        client = ACPClient(host="127.0.0.1", port=port)

        response = await client.request(
            method="session/prompt",
            params={"sessionId": "sess_1", "prompt": [{"type": "text", "text": "/term-run"}]},
            on_terminal_create=lambda _command: "term_1",
            on_terminal_output=lambda _terminal_id: "line-1",
            on_terminal_wait_for_exit=lambda _terminal_id: 0,
            on_terminal_release=lambda terminal_id: released_terminal_ids.append(terminal_id),
            on_terminal_kill=lambda _terminal_id: True,
        )

        assert response.result == {"stopReason": "end_turn"}
        assert released_terminal_ids == ["term_1"]
    finally:
        await runner.cleanup()
