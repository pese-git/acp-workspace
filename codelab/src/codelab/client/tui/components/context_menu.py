"""ContextMenu - контекстное меню.

Контекстное меню по правому клику:
- Группы пунктов с разделителями
- Иконки
- Hotkey hints
- Позиционирование относительно курсора
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import Offset
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Label, Static


@dataclass
class MenuItem:
    """Элемент контекстного меню.

    Атрибуты:
        id: Уникальный идентификатор
        label: Отображаемый текст
        icon: Опциональная иконка
        hotkey: Подсказка горячей клавиши
        disabled: Отключён ли пункт
        action: Функция-обработчик
        data: Дополнительные данные
    """

    id: str
    label: str
    icon: str | None = None
    hotkey: str | None = None
    disabled: bool = False
    action: Callable[[], Any] | None = None
    data: Any = None


@dataclass
class MenuSeparator:
    """Разделитель в меню."""

    pass


@dataclass
class MenuGroup:
    """Группа элементов меню.

    Атрибуты:
        items: Элементы группы
        title: Опциональный заголовок группы
    """

    items: list[MenuItem | MenuSeparator] = field(default_factory=list)
    title: str | None = None


class ContextMenuItem(Static):
    """Отдельный пункт контекстного меню."""

    DEFAULT_CSS = """
    ContextMenuItem {
        width: 100%;
        height: 1;
        padding: 0 1;
        layout: horizontal;
    }

    ContextMenuItem:hover {
        background: $primary 30%;
    }

    ContextMenuItem.-disabled {
        color: $foreground-muted;
    }

    ContextMenuItem.-disabled:hover {
        background: transparent;
    }

    ContextMenuItem .menu-icon {
        width: 3;
    }

    ContextMenuItem .menu-label {
        width: 1fr;
    }

    ContextMenuItem .menu-hotkey {
        width: auto;
        color: $foreground-muted;
    }

    ContextMenuItem.-selected {
        background: $primary 40%;
    }
    """

    class Selected(Message):
        """Сообщение о выборе пункта меню."""

        def __init__(self, item: MenuItem) -> None:
            self.item = item
            super().__init__()

    is_selected: reactive[bool] = reactive(False)

    def __init__(
        self,
        item: MenuItem,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Инициализирует пункт меню.

        Args:
            item: Данные пункта меню
            name: Имя виджета
            id: ID виджета
            classes: CSS классы
        """
        super().__init__(name=name, id=id or f"menu-item-{item.id}", classes=classes)
        self._item = item
        if item.disabled:
            self.add_class("-disabled")

    @property
    def item(self) -> MenuItem:
        """Данные пункта меню."""
        return self._item

    def compose(self) -> ComposeResult:
        """Создаёт содержимое пункта меню."""
        yield Label(self._item.icon or " ", classes="menu-icon")
        yield Label(self._item.label, classes="menu-label")
        if self._item.hotkey:
            yield Label(self._item.hotkey, classes="menu-hotkey")

    def watch_is_selected(self, selected: bool) -> None:
        """Обновляет стиль при выборе."""
        self.set_class(selected, "-selected")

    async def on_click(self) -> None:
        """Обрабатывает клик на пункт меню."""
        if not self._item.disabled:
            self.post_message(self.Selected(self._item))


class ContextMenuSeparator(Static):
    """Разделитель в контекстном меню."""

    DEFAULT_CSS = """
    ContextMenuSeparator {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: $border;
    }
    """

    def __init__(self) -> None:
        """Инициализирует разделитель."""
        super().__init__("─" * 20)


