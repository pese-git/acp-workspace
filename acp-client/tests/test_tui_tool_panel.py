from __future__ import annotations

from typing import TYPE_CHECKING

from acp_client.messages import ToolCallCreatedUpdate, ToolCallStateUpdate, ToolCallTerminalContent
from acp_client.tui.components.tool_panel import ToolPanel

if TYPE_CHECKING:
    from acp_client.presentation.chat_view_model import ChatViewModel


def test_tool_panel_applies_created_and_state_updates(
    mock_chat_view_model: ChatViewModel,
) -> None:
    panel = ToolPanel(mock_chat_view_model)
    panel.apply_update(
        ToolCallCreatedUpdate(
            sessionUpdate="tool_call",
            toolCallId="call_1",
            title="Read file",
            status="pending",
        )
    )
    panel.apply_update(
        ToolCallStateUpdate(
            sessionUpdate="tool_call_update",
            toolCallId="call_1",
            status="completed",
        )
    )

    rendered = panel._render_text()  # noqa: SLF001

    assert "Read file [completed] (call_1)" in rendered


def test_tool_panel_reset_clears_view(
    mock_chat_view_model: ChatViewModel,
) -> None:
    panel = ToolPanel(mock_chat_view_model)
    panel.apply_update(
        ToolCallCreatedUpdate(
            sessionUpdate="tool_call",
            toolCallId="call_1",
            title="Read file",
            status="pending",
        )
    )

    panel.reset()

    assert panel._render_text() == "Инструменты: нет активных вызовов"  # noqa: SLF001


def test_tool_panel_renders_terminal_id_and_output_excerpt(
    mock_chat_view_model: ChatViewModel,
) -> None:
    panel = ToolPanel(mock_chat_view_model)
    panel.apply_update(
        ToolCallCreatedUpdate(
            sessionUpdate="tool_call",
            toolCallId="call_1",
            title="Run command",
            status="in_progress",
            content=[ToolCallTerminalContent(type="terminal", terminalId="term_1")],
        )
    )
    panel.apply_update(
        ToolCallStateUpdate(
            sessionUpdate="tool_call_update",
            toolCallId="call_1",
            status="completed",
            rawOutput={"output": "line1\nline2\n", "exitCode": 0},
        )
    )

    rendered = panel._render_text()  # noqa: SLF001

    assert "terminal: term_1" in rendered
    assert "output: line1 line2 Exit code: 0" in rendered


def test_tool_panel_returns_latest_terminal_snapshot(
    mock_chat_view_model: ChatViewModel,
) -> None:
    panel = ToolPanel(mock_chat_view_model)
    panel.apply_update(
        ToolCallCreatedUpdate(
            sessionUpdate="tool_call",
            toolCallId="call_1",
            title="Run command",
            status="in_progress",
            content=[ToolCallTerminalContent(type="terminal", terminalId="term_9")],
        )
    )
    panel.apply_update(
        ToolCallStateUpdate(
            sessionUpdate="tool_call_update",
            toolCallId="call_1",
            status="completed",
            rawOutput={"output": "done\n", "exitCode": 0},
        )
    )

    snapshot = panel.latest_terminal_snapshot()

    assert snapshot is not None
    title, terminal_id, output = snapshot
    assert title == "Run command"
    assert terminal_id == "term_9"
    assert "done" in output.plain  # type: ignore[attr-defined]
