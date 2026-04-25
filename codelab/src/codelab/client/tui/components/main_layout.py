"""Главный layout контейнер приложения.

Референс: OpenCode packages/web/src/ui/layout.tsx

Отвечает за:
- Структуру layout: Header | (Sidebar | MainContent) | Footer
- Toggle sidebar и bottom panel
- Координацию между панелями через UIViewModel
- События изменения состояния (SidebarToggled, PanelToggled)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive

if TYPE_CHECKING:
    from codelab.client.presentation.ui_view_model import UIViewModel


@dataclass
class LayoutConfig:
    """Конфигурация MainLayout.
    
    Attributes:
        sidebar_width: Ширина sidebar в символах
        sidebar_visible: Начальная видимость sidebar
        bottom_panel_height: Высота нижней панели в строках
        bottom_panel_visible: Начальная видимость нижней панели
        min_width_for_sidebar: Минимальная ширина экрана для показа sidebar
    """
    
    sidebar_width: int = 30
    sidebar_visible: bool = True
    bottom_panel_height: int = 10
    bottom_panel_visible: bool = False
    min_width_for_sidebar: int = 80


class MainLayout(Container):
    """Главный layout контейнер.
    
    Структура:
    ┌─────────────────────────────────────────┐
    │ Header                                  │
    ├────────┬────────────────────────────────┤
    │        │ ChatView                       │
    │Sidebar │────────────────────────────────│
    │        │ PromptInput                    │
    │        ├────────────────────────────────│
    │        │ ToolPanel / TerminalPanel      │
    └────────┴────────────────────────────────┘
    │ Footer                                  │
    └─────────────────────────────────────────┘
    
    Attributes:
        sidebar_visible: Видимость sidebar
        bottom_panel_visible: Видимость нижней панели
    """

    # --- События ---
    
    class SidebarToggled(Message):
        """Событие переключения sidebar.
        
        Attributes:
            visible: Новое состояние видимости sidebar
        """
        
        def __init__(self, visible: bool) -> None:
            """Инициализирует событие.
            
            Args:
                visible: Новое состояние видимости
            """
            super().__init__()
            self.visible = visible
    
    class PanelToggled(Message):
        """Событие переключения нижней панели.
        
        Attributes:
            panel_type: Тип панели ('bottom')
            visible: Новое состояние видимости
        """
        
        def __init__(self, panel_type: str, visible: bool) -> None:
            """Инициализирует событие.
            
            Args:
                panel_type: Тип панели
                visible: Новое состояние видимости
            """
            super().__init__()
            self.panel_type = panel_type
            self.visible = visible

    # --- Reactive свойства ---
    
    sidebar_visible: reactive[bool] = reactive(True)
    bottom_panel_visible: reactive[bool] = reactive(False)
    
    DEFAULT_CSS = """
    MainLayout {
        layout: vertical;
        width: 100%;
        height: 100%;
    }
    
    MainLayout > .body-container {
        layout: horizontal;
        width: 100%;
        height: 1fr;
    }
    
    MainLayout > .body-container > .sidebar-column {
        width: 30;
        height: 100%;
    }
    
    MainLayout > .body-container > .sidebar-column.hidden {
        display: none;
    }
    
    MainLayout > .body-container > .main-column {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }
    
    MainLayout > .body-container > .main-column > .content-area {
        height: 1fr;
    }
    
    MainLayout > .body-container > .main-column > .bottom-panel {
        height: 10;
    }
    
    MainLayout > .body-container > .main-column > .bottom-panel.hidden {
        display: none;
    }
    """

    def __init__(
        self,
        config: LayoutConfig | None = None,
        ui_vm: UIViewModel | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Инициализирует MainLayout.

        Args:
            config: Конфигурация layout
            ui_vm: UIViewModel для управления состоянием layout
            name: Имя виджета
            id: ID виджета
            classes: CSS классы
        """
        super().__init__(name=name, id=id, classes=classes)
        self._config = config or LayoutConfig()
        self._ui_vm = ui_vm
        
        # Контейнеры для секций (инициализируем ДО reactive свойств)
        self._sidebar_container: Vertical | None = None
        self._content_container: Vertical | None = None
        self._bottom_panel_container: Vertical | None = None
        
        # Применяем начальные значения из конфигурации
        self.sidebar_visible = self._config.sidebar_visible
        self.bottom_panel_visible = self._config.bottom_panel_visible
        
        # Подписываемся на изменения в UIViewModel
        if self._ui_vm is not None:
            self._ui_vm.sidebar_collapsed.subscribe(self._on_sidebar_collapsed_changed)

    @property
    def config(self) -> LayoutConfig:
        """Возвращает конфигурацию layout."""
        return self._config

    def compose(self) -> ComposeResult:
        """Создает базовую структуру layout.
        
        Дочерние виджеты должны быть добавлены через mount() или в подклассе.
        """
        # Body контейнер (horizontal: sidebar | main)
        with Horizontal(classes="body-container", id="body-container"):
            # Sidebar колонка (левая)
            sidebar_classes = "sidebar-column"
            if not self.sidebar_visible:
                sidebar_classes += " hidden"
            self._sidebar_container = Vertical(
                classes=sidebar_classes,
                id="sidebar-column",
            )
            yield self._sidebar_container
            
            # Основная колонка (центр + низ)
            with Vertical(classes="main-column", id="main-column"):
                # Контент
                self._content_container = Vertical(
                    classes="content-area",
                    id="content-area",
                )
                yield self._content_container
                
                # Нижняя панель
                bottom_classes = "bottom-panel"
                if not self.bottom_panel_visible:
                    bottom_classes += " hidden"
                self._bottom_panel_container = Vertical(
                    classes=bottom_classes,
                    id="bottom-panel",
                )
                yield self._bottom_panel_container

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
        
        # Отправляем событие
        self.post_message(self.SidebarToggled(visible))

    def watch_bottom_panel_visible(self, visible: bool) -> None:
        """Реагирует на изменение видимости нижней панели.
        
        Args:
            visible: Новое значение видимости
        """
        if self._bottom_panel_container is not None:
            if visible:
                self._bottom_panel_container.remove_class("hidden")
            else:
                self._bottom_panel_container.add_class("hidden")
        
        # Отправляем событие
        self.post_message(self.PanelToggled("bottom", visible))

    def toggle_sidebar(self) -> None:
        """Переключает видимость sidebar."""
        self.sidebar_visible = not self.sidebar_visible
        # Синхронизируем с ViewModel если есть
        if self._ui_vm is not None:
            self._ui_vm.sidebar_collapsed.value = not self.sidebar_visible

    def toggle_bottom_panel(self) -> None:
        """Переключает видимость нижней панели."""
        self.bottom_panel_visible = not self.bottom_panel_visible

    def on_resize(self) -> None:
        """Обрабатывает изменение размера для responsive поведения."""
        # Автоматически скрываем sidebar при маленькой ширине
        if (
            self.size.width < self._config.min_width_for_sidebar
            and self.sidebar_visible
        ):
            self.sidebar_visible = False
        # Восстанавливаем если достаточно места и не было явно скрыто
        elif (
            self._ui_vm is not None
            and not self._ui_vm.sidebar_collapsed.value
            and not self.sidebar_visible
            and self.size.width >= self._config.min_width_for_sidebar
        ):
            self.sidebar_visible = True

    @property
    def sidebar_column(self) -> Vertical | None:
        """Возвращает контейнер sidebar колонки."""
        return self._sidebar_container
    
    @property
    def content_area(self) -> Vertical | None:
        """Возвращает контейнер области контента."""
        return self._content_container
    
    @property
    def bottom_panel(self) -> Vertical | None:
        """Возвращает контейнер нижней панели."""
        return self._bottom_panel_container
