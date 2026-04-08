"""Модальное окно просмотра текстового файла."""

from __future__ import annotations

from pathlib import Path

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class FileViewerModal(ModalScreen[None]):
    """Показывает содержимое выбранного файла с подсветкой синтаксиса."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("q", "close", "Close"),
    ]

    def __init__(self, *, file_path: str, content: str) -> None:
        """Сохраняет путь и текст файла для последующего рендера."""

        super().__init__()
        self._file_path = file_path
        self._content = content

    def compose(self) -> ComposeResult:
        """Рендерит заголовок и подсвеченный контент файла."""

        with Vertical(id="file-viewer-modal"):
            yield Static(f"Файл: {self._file_path}", id="file-viewer-title")
            yield Static(self._build_syntax(), id="file-viewer-content")

    def action_close(self) -> None:
        """Закрывает окно просмотра файла по hotkey."""

        self.dismiss(None)

    def _build_syntax(self) -> Syntax:
        """Создает Rich Syntax-блок с авто-определением языка по расширению."""

        guessed_language = Path(self._file_path).suffix.removeprefix(".")
        language = guessed_language if guessed_language else "text"
        return Syntax(
            self._content,
            language,
            line_numbers=True,
            word_wrap=False,
            indent_guides=True,
        )
