"""Левая панель с краткой информацией о сессиях."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import Static

from acp_client.messages import SessionListItem


class Sidebar(Static):
    """Упрощенная панель сессий для MVP-alpha."""

    can_focus = True

    class SessionSelected(Message):
        """Событие выбора сессии по Enter в sidebar."""

        def __init__(self, session_id: str) -> None:
            """Сохраняет идентификатор выбранной сессии."""

            super().__init__()
            self.session_id = session_id

    def __init__(self) -> None:
        """Создает sidebar с начальным placeholder состоянием."""

        super().__init__("Сессии загружаются...", id="sidebar")
        self._sessions: list[SessionListItem] = []
        self._active_session_id: str | None = None
        self._selected_index: int = 0

    def set_sessions(self, sessions: list[SessionListItem], active_session_id: str | None) -> None:
        """Сохраняет текущий список сессий и активную сессию."""

        self._sessions = sessions
        self._active_session_id = active_session_id
        self._sync_selected_index()
        self.update(self._render_text())

    def select_next(self) -> None:
        """Смещает выделение к следующей сессии и обновляет вид."""

        if not self._sessions:
            return
        self._selected_index += 1
        if self._selected_index >= len(self._sessions):
            self._selected_index = 0
        self.update(self._render_text())

    def select_previous(self) -> None:
        """Смещает выделение к предыдущей сессии и обновляет вид."""

        if not self._sessions:
            return
        self._selected_index -= 1
        if self._selected_index < 0:
            self._selected_index = len(self._sessions) - 1
        self.update(self._render_text())

    def get_selected_session_id(self) -> str | None:
        """Возвращает sessionId для текущей выделенной строки."""

        if not self._sessions:
            return None
        return self._sessions[self._selected_index].sessionId

    def on_key(self, event: events.Key) -> None:
        """Обрабатывает управление выбором сессии с клавиатуры."""

        if event.key == "up":
            self.select_previous()
            event.stop()
            return
        if event.key == "down":
            self.select_next()
            event.stop()
            return
        if event.key == "enter":
            selected_session_id = self.get_selected_session_id()
            if selected_session_id is not None:
                self.post_message(self.SessionSelected(selected_session_id))
                event.stop()

    def _render_text(self) -> str:
        """Формирует текстовое представление списка сессий."""

        if not self._sessions:
            return "Сессий пока нет"

        lines: list[str] = ["Сессии (Up/Down + Enter):"]
        for index, session in enumerate(self._sessions[:10]):
            marker = "*" if session.sessionId == self._active_session_id else " "
            cursor = ">" if index == self._selected_index else " "
            title = session.title or session.sessionId
            lines.append(f"{cursor}{marker} {title}")
        return "\n".join(lines)

    def _sync_selected_index(self) -> None:
        """Синхронизирует выделение с активной сессией после refresh списка."""

        if not self._sessions:
            self._selected_index = 0
            return
        if self._active_session_id is None:
            self._selected_index = 0
            return
        for index, session in enumerate(self._sessions):
            if session.sessionId == self._active_session_id:
                self._selected_index = index
                return
        self._selected_index = 0
