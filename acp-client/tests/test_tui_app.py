from __future__ import annotations

from acp_client.tui.app import (
    ACPClientApp,
    ConnectionState,
    build_error_state_status,
    build_retry_skipped_status,
    build_retry_started_status,
    format_footer_error,
    format_footer_status,
    format_offline_footer_detail,
    format_retry_footer_error,
)


def test_format_footer_error_extracts_jsonrpc_code_and_reason() -> None:
    error = RuntimeError("WebSocket initialize failed: -32601 Method not found")

    formatted = format_footer_error(error, prefix="Connection error")

    assert "Connection error" in formatted
    assert "code=-32601" in formatted
    assert "Method not found" in formatted


def test_format_footer_error_handles_plain_error_message() -> None:
    error = RuntimeError("temporary network timeout")

    formatted = format_footer_error(error, prefix="Connected | Error")

    assert formatted == "Connected | Error | temporary network timeout"


def test_format_retry_footer_error_adds_retry_hint() -> None:
    error = RuntimeError("temporary network timeout")

    formatted = format_retry_footer_error(error, action_label="prompt", pending_count=2)

    assert formatted == "Error | temporary network timeout | Ctrl+R retry prompt | queued=2"


def test_failed_operations_queue_deduplicates_by_label() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)

    async def first_action() -> None:
        return None

    async def second_action() -> None:
        return None

    app._remember_failed_operation(label="prompt", action=first_action)  # noqa: SLF001
    app._remember_failed_operation(label="prompt", action=second_action)  # noqa: SLF001

    assert len(app._failed_operations) == 1  # noqa: SLF001
    failed_operation = app._pop_failed_operation()  # noqa: SLF001
    assert failed_operation is not None
    assert failed_operation.label == "prompt"


def test_failed_operations_queue_keeps_latest_five() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)

    async def retry_action() -> None:
        return None

    for index in range(6):
        app._remember_failed_operation(  # noqa: SLF001
            label=f"op_{index}",
            action=retry_action,
        )

    assert len(app._failed_operations) == 5  # noqa: SLF001
    assert app._failed_operations[0].label == "op_1"  # noqa: SLF001
    assert app._failed_operations[-1].label == "op_5"  # noqa: SLF001


def test_format_offline_footer_detail_includes_retry_hint() -> None:
    formatted = format_offline_footer_detail(reason="Prompt blocked: connection unavailable")

    assert formatted == "Prompt blocked: connection unavailable | Ctrl+R retry failed op"


def test_format_offline_footer_detail_uses_default_reason_when_empty() -> None:
    formatted = format_offline_footer_detail(reason="   ")

    assert formatted == "connection unavailable | Ctrl+R retry failed op"


def test_format_footer_status_builds_state_prefixed_line() -> None:
    formatted = format_footer_status(state=ConnectionState.OFFLINE, detail="connection unavailable")

    assert formatted == "Offline | connection unavailable"


def test_build_error_state_status_returns_offline_when_not_ready() -> None:
    error = RuntimeError("network timeout")

    state, detail = build_error_state_status(
        error,
        connection_ready=False,
        degraded_prefix="Error creating session",
    )

    assert state == ConnectionState.OFFLINE
    assert detail == "network timeout | Ctrl+R retry failed op"


def test_build_error_state_status_returns_degraded_with_prefix() -> None:
    error = RuntimeError("method failed")

    state, detail = build_error_state_status(
        error,
        connection_ready=True,
        degraded_prefix="Error switching session",
    )

    assert state == ConnectionState.DEGRADED
    assert detail == "Error switching session | method failed"


def test_build_error_state_status_adds_retry_hint_for_retryable_action() -> None:
    error = RuntimeError("temporary network timeout")

    state, detail = build_error_state_status(
        error,
        connection_ready=True,
        degraded_prefix="Error",
        include_retry_hint=True,
        retry_action_label="prompt",
        pending_count=2,
    )

    assert state == ConnectionState.DEGRADED
    assert detail == "Error | temporary network timeout | Ctrl+R retry prompt | queued=2"


def test_build_retry_skipped_status_returns_offline_when_disconnected() -> None:
    state, detail = build_retry_skipped_status(connection_ready=False)

    assert state == ConnectionState.OFFLINE
    assert detail == "Retry skipped: no failed operation | Ctrl+R retry failed op"


def test_build_retry_started_status_returns_reconnecting_when_disconnected() -> None:
    state, detail = build_retry_started_status(
        connection_ready=False,
        label="prompt",
        remaining_count=1,
    )

    assert state == ConnectionState.RECONNECTING
    assert detail == "Retrying failed operation: prompt (1 remaining)"
