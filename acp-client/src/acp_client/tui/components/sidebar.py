"""Левая панель с краткой информацией о сессиях с MVVM интеграцией.

Отвечает за:
- Отображение списка сессий из SessionViewModel
- Навигацию по сессиям (Up/Down)
- Выбор сессии (Enter)
- Реактивные обновления при изменении состояния
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual import events
from textual.message import Message
from textual.widgets import Static

if TYPE_CHECKING:
    from acp_client.presentation.session_view_model import SessionViewModel


class Sidebar(Static):
    """Панель сессий с MVVM интеграцией.

    Обязательно требует SessionViewModel для работы. Подписывается на Observable свойства:
    - sessions: список доступных сессий
    - selected_session_id: текущая выбранная сессия
    - is_loading_sessions: флаг загрузки сессий

    Примеры использования:
        >>> from acp_client.presentation.session_view_model import SessionViewModel
        >>> session_vm = SessionViewModel(coordinator, event_bus)
        >>> sidebar = Sidebar(session_vm)
        >>>
        >>> # Когда SessionViewModel обновляется, sidebar обновляется автоматически
        >>> session_vm.sessions.value = [session1, session2]
    """

    can_focus = True

    class SessionSelected(Message):
        """Событие выбора сессии по Enter в sidebar."""

        def __init__(self, session_id: str) -> None:
            """Сохраняет идентификатор выбранной сессии."""
            super().__init__()
            self.session_id = session_id

    def __init__(self, session_vm: SessionViewModel) -> None:
        """Инициализирует Sidebar с обязательным SessionViewModel.

        Args:
            session_vm: SessionViewModel для управления состоянием сессий
        """
        super().__init__("", id="sidebar")
        self.session_vm = session_vm
        self._selected_index: int = 0

        # Подписываемся на изменения в SessionViewModel
        self.session_vm.sessions.subscribe(self._on_sessions_changed)
        self.session_vm.selected_session_id.subscribe(self._on_selected_session_changed)
        self.session_vm.is_loading_sessions.subscribe(self._on_loading_changed)

        # Инициализируем UI с текущим состоянием
        self._update_display()

    def _on_sessions_changed(self, sessions: list) -> None:
        """Обновить sidebar при изменении списка сессий.

        Args:
            sessions: Новый список сессий
        """
        # Синхронизировать выделение с выбранной сессией
        self._sync_selected_index()
        self._update_display()

    def _on_selected_session_changed(self, session_id: str | None) -> None:
        """Обновить sidebar при изменении выбранной сессии.

        Args:
            session_id: ID выбранной сессии или None
        """
        self._sync_selected_index()
        self._update_display()

    def _on_loading_changed(self, is_loading: bool) -> None:
        """Обновить sidebar при изменении статуса загрузки.

        Args:
            is_loading: True если идет загрузка, False иначе
        """
        self._update_display()

    def _update_display(self) -> None:
        """Обновить отображение sidebar'а на основе текущего состояния."""
        self.update(self._render_text())

    def select_next(self) -> None:
        """Смещает выделение к следующей сессии."""
        sessions = self.session_vm.sessions.value
        if not sessions:
            return

        self._selected_index += 1
        if self._selected_index >= len(sessions):
            self._selected_index = 0

        # Обновить выбранную сессию в ViewModel
        self._update_selected_session()

    def select_previous(self) -> None:
        """Смещает выделение к предыдущей сессии."""
        sessions = self.session_vm.sessions.value
        if not sessions:
            return

        self._selected_index -= 1
        if self._selected_index < 0:
            self._selected_index = len(sessions) - 1

        # Обновить выбранную сессию в ViewModel
        self._update_selected_session()

    def get_selected_session_id(self) -> str | None:
        """Возвращает sessionId для текущей выделенной строки."""
        sessions = self.session_vm.sessions.value
        if not sessions or self._selected_index >= len(sessions):
            return None
        return self._extract_session_id(sessions[self._selected_index])

    def _update_selected_session(self) -> None:
        """Обновить выбранную сессию в ViewModel."""
        selected_id = self.get_selected_session_id()
        if selected_id is not None:
            self.session_vm.selected_session_id.value = selected_id
            self._update_display()

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
        sessions = self.session_vm.sessions.value
        is_loading = self.session_vm.is_loading_sessions.value
        selected_id = self.session_vm.selected_session_id.value

        if is_loading:
            return "Сессии загружаются..."

        if not sessions:
            return "Сессий пока нет"

        lines: list[str] = ["Сессии (Up/Down + Enter):"]
        for index, session in enumerate(sessions[:10]):
            session_id = self._extract_session_id(session)
            marker = "*" if session_id == selected_id else " "
            cursor = ">" if index == self._selected_index else " "
            title = self._extract_session_title(session)
            lines.append(f"{cursor}{marker} {title}")
        return "\n".join(lines)

    def _sync_selected_index(self) -> None:
        """Синхронизирует выделение с выбранной сессией из ViewModel."""
        sessions = self.session_vm.sessions.value
        selected_id = self.session_vm.selected_session_id.value

        if not sessions:
            self._selected_index = 0
            return

        if selected_id is None:
            self._selected_index = 0
            return

        # Найти индекс выбранной сессии
        for index, session in enumerate(sessions):
            if self._extract_session_id(session) == selected_id:
                self._selected_index = index
                return

        # Если не нашли, выбрать первую
        self._selected_index = 0

    @staticmethod
    def _extract_session_id(session: Any) -> str | None:
        """Возвращает идентификатор сессии из dict/DTO/entity объектов."""

        if isinstance(session, dict):
            raw_id = session.get("sessionId") or session.get("id")
            return raw_id if isinstance(raw_id, str) else None

        for attribute_name in ("sessionId", "id"):
            if hasattr(session, attribute_name):
                raw_id = getattr(session, attribute_name)
                if isinstance(raw_id, str):
                    return raw_id
        return None

    @classmethod
    def _extract_session_title(cls, session: Any) -> str:
        """Возвращает заголовок сессии или fallback по идентификатору."""

        if isinstance(session, dict):
            raw_title = session.get("title")
            if isinstance(raw_title, str) and raw_title:
                return raw_title
            session_id = cls._extract_session_id(session)
            return session_id or "unknown-session"
        try:
            raw_title = session.title
            if isinstance(raw_title, str) and raw_title:
                return raw_title
        except AttributeError:
            pass
        session_id = cls._extract_session_id(session)
        return session_id or "unknown-session"
