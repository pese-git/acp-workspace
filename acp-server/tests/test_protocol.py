from acp_server.messages import ACPMessage
from acp_server.protocol import ACPProtocol


def _initialize_with_tool_runtime(protocol: ACPProtocol) -> None:
    """Инициализирует протокол с включенным tool-runtime capability profile."""

    init = protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": True,
                },
            },
        )
    )
    assert init.response is not None
    assert init.response.error is None


def test_initialize_request() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request(
        "initialize",
        {
            "protocolVersion": 1,
            "clientCapabilities": {},
        },
    )

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is None
    assert outcome.response.result is not None
    assert outcome.response.result["protocolVersion"] == 1


def test_initialize_negotiates_to_supported_version() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request(
        "initialize",
        {
            "protocolVersion": 999,
            "clientCapabilities": {},
        },
    )

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is None
    assert outcome.response.result is not None
    assert outcome.response.result["protocolVersion"] == 1


def test_initialize_rejects_non_integer_protocol_version() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request(
        "initialize",
        {
            "protocolVersion": "1",
            "clientCapabilities": {},
        },
    )

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is not None
    assert outcome.response.error.code == -32602


def test_initialize_requires_client_capabilities_object() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request("initialize", {"protocolVersion": 1})

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is not None
    assert outcome.response.error.code == -32602


def test_initialize_requires_protocol_version_field() -> None:
    protocol = ACPProtocol()
    request = ACPMessage.request("initialize", {"clientCapabilities": {}})

    outcome = protocol.handle(request)

    assert outcome.response is not None
    assert outcome.response.error is not None
    assert outcome.response.error.code == -32602


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


def test_prompt_with_plan_slash_command_emits_plan_update() -> None:
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
                "prompt": [{"type": "text", "text": "/plan build steps"}],
            },
        )
    )

    assert outcome.response is not None
    plan_updates = [
        notification
        for notification in outcome.notifications
        if notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "plan"
    ]
    assert len(plan_updates) == 1
    assert plan_updates[0].params is not None
    assert isinstance(plan_updates[0].params["update"].get("entries"), list)


def test_prompt_with_legacy_marker_does_not_emit_plan_update() -> None:
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
                "prompt": [{"type": "text", "text": "[plan] собрать шаги"}],
            },
        )
    )

    assert outcome.response is not None
    assert not any(
        notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "plan"
        for notification in outcome.notifications
    )


def test_session_new_returns_modes_state() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    assert isinstance(created.response.result.get("modes"), dict)
    assert created.response.result["modes"]["currentModeId"] == "ask"


def test_prompt_tool_flow_respects_negotiated_client_capabilities() -> None:
    protocol = ACPProtocol()
    init = protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
    )
    assert init.response is not None
    assert init.response.error is None

    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
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
    assert "tool_call" not in update_types


def test_prompt_tool_flow_requires_initialize_capability_negotiation() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
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
    assert "tool_call" not in update_types
    unavailable_messages = [
        notification.params["update"]["content"]["text"]
        for notification in outcome.notifications
        if notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "agent_message_chunk"
        and isinstance(notification.params["update"].get("content"), dict)
        and isinstance(notification.params["update"]["content"].get("text"), str)
    ]
    assert any("Tool runtime unavailable" in text for text in unavailable_messages)


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


def test_session_list_supports_cursor_pagination() -> None:
    protocol = ACPProtocol()
    for _ in range(51):
        created = protocol.handle(
            ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []})
        )
        assert created.response is not None

    first_page = protocol.handle(ACPMessage.request("session/list", {}))
    assert first_page.response is not None
    assert isinstance(first_page.response.result, dict)
    first_sessions = first_page.response.result["sessions"]
    next_cursor = first_page.response.result["nextCursor"]
    assert len(first_sessions) == 50
    assert isinstance(next_cursor, str)

    second_page = protocol.handle(ACPMessage.request("session/list", {"cursor": next_cursor}))
    assert second_page.response is not None
    assert isinstance(second_page.response.result, dict)
    second_sessions = second_page.response.result["sessions"]
    assert len(second_sessions) == 1
    assert second_page.response.result["nextCursor"] is None


