from acp_server.messages import ACPMessage
from acp_server.protocol import ACPProtocol


def _initialize_with_tool_runtime(protocol: ACPProtocol) -> None:
    """Инициализирует capability profile, разрешающий tool-runtime сценарии."""

    initialized = protocol.handle(
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
    assert initialized.response is not None
    assert initialized.response.error is None


def test_conformance_prompt_returns_end_turn_with_agent_update() -> None:
    """Проверяет базовый ACP prompt-cycle: update-поток + финальный end_turn."""

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
                "prompt": [{"type": "text", "text": "hello"}],
            },
        )
    )

    assert prompted.response is not None
    assert prompted.response.result == {"stopReason": "end_turn"}
    update_types = [
        notification.params["update"]["sessionUpdate"]
        for notification in prompted.notifications
        if notification.params is not None
    ]
    assert "agent_message_chunk" in update_types


def test_conformance_cancel_while_waiting_permission_returns_cancelled() -> None:
    """Проверяет обязательный ACP-инвариант: cancel завершает turn как cancelled."""

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

    cancel_outcome = protocol.handle(
        ACPMessage.notification("session/cancel", {"sessionId": session_id})
    )
    assert len(cancel_outcome.followup_responses) == 1
    assert cancel_outcome.followup_responses[0].result == {"stopReason": "cancelled"}


def test_conformance_permission_selected_completes_turn() -> None:
    """Проверяет ACP permission-flow: selected/allow завершает turn как end_turn."""

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

    permission_resolved = protocol.handle_client_response(
        ACPMessage.response(
            permission_request.id,
            {
                "outcome": {
                    "outcome": "selected",
                    "optionId": "allow_once",
                }
            },
        )
    )
    assert len(permission_resolved.followup_responses) == 1
    assert permission_resolved.followup_responses[0].result == {"stopReason": "end_turn"}


def test_conformance_load_replays_history_and_stateful_updates() -> None:
    """Проверяет load replay для истории, plan и tool call состояния."""

    protocol = ACPProtocol()
    _initialize_with_tool_runtime(protocol)
    created = protocol.handle(ACPMessage.request("session/new", {"cwd": "/tmp", "mcpServers": []}))
    assert created.response is not None
    assert isinstance(created.response.result, dict)
    session_id = created.response.result["sessionId"]

    _ = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/plan release checklist"}],
            },
        )
    )
    _ = protocol.handle(
        ACPMessage.request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": "/tool-pending run"}],
            },
        )
    )

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

    replay_types = [
        notification.params["update"]["sessionUpdate"]
        for notification in loaded.notifications
        if notification.params is not None
    ]
    assert "user_message_chunk" in replay_types
    assert "agent_message_chunk" in replay_types
    assert "plan" in replay_types
    assert "tool_call" in replay_types
