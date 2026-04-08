"""Компонент для отображения вывода терминала в TUI."""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static


class TerminalOutputPanel(Static):
    """Рендерит потоковый terminal output с поддержкой ANSI-последовательностей."""

    def __init__(self) -> None:
        """Создает панель вывода терминала с пустым состоянием."""

        super().__init__(id="terminal-output")
        self._output_chunks: list[str] = []
        self._exit_code: int | None = None

    def reset(self) -> None:
        """Сбрасывает буфер вывода и код завершения."""

        self._output_chunks = []
        self._exit_code = None

    def append_output(self, output: str) -> None:
        """Добавляет очередной chunk stdout/stderr в буфер панели."""

        if output:
            self._output_chunks.append(output)

    def set_exit_code(self, exit_code: int | None) -> None:
        """Сохраняет известный exit code завершенного терминального процесса."""

        self._exit_code = exit_code

    def render_text(self) -> Text:
        """Возвращает итоговый Rich Text с ANSI-цветами и статусной строкой."""

        if not self._output_chunks:
            if self._exit_code is None:
                return Text("Нет вывода терминала")
            return Text(f"Exit code: {self._exit_code}")

        output_text = Text.from_ansi("".join(self._output_chunks))
        if self._exit_code is not None:
            output_text.append(f"\n\nExit code: {self._exit_code}", style="bold")
        return output_text