def test_session_list_rejects_invalid_cursor() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None

    listed = protocol.handle(ACPMessage.request("session/list", {"cursor": "not-a-valid-cursor"}))
    assert listed.response is not None
    assert listed.response.error is not None
    assert listed.response.error.code == -32602


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
    assert isinstance(updated.response.result.get("modes"), dict)
    assert updated.response.result["modes"]["currentModeId"] == "code"
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
    _initialize_with_tool_runtime(protocol)
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

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": created_id,
                "prompt": [{"type": "text", "text": "/tool run for me"}],
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


def test_prompt_fs_read_emits_client_rpc_request_when_capability_enabled() -> None:
    protocol = ACPProtocol()
    initialized = protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
    )
    assert initialized.response is not None

    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/fs-read README.md"}],
            },
        )
    )

    assert outcome.response is None
    assert any(notification.method == "fs/read_text_file" for notification in outcome.notifications)


def test_fs_read_response_completes_turn_with_completed_tool_update() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/fs-read README.md"}],
            },
        )
    )
    assert prompt_outcome.response is None

    fs_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "fs/read_text_file"
    )
    assert fs_request.id is not None

    resolved = protocol.handle_client_response(
        ACPMessage.response(fs_request.id, {"content": "file-body"})
    )
    assert len(resolved.followup_responses) == 1
    assert resolved.followup_responses[0].result == {"stopReason": "end_turn"}
    assert any(
        notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "tool_call_update"
        and notification.params["update"].get("status") == "completed"
        for notification in resolved.notifications
    )


def test_fs_write_response_contains_diff_tool_content() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": True},
                    "terminal": False,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/fs-write notes.txt updated"}],
            },
        )
    )
    assert prompt_outcome.response is None

    fs_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "fs/write_text_file"
    )
    assert fs_request.id is not None

    resolved = protocol.handle_client_response(
        ACPMessage.response(
            fs_request.id,
            {
                "ok": True,
                "oldText": "before",
                "newText": "updated",
            },
        )
    )
    diff_updates = [
        notification
        for notification in resolved.notifications
        if notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "tool_call_update"
    ]
    assert len(diff_updates) >= 1
    assert diff_updates[0].params is not None
    content = diff_updates[0].params["update"].get("content")
    assert isinstance(content, list)
    assert content[0].get("type") == "diff"


def test_prompt_fs_read_without_capability_does_not_emit_fs_rpc() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/fs-read README.md"}],
            },
        )
    )

    assert outcome.response is not None
    assert outcome.response.result == {"stopReason": "end_turn"}
    assert all(notification.method != "fs/read_text_file" for notification in outcome.notifications)


def test_fs_read_client_error_marks_tool_as_failed() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": True, "writeTextFile": False},
                    "terminal": False,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/fs-read README.md"}],
            },
        )
    )
    assert prompt_outcome.response is None

    fs_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "fs/read_text_file"
    )
    assert fs_request.id is not None

    resolved = protocol.handle_client_response(
        ACPMessage.error_response(
            fs_request.id,
            code=-32000,
            message="read failed",
        )
    )
    assert len(resolved.followup_responses) == 1
    assert resolved.followup_responses[0].result == {"stopReason": "end_turn"}
    assert any(
        notification.params is not None and notification.params["update"].get("status") == "failed"
        for notification in resolved.notifications
    )


def test_prompt_terminal_run_emits_terminal_create_request() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": True,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/term-run ls -la"}],
            },
        )
    )
    assert outcome.response is None
    assert any(notification.method == "terminal/create" for notification in outcome.notifications)


