from __future__ import annotations

from acp_client.tui.app import format_footer_error, format_retry_footer_error


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

    formatted = format_retry_footer_error(error)

    assert formatted == "Connected | Error | temporary network timeout | Ctrl+R retry"
