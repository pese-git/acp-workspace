"""Поле ввода пользовательского промпта."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea


class PromptInput(TextArea):
    """Многострочное поле ввода с отправкой по Ctrl+Enter."""

    BINDINGS = [
        ("ctrl+enter", "submit", "Send"),
        ("up", "history_previous", "Prev Prompt"),
        ("down", "history_next", "Next Prompt"),
        ("ctrl+up", "history_previous", "Prev Prompt"),
        ("ctrl+down", "history_next", "Next Prompt"),
    ]

    class Submitted(Message):
        """Событие отправки текущего текста из поля ввода."""

        def __init__(self, text: str) -> None:
            """Сохраняет текст отправленного сообщения."""

            super().__init__()
            self.text = text

    def __init__(self) -> None:
        """Создает поле ввода с placeholder подсказкой."""

        super().__init__(id="prompt-input")
        self.border_title = "Prompt"
        self.tooltip = "Ctrl+Enter - отправить, Up/Down - история"
        self._active_session_id: str | None = None
        self._history_by_session: dict[str, list[str]] = {}
        self._history_index: int | None = None
        self._draft_text: str = ""

    def set_active_session(self, session_id: str | None) -> None:
        """Переключает активный контекст истории промптов для текущей сессии."""

        self._active_session_id = session_id
        self._history_index = None
        self._draft_text = ""

    def remember_prompt(self, text: str) -> None:
        """Сохраняет отправленный prompt в историю активной сессии."""

        normalized = text.strip()
        if not normalized:
            return
        history = self._active_history()
        if history and history[-1] == normalized:
            return
        history.append(normalized)
        if len(history) > 100:
            del history[0]
        self._history_index = None
        self._draft_text = ""

    def action_submit(self) -> None:
        """Отправляет текст, если поле не пустое."""

        normalized = self.text.strip()
        if not normalized:
            return
        self.post_message(self.Submitted(normalized))

    def action_history_previous(self) -> None:
        """Подставляет предыдущий prompt из истории активной сессии."""

        history = self._active_history()
        if not history:
            return
        if self._history_index is None:
            self._draft_text = self.text
            self._history_index = len(history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self.text = history[self._history_index]

    def action_history_next(self) -> None:
        """Переходит к более новому prompt или возвращает сохраненный черновик."""

        history = self._active_history()
        if not history or self._history_index is None:
            return
        if self._history_index < len(history) - 1:
            self._history_index += 1
            self.text = history[self._history_index]
            return
        self._history_index = None
        self.text = self._draft_text
        self._draft_text = ""

    def on_key(self, event: events.Key) -> None:
        """Сохраняет Enter как перенос строки внутри поля ввода."""

        # Явно оставляем стандартное поведение TextArea для Enter.
        if event.key == "enter":
            return

    def _active_history(self) -> list[str]:
        """Возвращает список истории для активной сессии."""

        history_key = self._active_session_id or "__default__"
        if history_key not in self._history_by_session:
            self._history_by_session[history_key] = []
        return self._history_by_session[history_key]
