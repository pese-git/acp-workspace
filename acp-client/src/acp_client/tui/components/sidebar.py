"""Левая панель с краткой информацией о сессиях."""

from __future__ import annotations

from textual.widgets import Static

from acp_client.messages import SessionListItem


class Sidebar(Static):
    """Упрощенная панель сессий для MVP-alpha."""

    def __init__(self) -> None:
        """Создает sidebar с начальным placeholder состоянием."""

        super().__init__("Сессии загружаются...", id="sidebar")
        self._sessions: list[SessionListItem] = []
        self._active_session_id: str | None = None

    def set_sessions(self, sessions: list[SessionListItem], active_session_id: str | None) -> None:
        """Сохраняет текущий список сессий и активную сессию."""

        self._sessions = sessions
        self._active_session_id = active_session_id
        self.update(self._render_text())

    def _render_text(self) -> str:
        """Формирует текстовое представление списка сессий."""

        if not self._sessions:
            return "Сессий пока нет"

        lines: list[str] = ["Сессии:"]
        for session in self._sessions[:10]:
            marker = "*" if session.sessionId == self._active_session_id else " "
            title = session.title or session.sessionId
            lines.append(f"{marker} {title}")
        return "\n".join(lines)
