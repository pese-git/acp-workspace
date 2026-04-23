"""Компонент для отображения вывода терминала в TUI."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from codelab.client.presentation.terminal_view_model import TerminalViewModel


class TerminalOutputPanel(Static):
    """Рендерит потоковый terminal output с поддержкой ANSI-последовательностей.
    
    Интегрирован с TerminalViewModel для управления состоянием вывода через MVVM паттерн.
    Все изменения вывода должны проходить через ViewModel.
    """

    def __init__(self, terminal_vm: TerminalViewModel) -> None:
        """Создает панель вывода терминала с ViewModel.
        
        Args:
            terminal_vm: TerminalViewModel для управления состоянием (ТРЕБУЕТСЯ)
        """
        super().__init__(id="terminal-output")
        self._terminal_vm = terminal_vm
        self._exit_code: int | None = None
        
        # Подписываемся на изменения ViewModel
        self._terminal_vm.output.subscribe(self._on_output_changed)
        self._terminal_vm.has_output.subscribe(self._on_has_output_changed)
        self._terminal_vm.is_running.subscribe(self._on_running_changed)

    def _on_output_changed(self, output: str) -> None:
        """Обработчик изменения вывода в ViewModel.
        
        Args:
            output: Новый текст вывода
        """
        # Обновляем UI, игнорируя ошибки если компонент не смонтирован
        with suppress(RuntimeError):
            self.update(self.render_text())

    def _on_has_output_changed(self, has_output: bool) -> None:
        """Обработчик изменения флага наличия вывода.
        
        Args:
            has_output: True если есть вывод, False если пусто
        """
        # Обновляем UI, игнорируя ошибки если компонент не смонтирован
        with suppress(RuntimeError):
            self.update(self.render_text())

    def _on_running_changed(self, is_running: bool) -> None:
        """Обработчик изменения статуса выполнения команды.
        
        Args:
            is_running: True если команда выполняется, False если завершена
        """
        # Обновляем UI, игнорируя ошибки если компонент не смонтирован
        with suppress(RuntimeError):
            self.update(self.render_text())

    def reset(self) -> None:
        """Сбрасывает вывод терминала через ViewModel."""
        self._terminal_vm.clear_output()
        self._exit_code = None

    def append_output(self, output: str) -> None:
        """Добавляет очередной chunk stdout/stderr через ViewModel.
        
        Args:
            output: Текст для добавления в конец вывода
        """
        if output:
            self._terminal_vm.append_output(output)

    def set_output(self, output: str) -> None:
        """Установить весь вывод через ViewModel.
        
        Args:
            output: Новый текст вывода (заменяет предыдущий)
        """
        self._terminal_vm.set_output(output)

    def set_exit_code(self, exit_code: int | None) -> None:
        """Сохраняет известный exit code завершенного терминального процесса.
        
        Args:
            exit_code: Код завершения процесса или None
        """
        self._exit_code = exit_code
        self.update(self.render_text())

    def render_text(self) -> Text:
        """Возвращает итоговый Rich Text с ANSI-цветами и статусной строкой."""
        output = self._terminal_vm.output.value
        
        # Если нет вывода
        if not output:
            if self._exit_code is None:
                return Text("Нет вывода терминала")
            return Text(f"Exit code: {self._exit_code}")
        
        # Рендеризуем вывод с ANSI поддержкой
        output_text = Text.from_ansi(output)
        
        # Добавляем exit code если доступен
        if self._exit_code is not None:
            output_text.append(f"\n\nExit code: {self._exit_code}", style="bold")
        
        return output_text