def test_terminal_rpc_chain_completes_prompt_turn() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": True,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/term-run ls"}],
            },
        )
    )
    assert prompt_outcome.response is None

    create_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "terminal/create"
    )
    assert create_request.id is not None

    output_step = protocol.handle_client_response(
        ACPMessage.response(create_request.id, {"terminalId": "term_1"})
    )
    output_request = next(
        notification
        for notification in output_step.notifications
        if notification.method == "terminal/output"
    )
    assert output_request.id is not None

    wait_step = protocol.handle_client_response(
        ACPMessage.response(output_request.id, {"output": "hello"})
    )
    wait_request = next(
        notification
        for notification in wait_step.notifications
        if notification.method == "terminal/wait_for_exit"
    )
    assert wait_request.id is not None

    release_step = protocol.handle_client_response(
        ACPMessage.response(wait_request.id, {"exitCode": 0})
    )
    release_request = next(
        notification
        for notification in release_step.notifications
        if notification.method == "terminal/release"
    )
    assert release_request.id is not None

    done = protocol.handle_client_response(ACPMessage.response(release_request.id, {"ok": True}))
    assert len(done.followup_responses) == 1
    assert done.followup_responses[0].result == {"stopReason": "end_turn"}
    assert any(
        notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "tool_call_update"
        and notification.params["update"].get("status") == "completed"
        for notification in done.notifications
    )


def test_cancel_during_terminal_flow_emits_kill_and_release_requests() -> None:
    protocol = ACPProtocol()
    protocol.handle(
        ACPMessage.request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": True,
                },
            },
        )
    )
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/term-run sleep 10"}],
            },
        )
    )
    assert prompt_outcome.response is None
    create_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "terminal/create"
    )
    assert create_request.id is not None

    _ = protocol.handle_client_response(
        ACPMessage.response(create_request.id, {"terminalId": "term_1"})
    )

    cancel_outcome = protocol.handle(
        ACPMessage.request(
            "session/cancel",
            {
                "sessionId": session_id,
            },
        )
    )
    methods = [notification.method for notification in cancel_outcome.notifications]
    assert "terminal/kill" in methods
    assert "terminal/release" in methods


def test_cancel_marks_active_tool_call_as_cancelled() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    created_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": created_id,
                "prompt": [{"type": "text", "text": "/tool-pending run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    tool_call_created = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.params is not None
        and notification.params["update"]["sessionUpdate"] == "tool_call"
    )
    assert tool_call_created.params is not None
    tool_call_id = tool_call_created.params["update"]["toolCallId"]

    cancel_outcome = protocol.handle(
        ACPMessage.notification("session/cancel", {"sessionId": created_id})
    )

    assert len(cancel_outcome.followup_responses) == 1
    assert cancel_outcome.followup_responses[0].result == {"stopReason": "cancelled"}

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


def test_deferred_prompt_can_be_completed_without_cancel() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool-pending run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    completed_response = protocol.complete_active_turn(session_id, stop_reason="end_turn")
    assert completed_response is not None
    assert completed_response.result == {"stopReason": "end_turn"}


def test_prompt_with_tool_pending_slash_command_defers_turn() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    # Переключаемся в mode=code, чтобы не уходить в permission-flow и проверить defer tool-call.
    updated = protocol.handle(
        ACPMessage.request(
            "session/set_config_option",
            {
                "sessionId": session_id,
                "configId": "mode",
                "value": "code",
            },
        )
    )
    assert updated.response is not None

    outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool-pending выполнить"}],
            },
        )
    )

    assert outcome.response is None
    assert any(
        notification.params is not None
        and notification.params["update"].get("sessionUpdate") == "tool_call"
        for notification in outcome.notifications
    )


