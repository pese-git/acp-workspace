from __future__ import annotations

from acp_client.tui.managers.handlers import UpdateMessageHandler


def test_update_handler_routes_agent_and_user_text_chunks() -> None:
    received_agent: list[str] = []
    received_user: list[str] = []

    handler = UpdateMessageHandler(
        on_agent_chunk=received_agent.append,
        on_user_chunk=received_user.append,
    )

    handler.handle(
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
    handler.handle(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "user_message_chunk",
                    "content": {"type": "text", "text": "world"},
                },
            },
        }
    )

    assert received_agent == ["hello"]
    assert received_user == ["world"]


def test_update_handler_ignores_non_text_content() -> None:
    received_agent: list[str] = []

    handler = UpdateMessageHandler(
        on_agent_chunk=received_agent.append,
        on_user_chunk=lambda _text: None,
    )

    handler.handle(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "image", "data": "...", "mimeType": "image/png"},
                },
            },
        }
    )

    assert received_agent == []
