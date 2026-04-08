"""Локальный менеджер терминальных процессов для TUI."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TerminalProcessState:
    """Состояние одного терминального процесса."""

    process: subprocess.Popen[str]
    output_buffer: str = ""


class LocalTerminalManager:
    """Обрабатывает terminal/* запросы и управляет локальными процессами."""

    def __init__(self) -> None:
        """Инициализирует хранилище процессов и счетчик terminal id."""

        self._processes: dict[str, TerminalProcessState] = {}
        self._counter = 0

    def create_terminal(self, command: str) -> str:
        """Создает терминальный процесс по shell-команде и возвращает terminal id."""

        args = shlex.split(command)
        if not args:
            msg = "Command must not be empty"
            raise ValueError(msg)

        process = subprocess.Popen(
            args,
            cwd=Path.cwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if process.stdout is None:
            msg = "Terminal stdout is not available"
            raise RuntimeError(msg)

        os.set_blocking(process.stdout.fileno(), False)
        terminal_id = self._next_terminal_id()
        self._processes[terminal_id] = TerminalProcessState(process=process)
        return terminal_id

    def get_output(self, terminal_id: str) -> str:
        """Возвращает накопленный stdout процесса с неблокирующим чтением."""

        state = self._get_state(terminal_id)
        stream = state.process.stdout
        if stream is None:
            return ""

        try:
            chunk = stream.read()
        except (BlockingIOError, ValueError, TypeError):
            # BlockingIOError: неблокирующее чтение не имеет данных
            # ValueError: поток закрыт
            # TypeError: проблема с кодированием при завершенном процессе
            chunk = ""
        if chunk is None or not isinstance(chunk, str):
            chunk = ""
        if chunk:
            state.output_buffer += chunk

        buffered_output = state.output_buffer
        state.output_buffer = ""
        return buffered_output

    def wait_for_exit(self, terminal_id: str) -> int | tuple[int | None, str | None]:
        """Возвращает exit code завершенного процесса или `(None, None)` если еще жив."""

        state = self._get_state(terminal_id)
        return_code = state.process.poll()
        if return_code is None:
            return (None, None)
        return return_code

    def release_terminal(self, terminal_id: str) -> None:
        """Освобождает записи о процессе и закрывает его пайпы, если открыты."""

        state = self._processes.pop(terminal_id, None)
        if state is None:
            return
        if state.process.stdout is not None:
            state.process.stdout.close()

    def kill_terminal(self, terminal_id: str) -> bool:
        """Завершает процесс по terminal id и возвращает флаг успешной операции."""

        state = self._processes.get(terminal_id)
        if state is None:
            return False
        if state.process.poll() is not None:
            return True

        state.process.kill()
        try:
            state.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            return False
        return state.process.poll() is not None

    def _get_state(self, terminal_id: str) -> TerminalProcessState:
        """Возвращает состояние процесса или бросает ошибку для неизвестного id."""

        state = self._processes.get(terminal_id)
        if state is None:
            msg = f"Unknown terminal id: {terminal_id}"
            raise ValueError(msg)
        return state

    def _next_terminal_id(self) -> str:
        """Генерирует следующий локальный идентификатор терминала."""

        self._counter += 1
        return f"term_{self._counter}"
