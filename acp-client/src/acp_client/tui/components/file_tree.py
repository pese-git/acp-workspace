"""Дерево файлов проекта для sidebar панели TUI."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.message import Message
from textual.widgets import DirectoryTree
from textual.widgets.directory_tree import DirEntry
from textual.widgets.tree import TreeNode


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
        self._changed_paths: set[Path] = set()
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
        self._changed_paths = set()

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

    def mark_changed(self, path: Path) -> None:
        """Помечает файл как измененный для визуального индикатора в дереве."""

        normalized_path = path.expanduser().resolve()
        if normalized_path.is_absolute():
            self._changed_paths.add(normalized_path)

    def is_changed(self, path: Path) -> bool:
        """Проверяет, что путь имеет отметку измененного файла в текущем root."""

        return self._path_has_changes(path.expanduser().resolve())

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Пробрасывает выбор файла в приложение через отдельное событие."""

        if event.path is None:
            return
        selected_path = Path(event.path)
        if not selected_path.is_file():
            return
        self.post_message(self.FileOpenRequested(selected_path))

    def render_label(self, node: TreeNode[DirEntry], base_style: Style, style: Style) -> Text:
        """Добавляет маркер `*` к файлам и директориям с локальными изменениями."""

        label = super().render_label(node, base_style, style)
        node_data = node.data
        if node_data is None:
            return label
        node_path = node_data.path.resolve()
        if self._path_has_changes(node_path):
            label.append(" *", style="bold #d97706")
        return label

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        """Скрывает dot-файлы и служебные каталоги из дерева проекта."""

        return [path for path in paths if not path.name.startswith(".")]

    def _path_has_changes(self, path: Path) -> bool:
        """Определяет, затронут ли путь прямым или дочерним изменением."""

        if path in self._changed_paths:
            return True
        if not path.is_dir():
            return False
        return any(changed_path.is_relative_to(path) for changed_path in self._changed_paths)
