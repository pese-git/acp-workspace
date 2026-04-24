"""Главный layout контейнер приложения.

Референс: OpenCode packages/web/src/ui/layout.tsx

Отвечает за:
- Трехколоночный layout: Sidebar | MainContent | RightPanel (опционально)
- Responsive поведение: скрытие sidebar при маленьком размере
- Координацию между панелями через UIViewModel
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import reactive

if TYPE_CHECKING:
    from codelab.client.presentation.ui_view_model import UIViewModel


class MainLayout(Container):
    """Главный layout контейнер с трехколоночной структурой.
    
    Структура по образцу OpenCode:
    - Titlebar (header) - вынесен отдельно
    - Body: Horizontal container
      - Sidebar (левая колонка, сворачиваемая)
      - MainContent (центральная колонка, основной контент)
      - RightPanel (правая колонка, опциональная)
    
    Attributes:
        sidebar_visible: Видимость левой панели
        right_panel_visible: Видимость правой панели
    """

    # Reactive свойства для управления видимостью панелей
    sidebar_visible: reactive[bool] = reactive(True)
    right_panel_visible: reactive[bool] = reactive(False)
    
    # Минимальная ширина экрана для показа sidebar
    MIN_WIDTH_FOR_SIDEBAR = 80
    
    DEFAULT_CSS = """
    MainLayout {
        layout: horizontal;
        width: 100%;
        height: 100%;
    }
    
    MainLayout > .sidebar-column {
        width: 30;
        height: 100%;
    }
    
    MainLayout > .sidebar-column.hidden {
        display: none;
    }
    
    MainLayout > .main-column {
        width: 1fr;
        height: 100%;
    }
    
    MainLayout > .right-panel-column {
        width: 30;
        height: 100%;
    }
    
    MainLayout > .right-panel-column.hidden {
        display: none;
    }
    """

    def __init__(
        self,
        ui_vm: UIViewModel | None = None,
        *,
        sidebar_width: int = 30,
        right_panel_width: int = 30,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Инициализирует MainLayout.

        Args:
            ui_vm: UIViewModel для управления состоянием layout
            sidebar_width: Ширина sidebar в символах
            right_panel_width: Ширина правой панели в символах
            name: Имя виджета
            id: ID виджета
            classes: CSS классы
        """
        super().__init__(name=name, id=id, classes=classes)
        self._ui_vm = ui_vm
        self._sidebar_width = sidebar_width
        self._right_panel_width = right_panel_width
        
        # Контейнеры для колонок создаются в compose
        self._sidebar_container: Vertical | None = None
        self._main_container: Vertical | None = None
        self._right_panel_container: Vertical | None = None
        
        # Подписываемся на изменения в UIViewModel
        if self._ui_vm is not None:
            self._ui_vm.sidebar_collapsed.subscribe(self._on_sidebar_collapsed_changed)

    def compose(self) -> ComposeResult:
        """Создает базовую структуру layout.
        
        Дочерние виджеты должны быть добавлены через mount() или в подклассе.
        """
        # Sidebar колонка (левая)
        self._sidebar_container = Vertical(
            classes="sidebar-column",
            id="sidebar-column",
        )
        yield self._sidebar_container
        
        # Основная колонка (центр)
        self._main_container = Vertical(
            classes="main-column",
            id="main-column",
        )
        yield self._main_container
        
        # Правая панель (опционально)
        self._right_panel_container = Vertical(
            classes="right-panel-column hidden",
            id="right-panel-column",
        )
        yield self._right_panel_container

    def _on_sidebar_collapsed_changed(self, collapsed: bool) -> None:
        """Обработчик изменения состояния свернутости sidebar.
        
        Args:
            collapsed: True если sidebar свернут
        """
        self.sidebar_visible = not collapsed

    def watch_sidebar_visible(self, visible: bool) -> None:
        """Реагирует на изменение видимости sidebar.
        
        Args:
            visible: Новое значение видимости
        """
        if self._sidebar_container is not None:
            if visible:
                self._sidebar_container.remove_class("hidden")
            else:
                self._sidebar_container.add_class("hidden")

    def watch_right_panel_visible(self, visible: bool) -> None:
        """Реагирует на изменение видимости правой панели.
        
        Args:
            visible: Новое значение видимости
        """
        if self._right_panel_container is not None:
            if visible:
                self._right_panel_container.remove_class("hidden")
            else:
                self._right_panel_container.add_class("hidden")

    def toggle_sidebar(self) -> None:
        """Переключает видимость sidebar."""
        self.sidebar_visible = not self.sidebar_visible
        # Синхронизируем с ViewModel если есть
        if self._ui_vm is not None:
            self._ui_vm.sidebar_collapsed.value = not self.sidebar_visible

    def toggle_right_panel(self) -> None:
        """Переключает видимость правой панели."""
        self.right_panel_visible = not self.right_panel_visible

    def on_resize(self) -> None:
        """Обрабатывает изменение размера для responsive поведения."""
        # Автоматически скрываем sidebar при маленькой ширине
        if self.size.width < self.MIN_WIDTH_FOR_SIDEBAR and self.sidebar_visible:
            self.sidebar_visible = False
        # Восстанавливаем если достаточно места и не было явно скрыто
        elif (
            self._ui_vm is not None
            and not self._ui_vm.sidebar_collapsed.value
            and not self.sidebar_visible
        ):
            self.sidebar_visible = True

    @property
    def sidebar_column(self) -> Vertical | None:
        """Возвращает контейнер sidebar колонки."""
        return self._sidebar_container
    
    @property
    def main_column(self) -> Vertical | None:
        """Возвращает контейнер основной колонки."""
        return self._main_container
    
    @property
    def right_panel_column(self) -> Vertical | None:
        """Возвращает контейнер правой панели."""
        return self._right_panel_container
