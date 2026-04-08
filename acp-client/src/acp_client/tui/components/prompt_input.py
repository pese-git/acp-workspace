"""Поле ввода пользовательского промпта."""

from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea


class PromptInput(TextArea):
    """Многострочное поле ввода с отправкой по Ctrl+Enter."""

    BINDINGS = [
        ("ctrl+enter", "submit", "Send"),
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
        self.tooltip = "Ctrl+Enter - отправить"

    def action_submit(self) -> None:
        """Отправляет текст, если поле не пустое."""

        normalized = self.text.strip()
        if not normalized:
            return
        self.post_message(self.Submitted(normalized))

    def on_key(self, event: events.Key) -> None:
        """Сохраняет Enter как перенос строки внутри поля ввода."""

        # Явно оставляем стандартное поведение TextArea для Enter.
        if event.key == "enter":
            return
