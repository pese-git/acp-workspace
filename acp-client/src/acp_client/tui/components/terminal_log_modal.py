"""Модальное окно детального просмотра terminal output."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class TerminalLogModal(ModalScreen[None]):
    """Показывает полный вывод терминала для выбранного tool call."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def __init__(self, *, title: str, terminal_id: str, output: Text) -> None:
        """Сохраняет заголовок, terminal id и текст вывода для рендера."""

        super().__init__()
        self._title = title
        self._terminal_id = terminal_id
        self._output = output

    def compose(self) -> ComposeResult:
        """Рендерит заголовок и scrollable-блок вывода терминала."""

        with Vertical(id="terminal-log-modal"):
            yield Static(
                f"{self._title} | terminal: {self._terminal_id}",
                id="terminal-log-title",
            )
            yield Static(self._output, id="terminal-log-content")

    def action_close(self) -> None:
        """Закрывает модальное окно по hotkey."""

        self.dismiss(None)
