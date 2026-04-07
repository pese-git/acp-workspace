import pytest

from acp_client.messages import (
    ACPMessage,
    InitializeResult,
    JsonRpcError,
    PlanUpdate,
    RequestPermissionRequest,
    ToolCallCreatedUpdate,
    ToolCallStateUpdate,
    parse_initialize_result,
    parse_json_params,
    parse_plan_update,
    parse_request_permission_request,
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


def test_parse_request_permission_request() -> None:
    payload = {
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
    parsed = parse_request_permission_request(payload)
    assert isinstance(parsed, RequestPermissionRequest)
    assert parsed.id == "perm_1"
    assert parsed.params.options[0].optionId == "allow_once"


def test_parse_plan_update() -> None:
    notification = parse_session_update_notification(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "plan",
                    "entries": [
                        {
                            "content": "Подготовить изменения",
                            "priority": "high",
                            "status": "in_progress",
                        }
                    ],
                },
            },
        }
    )
    assert notification is not None

    parsed = parse_plan_update(notification)
    assert isinstance(parsed, PlanUpdate)
    assert parsed.entries[0].priority == "high"


def test_parse_initialize_result_success() -> None:
    response = ACPMessage.response(
        "init_1",
        {
            "protocolVersion": 1,
            "agentCapabilities": {
                "loadSession": True,
                "promptCapabilities": {"image": False},
                "mcpCapabilities": {"http": False, "sse": False},
                "sessionCapabilities": {"list": {}},
            },
            "agentInfo": {"name": "acp-server", "version": "0.1.0"},
            "authMethods": [],
        },
    )

    parsed = parse_initialize_result(response)
    assert isinstance(parsed, InitializeResult)
    assert parsed.protocolVersion == 1
    assert parsed.agentCapabilities.loadSession is True


def test_parse_initialize_result_error_response_raises() -> None:
    response = ACPMessage(
        id="init_1",
        error=JsonRpcError(code=-32602, message="Invalid params"),
    )

    with pytest.raises(ValueError):
        parse_initialize_result(response)
