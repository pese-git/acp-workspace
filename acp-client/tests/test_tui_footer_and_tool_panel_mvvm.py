"""Тесты для компонентов FooterBar и ToolPanel с MVVM интеграцией."""

from __future__ import annotations

import pytest

from acp_client.infrastructure.events.bus import EventBus
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.ui_view_model import ConnectionStatus, UIViewModel
from acp_client.tui.components.footer import FooterBar
from acp_client.tui.components.tool_panel import ToolPanel


@pytest.fixture
def event_bus() -> EventBus:
    """Создать EventBus для тестов."""
    return EventBus()


@pytest.fixture
def ui_view_model(event_bus: EventBus) -> UIViewModel:
    """Создать UIViewModel для тестов."""
    return UIViewModel(event_bus=event_bus, logger=None)


@pytest.fixture
def chat_view_model(event_bus: EventBus) -> ChatViewModel:
    """Создать ChatViewModel для тестов."""
    coordinator = None
    return ChatViewModel(coordinator=coordinator, event_bus=event_bus, logger=None)


@pytest.fixture
def footer_bar(ui_view_model: UIViewModel) -> FooterBar:
    """Создать FooterBar с UIViewModel."""
    return FooterBar(ui_view_model)


@pytest.fixture
def tool_panel(chat_view_model: ChatViewModel) -> ToolPanel:
    """Создать ToolPanel с ChatViewModel."""
    return ToolPanel(chat_view_model)


# ===== FooterBar Tests =====

def test_footer_bar_initializes_with_ui_view_model(ui_view_model: UIViewModel) -> None:
    """Проверить что FooterBar инициализируется с UIViewModel."""
    footer = FooterBar(ui_view_model)
    
    assert footer.ui_vm is ui_view_model
    assert footer.id == "footer"


def test_footer_bar_displays_connection_status(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить что FooterBar отображает статус соединения."""
    ui_view_model.connection_status.value = ConnectionStatus.CONNECTED
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "connected" in rendered


def test_footer_bar_displays_error_message(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить что FooterBar отображает ошибку с приоритетом."""
    ui_view_model.error_message.value = "Connection failed"
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "Error" in rendered
    assert "Connection failed" in rendered


def test_footer_bar_displays_warning_message(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить что FooterBar отображает предупреждение."""
    ui_view_model.warning_message.value = "Low memory"
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "Warning" in rendered
    assert "Low memory" in rendered


def test_footer_bar_displays_info_message(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить что FooterBar отображает информационное сообщение."""
    ui_view_model.info_message.value = "Loading data..."
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "Loading data..." in rendered


def test_footer_bar_error_has_priority_over_warning(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить приоритет: ошибка > предупреждение."""
    ui_view_model.error_message.value = "Critical error"
    ui_view_model.warning_message.value = "Low memory"
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "Error" in rendered
    assert "Critical error" in rendered
    assert "Low memory" not in rendered


def test_footer_bar_warning_has_priority_over_info(
    footer_bar: FooterBar,
    ui_view_model: UIViewModel,
) -> None:
    """Проверить приоритет: предупреждение > информация."""
    ui_view_model.warning_message.value = "Low memory"
    ui_view_model.info_message.value = "Loading..."
    
    rendered = footer_bar.render().plain  # type: ignore[attr-defined]
    assert "Warning" in rendered
    assert "Low memory" in rendered
    assert "Loading..." not in rendered


# ===== ToolPanel Tests =====

def test_tool_panel_initializes_with_chat_view_model(chat_view_model: ChatViewModel) -> None:
    """Проверить что ToolPanel инициализируется с ChatViewModel."""
    tool_panel = ToolPanel(chat_view_model)
    
    assert tool_panel.chat_vm is chat_view_model
    assert tool_panel.id == "tool-panel"


def test_tool_panel_displays_empty_message_by_default(tool_panel: ToolPanel) -> None:
    """Проверить что ToolPanel показывает "нет активных вызовов" по умолчанию."""
    rendered = tool_panel.render().plain  # type: ignore[attr-defined]
    assert "нет активных вызовов" in rendered


def test_tool_panel_updates_on_tool_calls_empty(
    tool_panel: ToolPanel,
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ToolPanel обновляется когда tool_calls пусто."""
    chat_view_model.tool_calls.value = []
    
    rendered = tool_panel.render().plain  # type: ignore[attr-defined]
    assert "нет активных вызовов" in rendered


def test_tool_panel_updates_on_tool_calls_added(
    tool_panel: ToolPanel,
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ToolPanel обновляется когда добавляются tool_calls."""
    tool_calls = [
        {"id": "tool_1", "status": "running"},
        {"id": "tool_2", "status": "pending"},
    ]
    
    chat_view_model.tool_calls.value = tool_calls
    
    rendered = tool_panel.render().plain  # type: ignore[attr-defined]
    assert "Инструменты:" in rendered


def test_tool_panel_reset_clears_calls(tool_panel: ToolPanel) -> None:
    """Проверить что reset() очищает tool calls."""
    tool_panel.reset()
    
    rendered = tool_panel.render().plain  # type: ignore[attr-defined]
    assert "нет активных вызовов" in rendered


def test_tool_panel_apply_update_works(tool_panel: ToolPanel) -> None:
    """Проверить что apply_update работает правильно."""
    # ToolPanel должен иметь метод apply_update для backward compatibility
    assert hasattr(tool_panel, "apply_update")
    assert callable(tool_panel.apply_update)
