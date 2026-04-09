from __future__ import annotations

from typing import TYPE_CHECKING

from acp_client.messages import SessionListItem
from acp_client.tui.components.sidebar import Sidebar

if TYPE_CHECKING:
    from acp_client.presentation.session_view_model import SessionViewModel


def test_sidebar_syncs_selected_with_active_session(
    mock_session_view_model: SessionViewModel,
) -> None:
    sidebar = Sidebar(mock_session_view_model)
    sidebar.set_sessions(
        [
            SessionListItem(sessionId="sess_1", cwd="/tmp"),
            SessionListItem(sessionId="sess_2", cwd="/tmp"),
        ],
        active_session_id="sess_2",
    )

    assert sidebar.get_selected_session_id() == "sess_2"


def test_sidebar_select_next_and_previous_wraps(
    mock_session_view_model: SessionViewModel,
) -> None:
    sidebar = Sidebar(mock_session_view_model)
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


def test_sidebar_render_marks_selected_and_active_session(
    mock_session_view_model: SessionViewModel,
) -> None:
    sidebar = Sidebar(mock_session_view_model)
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
