import pytest

from acp_client.messages import (
    ACPMessage,
    ToolCallCreatedUpdate,
    ToolCallStateUpdate,
    parse_json_params,
    parse_session_update_notification,
    parse_tool_call_update,
)


def test_parse_json_params_object() -> None:
    params = parse_json_params('{"x":1,"y":"ok"}')
    assert params == {"x": 1, "y": "ok"}


def test_parse_json_params_requires_object() -> None:
    with pytest.raises(ValueError):
        parse_json_params("[1, 2]")


def test_message_to_from_dict() -> None:
    request = ACPMessage.request(method="ping", params={})
    restored = ACPMessage.from_dict(request.to_dict())
    assert restored.method == "ping"


def test_parse_session_update_notification() -> None:
    payload = {
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
    parsed = parse_session_update_notification(payload)
    assert parsed is not None
    assert parsed.params.sessionId == "sess_1"
    assert parsed.params.update.sessionUpdate == "agent_message_chunk"


def test_parse_session_update_notification_ignores_other_methods() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": "req_1",
        "result": {},
    }
    parsed = parse_session_update_notification(payload)
    assert parsed is None


def test_parse_tool_call_created_update() -> None:
    notification = parse_session_update_notification(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
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
    assert notification is not None

    parsed = parse_tool_call_update(notification)
    assert isinstance(parsed, ToolCallCreatedUpdate)
    assert parsed.toolCallId == "call_001"


def test_parse_tool_call_state_update() -> None:
    notification = parse_session_update_notification(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": "call_001",
                    "status": "completed",
                    "content": [
                        {
                            "type": "content",
                            "content": {"type": "text", "text": "ok"},
                        }
                    ],
                },
            },
        }
    )
    assert notification is not None

    parsed = parse_tool_call_update(notification)
    assert isinstance(parsed, ToolCallStateUpdate)
    assert parsed.status == "completed"
