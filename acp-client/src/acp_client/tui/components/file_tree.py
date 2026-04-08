"""Дерево файлов проекта для sidebar панели TUI."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.message import Message
from textual.widgets import DirectoryTree


class FileTree(DirectoryTree):
    """Показывает локальную структуру файлов с фильтрацией скрытых путей."""

    class FileOpenRequested(Message):
        """Событие запроса на открытие файла из дерева."""

        def __init__(self, path: Path) -> None:
            """Сохраняет абсолютный путь выбранного файла."""

            super().__init__()
            self.path = path

    def __init__(self, *, root_path: str) -> None:
        """Создает дерево файлов с указанным корневым абсолютным путем."""

        self._root_path = Path(root_path).expanduser()
        super().__init__(str(self._root_path), id="file-tree")

    @property
    def root_path(self) -> Path:
        """Возвращает последнее установленное корневое значение для дерева."""

        return self._root_path

    def set_root_path(self, root_path: str) -> None:
        """Обновляет корневой путь дерева, если путь валиден и абсолютный."""

        normalized_path = Path(root_path).expanduser()
        if not normalized_path.is_absolute():
            return
        if not normalized_path.exists() or not normalized_path.is_dir():
            return
        self._root_path = normalized_path

        # Если компонент еще не смонтирован в App, откладываем фактический reload.
        try:
            _ = self.app
        except Exception:
            return

        self.path = normalized_path
        self.reload()

    def refresh_tree(self) -> None:
        """Принудительно обновляет дерево файлов, если компонент смонтирован."""

        try:
            _ = self.app
        except Exception:
            return
        self.reload()

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Пробрасывает выбор файла в приложение через отдельное событие."""

        selected_path = Path(event.path)
        if not selected_path.is_file():
            return
        self.post_message(self.FileOpenRequested(selected_path))

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Скрывает dot-файлы и служебные каталоги из дерева проекта."""

        return [path for path in paths if not path.name.startswith(".")]
