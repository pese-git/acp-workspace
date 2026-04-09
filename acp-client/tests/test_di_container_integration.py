"""Тесты для DIContainer интеграции с ViewModels (Phase 4.6).

Проверяет:
- Регистрацию ViewModels в DIContainer
- Singleton scope для ViewModels
- ViewModelFactory функциональность
- Инъекцию в ACPClientApp
"""

from unittest.mock import MagicMock, patch

import pytest

from acp_client.infrastructure.di_container import DIContainer
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.session_view_model import SessionViewModel
from acp_client.presentation.ui_view_model import UIViewModel
from acp_client.presentation.view_model_factory import ViewModelFactory


class TestViewModelFactory:
    """Тесты для ViewModelFactory класса."""

    def test_register_view_models_registers_all_vms(self) -> None:
        """ViewModelFactory регистрирует все ViewModels с coordinator и event_bus."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        # Все ViewModels зарегистрированы
        assert container.resolve(UIViewModel) is not None
        assert container.resolve(SessionViewModel) is not None
        assert container.resolve(ChatViewModel) is not None

    def test_register_view_models_requires_coordinator(self) -> None:
        """ViewModelFactory требует coordinator как обязательный параметр."""
        container = DIContainer()
        
        # Без coordinator выбросит TypeError
        with pytest.raises(TypeError, match="session_coordinator is required"):
            ViewModelFactory.register_view_models(container, session_coordinator=None)
        
        # Без параметра координатора тоже ошибка
        with pytest.raises(TypeError):
            ViewModelFactory.register_view_models(container)  # type: ignore[missing-argument]

    def test_register_view_models_with_coordinator(self) -> None:
        """ViewModelFactory регистрирует все три VM с coordinator и event_bus."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        # Все три ViewModel зарегистрированы
        assert container.resolve(UIViewModel) is not None
        assert container.resolve(SessionViewModel) is not None
        assert container.resolve(ChatViewModel) is not None

    def test_ui_view_model_is_singleton(self) -> None:
        """UIViewModel регистрируется как singleton."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        # Получаем UIViewModel несколько раз
        ui_vm_1 = container.resolve(UIViewModel)
        ui_vm_2 = container.resolve(UIViewModel)
        
        # Проверяем, что это одинаковые объекты (singleton)
        assert ui_vm_1 is ui_vm_2, "UIViewModel должны быть одним экземпляром"

    def test_view_models_are_singletons_with_coordinator(self) -> None:
        """ViewModels регистрируются как singletons с coordinator и event_bus."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        # Получаем ViewModels несколько раз
        ui_vm_1 = container.resolve(UIViewModel)
        ui_vm_2 = container.resolve(UIViewModel)
        
        session_vm_1 = container.resolve(SessionViewModel)
        session_vm_2 = container.resolve(SessionViewModel)
        
        chat_vm_1 = container.resolve(ChatViewModel)
        chat_vm_2 = container.resolve(ChatViewModel)
        
        # Проверяем, что это одинаковые объекты (singleton)
        assert ui_vm_1 is ui_vm_2, "UIViewModel должны быть одним экземпляром"
        assert session_vm_1 is session_vm_2, "SessionViewModel должны быть одним экземпляром"
        assert chat_vm_1 is chat_vm_2, "ChatViewModel должны быть одним экземпляром"

    def test_register_view_models_with_event_bus(self) -> None:
        """ViewModelFactory передает event_bus в ViewModels."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        ui_vm = container.resolve(UIViewModel)
        session_vm = container.resolve(SessionViewModel)
        
        # Проверяем, что event_bus был передан
        assert ui_vm.event_bus is event_bus
        assert session_vm.event_bus is event_bus

    def test_register_view_models_with_logger(self) -> None:
        """ViewModelFactory передает logger в ViewModels."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        logger = MagicMock()
        
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
            logger=logger,
        )
        
        ui_vm = container.resolve(UIViewModel)
        session_vm = container.resolve(SessionViewModel)
        
        # Проверяем, что logger был передан
        assert ui_vm.logger is logger
        assert session_vm.logger is logger

    def test_register_view_models_different_containers(self) -> None:
        """ViewModels в разных контейнерах - разные экземпляры."""
        container1 = DIContainer()
        container2 = DIContainer()
        coordinator1 = MagicMock()
        coordinator2 = MagicMock()
        event_bus1 = MagicMock()
        event_bus2 = MagicMock()
        
        ViewModelFactory.register_view_models(
            container1,
            session_coordinator=coordinator1,
            event_bus=event_bus1,
        )
        ViewModelFactory.register_view_models(
            container2,
            session_coordinator=coordinator2,
            event_bus=event_bus2,
        )
        
        ui_vm_1 = container1.resolve(UIViewModel)
        ui_vm_2 = container2.resolve(UIViewModel)
        
        # ViewModels из разных контейнеров должны быть разными объектами
        assert ui_vm_1 is not ui_vm_2


