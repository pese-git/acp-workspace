from acp_server.messages import ACPMessage
from acp_server.protocol import ACPProtocol


def test_initialize_request() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request("initialize", {"protocolVersion": 1})

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is None
    assert outcome.response.result is not None
    assert outcome.response.result["protocolVersion"] == 1


def test_unknown_method() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request("missing", {})

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is not None
    assert outcome.response.error.code == -32601


def test_session_prompt_sends_update() -> None:
    protocol = ACPProtocol()

    new_session = protocol.handle(
        ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []})
    )
    assert new_session.response is not None
    assert isinstance(new_session.response.result, dict)
    session_id = new_session.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "hello"}],
            },
        )
    )

    assert outcome.response is not None
    assert outcome.response.result == {"stopReason": "end_turn"}
    update_types = [
        notification.params["update"]["sessionUpdate"]
        for notification in outcome.notifications
        if notification.params is not None
    ]
    assert "agent_message_chunk" in update_types
    assert "session_info_update" in update_types
    assert "available_commands_update" in update_types


def test_session_list_returns_created_session() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    listed = protocol.handle(ACPMessage.request("session/list", {}))
    assert listed.response is not None
    assert isinstance(listed.response.result, dict)
    sessions = listed.response.result["sessions"]
    assert isinstance(sessions, list)
    assert any(session["sessionId"] == created_id for session in sessions)


def test_set_config_option_updates_value() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    updated = protocol.handle(
        ACPMessage.request(
            "session/set_config_option",
            {
                "sessionId": created_id,
                "configId": "mode",
                "value": "code",
            },
        )
    )

    assert updated.response is not None
    assert isinstance(updated.response.result, dict)
    config_options = updated.response.result["configOptions"]
    mode = next(option for option in config_options if option["id"] == "mode")
    assert mode["currentValue"] == "code"
    assert len(updated.notifications) == 3
    assert updated.notifications[0].params is not None
    assert updated.notifications[0].params["update"]["sessionUpdate"] == "config_option_update"
    assert updated.notifications[1].params is not None
    assert updated.notifications[1].params["update"]["sessionUpdate"] == "current_mode_update"
    assert updated.notifications[2].params is not None
    assert updated.notifications[2].params["update"]["sessionUpdate"] == "session_info_update"


def test_prompt_rejects_unsupported_content_type() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": created_id,
                "prompt": [{"type": "audio", "data": "abc"}],
            },
        )
    )

    assert outcome.response is not None
    assert outcome.response.error is not None
    assert outcome.response.error.code == -32602


def test_prompt_can_emit_tool_call_updates() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": created_id,
                "prompt": [{"type": "text", "text": "run [tool] for me"}],
            },
        )
    )

    assert outcome.response is not None
    assert outcome.response.result == {"stopReason": "end_turn"}
    update_types = [
        notification.params["update"]["sessionUpdate"]
        for notification in outcome.notifications
        if notification.params is not None
    ]
    assert "tool_call" in update_types
    assert "tool_call_update" in update_types


def test_cancel_marks_active_tool_call_as_cancelled() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": created_id,
                "prompt": [{"type": "text", "text": "run [tool] with [tool-pending]"}],
            },
        )
    )
    assert prompt_outcome.response is not None

    tool_call_update = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.params is not None
        and notification.params["update"]["sessionUpdate"] == "tool_call_update"
    )
    assert tool_call_update.params is not None
    tool_call_id = tool_call_update.params["update"]["toolCallId"]

    cancel_outcome = protocol.handle(
        ACPMessage.notification("session/cancel", {"sessionId": created_id})
    )

    cancelled_updates = [
        notification
        for notification in cancel_outcome.notifications
        if notification.params is not None
        and notification.params["update"]["sessionUpdate"] == "tool_call_update"
        and notification.params["update"]["status"] == "cancelled"
    ]
    assert any(
        notification.params is not None
        and notification.params["update"]["toolCallId"] == tool_call_id
        for notification in cancelled_updates
    )


def test_session_load_replays_history_and_config() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompted = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "hello replay"}],
            },
        )
    )
    assert prompted.response is not None

    loaded = protocol.handle(
        ACPMessage.request(
            "session/load",
            {
                "sessionId": session_id,
                "cwd": "/tmp",
                "mcpServers": [],
            },
        )
    )

    assert loaded.response is not None
    assert loaded.response.result is None

    replay_updates = [
        notification.params["update"]["sessionUpdate"]
        for notification in loaded.notifications
        if notification.params is not None
    ]
    assert "user_message_chunk" in replay_updates
    assert "agent_message_chunk" in replay_updates
    assert "config_option_update" in replay_updates
    assert "session_info_update" in replay_updates
    assert "available_commands_update" in replay_updates


def test_session_load_replays_tool_call_state() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "run [tool] with [tool-pending]"}],
            },
        )
    )
    assert prompt_outcome.response is not None

    loaded = protocol.handle(
        ACPMessage.request(
            "session/load",
            {
                "sessionId": session_id,
                "cwd": "/tmp",
                "mcpServers": [],
            },
        )
    )
    assert loaded.response is not None

    replay_updates = [
        notification.params["update"]["sessionUpdate"]
        for notification in loaded.notifications
        if notification.params is not None
    ]
    assert "tool_call" in replay_updates
    assert "tool_call_update" in replay_updates
