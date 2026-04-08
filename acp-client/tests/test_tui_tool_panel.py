from __future__ import annotations

from acp_client.messages import ToolCallCreatedUpdate, ToolCallStateUpdate, ToolCallTerminalContent
from acp_client.tui.components.tool_panel import ToolPanel


def test_tool_panel_applies_created_and_state_updates() -> None:
    panel = ToolPanel()
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


def test_tool_panel_reset_clears_view() -> None:
    panel = ToolPanel()
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


def test_tool_panel_renders_terminal_id_and_output_excerpt() -> None:
    panel = ToolPanel()
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
