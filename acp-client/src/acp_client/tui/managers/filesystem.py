"""Локальный менеджер файловой системы для TUI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


class LocalFileSystemManager:
    """Обрабатывает fs/read_text_file и fs/write_text_file для ACP вызовов."""

    def __init__(
        self,
        *,
        on_file_written: Callable[[Path], None] | None = None,
    ) -> None:
        """Создает менеджер и опциональный callback для обновления UI после записи."""

        self._on_file_written = on_file_written

    def read_file(self, path: str, line: int | None = None, limit: int | None = None) -> str:
        """Читает текстовый файл по абсолютному пути с optional диапазоном строк."""

        normalized_path = self._validate_absolute_file_path(path)
        content = normalized_path.read_text(encoding="utf-8")

        if line is None and limit is None:
            return content

        lines = content.splitlines(keepends=True)
        start_index = 0
        if line is not None:
            # ACP передает line как 1-based индекс, поэтому аккуратно нормализуем.
            start_index = max(line - 1, 0)
        if start_index >= len(lines):
            return ""

        end_index = len(lines)
        if limit is not None and limit >= 0:
            end_index = min(start_index + limit, len(lines))

        return "".join(lines[start_index:end_index])

    def write_file(self, path: str, content: str) -> None:
        """Записывает текст в файл по абсолютному пути и уведомляет UI callback."""

        normalized_path = self._validate_absolute_path(path)
        if normalized_path.exists() and normalized_path.is_dir():
            msg = f"Path is a directory, not file: {normalized_path}"
            raise ValueError(msg)

        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(content, encoding="utf-8")

        if self._on_file_written is not None:
            self._on_file_written(normalized_path)

    def _validate_absolute_file_path(self, path: str) -> Path:
        """Проверяет, что путь абсолютный, существует и указывает на файл."""

        normalized_path = self._validate_absolute_path(path)
        if not normalized_path.exists():
            msg = f"File not found: {normalized_path}"
            raise FileNotFoundError(msg)
        if not normalized_path.is_file():
            msg = f"Path is not a file: {normalized_path}"
            raise ValueError(msg)
        return normalized_path

    @staticmethod
    def _validate_absolute_path(path: str) -> Path:
        """Проверяет абсолютность входного пути и возвращает нормализованный Path."""

        normalized_path = Path(path).expanduser()
        if not normalized_path.is_absolute():
            msg = f"Path must be absolute: {path}"
            raise ValueError(msg)
        return normalized_path