def test_permission_selected_completes_prompt_turn() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    permission_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "session/request_permission"
    )
    assert permission_request.id is not None
    assert permission_request.params is not None
    options = permission_request.params["options"]
    assert isinstance(options, list)
    assert any(
        isinstance(option, dict) and option.get("kind") == "reject_once" for option in options
    )

    resolved = protocol.handle_client_response(
        ACPMessage.response(
            permission_request.id,
            {
                "outcome": {
                    "outcome": "selected",
                    "optionId": "allow_once",
                },
            },
        )
    )
    assert len(resolved.followup_responses) == 1
    assert resolved.followup_responses[0].result == {"stopReason": "end_turn"}


def test_permission_cancelled_finishes_turn_with_cancelled() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    permission_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "session/request_permission"
    )
    assert permission_request.id is not None

    resolved = protocol.handle_client_response(
        ACPMessage.response(
            permission_request.id,
            {"outcome": {"outcome": "cancelled"}},
        )
    )
    assert len(resolved.followup_responses) == 1
    assert resolved.followup_responses[0].result == {"stopReason": "cancelled"}


def test_permission_reject_option_finishes_turn_with_cancelled() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    permission_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "session/request_permission"
    )
    assert permission_request.id is not None

    resolved = protocol.handle_client_response(
        ACPMessage.response(
            permission_request.id,
            {"outcome": {"outcome": "selected", "optionId": "reject_once"}},
        )
    )
    assert len(resolved.followup_responses) == 1
    assert resolved.followup_responses[0].result == {"stopReason": "cancelled"}


def test_late_permission_response_after_cancel_is_ignored() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool run"}],
            },
        )
    )
    assert prompt_outcome.response is None

    permission_request = next(
        notification
        for notification in prompt_outcome.notifications
        if notification.method == "session/request_permission"
    )
    assert permission_request.id is not None

    cancel_outcome = protocol.handle(
        ACPMessage.notification("session/cancel", {"sessionId": session_id})
    )
    assert len(cancel_outcome.followup_responses) == 1
    assert cancel_outcome.followup_responses[0].result == {"stopReason": "cancelled"}

    late_permission = protocol.handle_client_response(
        ACPMessage.response(
            permission_request.id,
            {
                "outcome": {
                    "outcome": "selected",
                    "optionId": "allow_once",
                },
            },
        )
    )
    assert late_permission.notifications == []
    assert late_permission.followup_responses == []

    next_prompt = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "normal prompt"}],
            },
        )
    )
    assert next_prompt.response is not None
    assert next_prompt.response.result == {"stopReason": "end_turn"}


def test_cancel_without_active_turn_does_not_affect_next_prompt() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    cancel_outcome = protocol.handle(
        ACPMessage.notification("session/cancel", {"sessionId": session_id})
    )
    assert cancel_outcome.response is None

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "normal prompt"}],
            },
        )
    )
    assert prompt_outcome.response is not None
    assert prompt_outcome.response.result == {"stopReason": "end_turn"}


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
    assert isinstance(loaded.response.result, dict)
    assert "configOptions" in loaded.response.result
    assert isinstance(loaded.response.result.get("modes"), dict)

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


def test_session_load_replays_last_plan_update() -> None:
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
                "prompt": [{"type": "text", "text": "/plan compose"}],
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
    replay_updates = [
        notification.params["update"]["sessionUpdate"]
        for notification in loaded.notifications
        if notification.params is not None
    ]
    assert "plan" in replay_updates


def test_session_set_mode_updates_current_mode() -> None:
    protocol = ACPProtocol()
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    outcome = protocol.handle(
        ACPMessage.request(
            "session/set_mode",
            {
                "sessionId": session_id,
                "modeId": "code",
            },
        )
    )

    assert outcome.response is not None
    assert outcome.response.result == {}
    update_types = [
        notification.params["update"]["sessionUpdate"]
        for notification in outcome.notifications
        if notification.params is not None
    ]
    assert "current_mode_update" in update_types


def test_session_load_replays_tool_call_state() -> None:
    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    prompt_outcome = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool-pending run"}],
            },
        )
    )
    assert prompt_outcome.response is None

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