class ContextMenu(Vertical):
    """Контекстное меню.

    Выпадающее меню с пунктами, разделителями и горячими клавишами.
    """

    DEFAULT_CSS = """
    ContextMenu {
        width: auto;
        min-width: 20;
        max-width: 40;
        height: auto;
        background: $background-secondary;
        border: solid $border;
        padding: 0;
        layer: context-menu;
    }

    ContextMenu .menu-title {
        width: 100%;
        height: 1;
        padding: 0 1;
        text-style: bold;
        border-bottom: solid $border;
    }
    """

    BINDINGS = [
        ("up", "move_up", "Up"),
        ("down", "move_down", "Down"),
        ("enter", "select", "Select"),
        ("escape", "close", "Close"),
    ]

    class ItemSelected(Message):
        """Сообщение о выборе пункта меню."""

        def __init__(self, item: MenuItem) -> None:
            self.item = item
            super().__init__()

    class Closed(Message):
        """Сообщение о закрытии меню."""

        pass

    def __init__(
        self,
        items: list[MenuItem | MenuSeparator | MenuGroup],
        *,
        title: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Инициализирует контекстное меню.

        Args:
            items: Элементы меню
            title: Опциональный заголовок
            name: Имя виджета
            id: ID виджета
            classes: CSS классы
        """
        super().__init__(name=name, id=id or "context-menu", classes=classes)
        self._items = items
        self._title = title
        self._menu_items: list[ContextMenuItem] = []
        self._selected_index: int = -1

    def compose(self) -> ComposeResult:
        """Создаёт содержимое меню."""
        if self._title:
            yield Label(self._title, classes="menu-title")

        for item in self._items:
            if isinstance(item, MenuGroup):
                # Группа с заголовком
                if item.title:
                    yield Label(item.title, classes="menu-title")
                for group_item in item.items:
                    yield from self._compose_item(group_item)
            else:
                yield from self._compose_item(item)

    def _compose_item(self, item: MenuItem | MenuSeparator) -> ComposeResult:
        """Создаёт виджет для элемента меню."""
        if isinstance(item, MenuSeparator):
            yield ContextMenuSeparator()
        else:
            menu_item = ContextMenuItem(item)
            self._menu_items.append(menu_item)
            yield menu_item

    def on_mount(self) -> None:
        """Выделяет первый доступный пункт при монтировании."""
        self._select_first_enabled()

    def _select_first_enabled(self) -> None:
        """Выделяет первый доступный пункт."""
        for i, item in enumerate(self._menu_items):
            if not item.item.disabled:
                self._select_item(i)
                break

    def _select_item(self, index: int) -> None:
        """Выделяет пункт по индексу."""
        # Снимаем выделение с предыдущего
        if 0 <= self._selected_index < len(self._menu_items):
            self._menu_items[self._selected_index].is_selected = False

        # Выделяем новый
        if 0 <= index < len(self._menu_items):
            self._selected_index = index
            self._menu_items[index].is_selected = True

    def action_move_up(self) -> None:
        """Перемещает выделение вверх."""
        if not self._menu_items:
            return

        start = self._selected_index
        index = (start - 1) % len(self._menu_items)

        # Пропускаем отключённые пункты
        while self._menu_items[index].item.disabled and index != start:
            index = (index - 1) % len(self._menu_items)

        self._select_item(index)

    def action_move_down(self) -> None:
        """Перемещает выделение вниз."""
        if not self._menu_items:
            return

        start = self._selected_index
        index = (start + 1) % len(self._menu_items)

        # Пропускаем отключённые пункты
        while self._menu_items[index].item.disabled and index != start:
            index = (index + 1) % len(self._menu_items)

        self._select_item(index)

    def action_select(self) -> None:
        """Выбирает текущий пункт."""
        if 0 <= self._selected_index < len(self._menu_items):
            item = self._menu_items[self._selected_index].item
            if not item.disabled:
                self._execute_item(item)

    def action_close(self) -> None:
        """Закрывает меню."""
        self.post_message(self.Closed())

    def on_context_menu_item_selected(self, event: ContextMenuItem.Selected) -> None:
        """Обрабатывает выбор пункта меню."""
        self._execute_item(event.item)

    def _execute_item(self, item: MenuItem) -> None:
        """Выполняет действие пункта меню."""
        # Вызываем action если определён
        if item.action:
            item.action()

        # Отправляем сообщение о выборе
        self.post_message(self.ItemSelected(item))


class ContextMenuScreen(ModalScreen[MenuItem | None]):
    """Модальный экран для контекстного меню.

    Показывает контекстное меню в указанной позиции.
    """

    DEFAULT_CSS = """
    ContextMenuScreen {
        background: transparent;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    def __init__(
        self,
        items: list[MenuItem | MenuSeparator | MenuGroup],
        *,
        position: Offset | None = None,
        title: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Инициализирует экран контекстного меню.

        Args:
            items: Элементы меню
            position: Позиция меню (x, y)
            title: Опциональный заголовок
            name: Имя виджета
            id: ID виджета
            classes: CSS классы
        """
        super().__init__(name=name, id=id, classes=classes)
        self._items = items
        self._position = position or Offset(0, 0)
        self._title = title

    def compose(self) -> ComposeResult:
        """Создаёт контекстное меню."""
        menu = ContextMenu(self._items, title=self._title)
        menu.styles.offset = self._position
        yield menu

    async def on_click(self) -> None:
        """Закрывает меню при клике вне него."""
        self.dismiss(None)

    def on_context_menu_item_selected(self, event: ContextMenu.ItemSelected) -> None:
        """Возвращает выбранный пункт."""
        self.dismiss(event.item)

    def on_context_menu_closed(self, event: ContextMenu.Closed) -> None:
        """Закрывает экран."""
        self.dismiss(None)
