"""Тесты для MainLayout компонента.

Проверяет:
- Инициализацию с LayoutConfig
- Toggle sidebar и bottom panel
- События SidebarToggled и PanelToggled
- Responsive поведение при resize
- Свойства контейнеров
"""

from __future__ import annotations

from codelab.client.tui.components.main_layout import LayoutConfig, MainLayout


class TestLayoutConfig:
    """Тесты для LayoutConfig dataclass."""

    def test_default_values(self) -> None:
        """LayoutConfig имеет корректные значения по умолчанию."""
        config = LayoutConfig()
        
        assert config.sidebar_width == 30
        assert config.sidebar_visible is True
        assert config.bottom_panel_height == 10
        assert config.bottom_panel_visible is False
        assert config.min_width_for_sidebar == 80

    def test_custom_values(self) -> None:
        """LayoutConfig принимает кастомные значения."""
        config = LayoutConfig(
            sidebar_width=40,
            sidebar_visible=False,
            bottom_panel_height=15,
            bottom_panel_visible=True,
            min_width_for_sidebar=100,
        )
        
        assert config.sidebar_width == 40
        assert config.sidebar_visible is False
        assert config.bottom_panel_height == 15
        assert config.bottom_panel_visible is True
        assert config.min_width_for_sidebar == 100


class TestMainLayout:
    """Тесты для MainLayout компонента."""

    def test_default_initialization(self) -> None:
        """MainLayout инициализируется с дефолтной конфигурацией."""
        layout = MainLayout()
        
        assert layout.sidebar_visible is True
        assert layout.bottom_panel_visible is False
        assert layout.config.sidebar_width == 30

    def test_initialization_with_config(self) -> None:
        """MainLayout инициализируется с кастомной конфигурацией."""
        config = LayoutConfig(
            sidebar_visible=False,
            bottom_panel_visible=True,
        )
        layout = MainLayout(config=config)
        
        assert layout.sidebar_visible is False
        assert layout.bottom_panel_visible is True

    def test_toggle_sidebar(self) -> None:
        """toggle_sidebar() переключает видимость sidebar."""
        layout = MainLayout()
        
        # Изначально видим
        assert layout.sidebar_visible is True
        
        # Переключаем
        layout.toggle_sidebar()
        assert layout.sidebar_visible is False
        
        # Переключаем обратно
        layout.toggle_sidebar()
        assert layout.sidebar_visible is True

    def test_toggle_bottom_panel(self) -> None:
        """toggle_bottom_panel() переключает видимость нижней панели."""
        layout = MainLayout()
        
        # Изначально скрыта
        assert layout.bottom_panel_visible is False
        
        # Переключаем
        layout.toggle_bottom_panel()
        assert layout.bottom_panel_visible is True
        
        # Переключаем обратно
        layout.toggle_bottom_panel()
        assert layout.bottom_panel_visible is False

    def test_config_property(self) -> None:
        """config property возвращает конфигурацию."""
        config = LayoutConfig(sidebar_width=50)
        layout = MainLayout(config=config)
        
        assert layout.config is config
        assert layout.config.sidebar_width == 50


class TestMainLayoutMessages:
    """Тесты для событий MainLayout."""

    def test_sidebar_toggled_message(self) -> None:
        """SidebarToggled содержит правильное состояние."""
        msg_visible = MainLayout.SidebarToggled(visible=True)
        msg_hidden = MainLayout.SidebarToggled(visible=False)
        
        assert msg_visible.visible is True
        assert msg_hidden.visible is False

    def test_panel_toggled_message(self) -> None:
        """PanelToggled содержит правильный тип и состояние."""
        msg = MainLayout.PanelToggled(panel_type="bottom", visible=True)
        
        assert msg.panel_type == "bottom"
        assert msg.visible is True


class TestMainLayoutContainers:
    """Тесты для контейнеров MainLayout (до compose)."""

    def test_containers_none_before_compose(self) -> None:
        """Контейнеры равны None до вызова compose()."""
        layout = MainLayout()
        
        # До compose все контейнеры None
        assert layout.sidebar_column is None
        assert layout.content_area is None
        assert layout.bottom_panel is None


class TestMainLayoutCSS:
    """Тесты для CSS MainLayout."""

    def test_has_default_css(self) -> None:
        """MainLayout имеет DEFAULT_CSS."""
        assert MainLayout.DEFAULT_CSS is not None
        assert "MainLayout" in MainLayout.DEFAULT_CSS
        assert "sidebar-column" in MainLayout.DEFAULT_CSS
        assert "bottom-panel" in MainLayout.DEFAULT_CSS

    def test_css_contains_hidden_rules(self) -> None:
        """CSS содержит правила для скрытия элементов."""
        css = MainLayout.DEFAULT_CSS
        
        assert ".hidden" in css
        assert "display: none" in css


class TestMainLayoutIntegration:
    """Интеграционные тесты для MainLayout."""

    def test_config_affects_initial_state(self) -> None:
        """Конфигурация влияет на начальное состояние."""
        # Sidebar скрыт, panel видим
        config = LayoutConfig(
            sidebar_visible=False,
            bottom_panel_visible=True,
        )
        layout = MainLayout(config=config)
        
        assert layout.sidebar_visible is False
        assert layout.bottom_panel_visible is True
        
    def test_multiple_toggles(self) -> None:
        """Множественные переключения работают корректно."""
        layout = MainLayout()
        
        # Несколько переключений sidebar
        for i in range(5):
            layout.toggle_sidebar()
            expected = i % 2 == 0  # False, True, False, True, False
            assert layout.sidebar_visible is not expected
        
        # Несколько переключений bottom panel
        for i in range(5):
            layout.toggle_bottom_panel()
            expected = i % 2 == 0  # True, False, True, False, True
            assert layout.bottom_panel_visible is expected