class TestDIContainerViewModelIntegration:
    """Тесты для интеграции DIContainer с ViewModels."""

    def test_resolve_ui_view_model(self) -> None:
        """DIContainer.resolve() возвращает UIViewModel корректно."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        ui_vm = container.resolve(UIViewModel)
        
        assert isinstance(ui_vm, UIViewModel)
        assert hasattr(ui_vm, 'connection_status')
        assert hasattr(ui_vm, 'is_loading')
        assert hasattr(ui_vm, 'error_message')

    def test_resolve_all_view_models_with_coordinator(self) -> None:
        """DIContainer.resolve() возвращает все ViewModels с coordinator и event_bus."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        ui_vm = container.resolve(UIViewModel)
        session_vm = container.resolve(SessionViewModel)
        chat_vm = container.resolve(ChatViewModel)
        
        assert isinstance(ui_vm, UIViewModel)
        assert isinstance(session_vm, SessionViewModel)
        assert isinstance(chat_vm, ChatViewModel)
        
        # Проверяем правильные свойства
        assert hasattr(ui_vm, 'connection_status')
        assert hasattr(session_vm, 'sessions')
        assert hasattr(chat_vm, 'messages')

    def test_container_scope_is_singleton(self) -> None:
        """ViewModels зарегистрированы с Scope.SINGLETON."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        # Проверяем, что получаем одинаковые экземпляры при множественных запросах
        vms_1 = (
            container.resolve(UIViewModel),
            container.resolve(SessionViewModel),
            container.resolve(ChatViewModel),
        )
        
        vms_2 = (
            container.resolve(UIViewModel),
            container.resolve(SessionViewModel),
            container.resolve(ChatViewModel),
        )
        
        for vm1, vm2 in zip(vms_1, vms_2, strict=True):
            assert vm1 is vm2, "ViewModels должны быть одинаковыми экземплярами"

    def test_multiple_viewmodel_instances_independent(self) -> None:
        """Разные ViewModels не влияют друг на друга."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        ui_vm = container.resolve(UIViewModel)
        session_vm = container.resolve(SessionViewModel)
        chat_vm = container.resolve(ChatViewModel)
        
        # Проверяем, что это разные объекты
        assert ui_vm is not session_vm
        assert session_vm is not chat_vm
        assert ui_vm is not chat_vm

    def test_container_clear_removes_singletons(self) -> None:
        """DIContainer.clear() очищает singleton экземпляры."""
        container = DIContainer()
        coordinator = MagicMock()
        event_bus = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator,
            event_bus=event_bus,
        )
        
        vm1 = container.resolve(UIViewModel)
        container.clear()
        
        # После clear, новая регистрация должна создать новый экземпляр
        coordinator2 = MagicMock()
        event_bus2 = MagicMock()
        ViewModelFactory.register_view_models(
            container,
            session_coordinator=coordinator2,
            event_bus=event_bus2,
        )
        vm2 = container.resolve(UIViewModel)
        
        assert vm1 is not vm2


class TestACPClientAppViewModelIntegration:
    """Тесты для интеграции ViewModels с ACPClientApp (мок тесты)."""

    @patch('acp_client.tui.app.ACPConnectionManager')
    @patch('acp_client.tui.app.TUIConfigStore')
    def test_app_initializes_container(
        self,
        mock_config_store: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """ACPClientApp инициализирует DIContainer в __init__."""
        from acp_client.tui.app import ACPClientApp
        
        mock_config_store.return_value.load.return_value = MagicMock()
        
        # Создаем приложение
        app = ACPClientApp(host="localhost", port=8000)
        
        # Проверяем, что контейнер был создан
        assert hasattr(app, '_container')
        assert isinstance(app._container, DIContainer)

    @patch('acp_client.tui.app.ACPConnectionManager')
    @patch('acp_client.tui.app.TUIConfigStore')
    def test_app_registers_all_viewmodels(
        self,
        mock_config_store: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """ACPClientApp регистрирует все ViewModels в контейнере."""
        from acp_client.tui.app import ACPClientApp
        
        mock_config_store.return_value.load.return_value = MagicMock()
        
        app = ACPClientApp(host="localhost", port=8000)
        
        # Все ViewModels зарегистрированы
        ui_vm = app._container.resolve(UIViewModel)
        session_vm = app._container.resolve(SessionViewModel)
        chat_vm = app._container.resolve(ChatViewModel)
        
        assert isinstance(ui_vm, UIViewModel)
        assert isinstance(session_vm, SessionViewModel)
        assert isinstance(chat_vm, ChatViewModel)

    @patch('acp_client.tui.app.ACPConnectionManager')
    @patch('acp_client.tui.app.TUIConfigStore')
    def test_app_stores_ui_viewmodel(
        self,
        mock_config_store: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """ACPClientApp сохраняет ссылку на UIViewModel в __init__."""
        from acp_client.tui.app import ACPClientApp
        
        mock_config_store.return_value.load.return_value = MagicMock()
        
        app = ACPClientApp(host="localhost", port=8000)
        
        # Проверяем, что UIViewModel сохранена как атрибут
        assert hasattr(app, '_ui_vm')
        assert isinstance(app._ui_vm, UIViewModel)

    @patch('acp_client.tui.app.ACPConnectionManager')
    @patch('acp_client.tui.app.TUIConfigStore')
    def test_app_viewmodels_are_singletons(
        self,
        mock_config_store: MagicMock,
        mock_connection: MagicMock,
    ) -> None:
        """ViewModels в ACPClientApp остаются одинаковыми при повторном запросе."""
        from acp_client.tui.app import ACPClientApp
        
        mock_config_store.return_value.load.return_value = MagicMock()
        
        app = ACPClientApp(host="localhost", port=8000)
        
        # Получаем ViewModels несколько раз
        ui_vm_1 = app._container.resolve(UIViewModel)
        ui_vm_2 = app._container.resolve(UIViewModel)
        
        assert ui_vm_1 is ui_vm_2
        assert ui_vm_1 is app._ui_vm
