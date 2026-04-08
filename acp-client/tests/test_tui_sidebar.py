from __future__ import annotations

from acp_client.messages import SessionListItem
from acp_client.tui.components.sidebar import Sidebar


def test_sidebar_syncs_selected_with_active_session() -> None:
    sidebar = Sidebar()
    sidebar.set_sessions(
        [
            SessionListItem(sessionId="sess_1", cwd="/tmp"),
            SessionListItem(sessionId="sess_2", cwd="/tmp"),
        ],
        active_session_id="sess_2",
    )

    assert sidebar.get_selected_session_id() == "sess_2"


def test_sidebar_select_next_and_previous_wraps() -> None:
    sidebar = Sidebar()
    sidebar.set_sessions(
        [
            SessionListItem(sessionId="sess_1", cwd="/tmp"),
            SessionListItem(sessionId="sess_2", cwd="/tmp"),
        ],
        active_session_id="sess_1",
    )

    sidebar.select_next()
    assert sidebar.get_selected_session_id() == "sess_2"

    sidebar.select_next()
    assert sidebar.get_selected_session_id() == "sess_1"

    sidebar.select_previous()
    assert sidebar.get_selected_session_id() == "sess_2"


def test_sidebar_render_marks_selected_and_active_session() -> None:
    sidebar = Sidebar()
    sidebar.set_sessions(
        [
            SessionListItem(sessionId="sess_1", cwd="/tmp", title="One"),
            SessionListItem(sessionId="sess_2", cwd="/tmp", title="Two"),
        ],
        active_session_id="sess_1",
    )

    rendered = sidebar._render_text()  # noqa: SLF001

    assert "Сессии (Up/Down + Enter):" in rendered
    assert ">* One" in rendered
