from __future__ import annotations

from acp_client.tui.components.terminal_output import TerminalOutputPanel


def test_terminal_output_panel_renders_empty_state() -> None:
    panel = TerminalOutputPanel()

    rendered = panel.render_text()

    assert rendered.plain == "Нет вывода терминала"  # type: ignore[attr-defined]


def test_terminal_output_panel_renders_output_and_exit_code() -> None:
    panel = TerminalOutputPanel()
    panel.append_output("hello\n")
    panel.set_exit_code(0)

    rendered = panel.render_text()

    assert "hello" in rendered.plain  # type: ignore[attr-defined]
    assert "Exit code: 0" in rendered.plain  # type: ignore[attr-defined]
