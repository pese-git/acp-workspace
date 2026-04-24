"""Тесты для DIBootstrapper.

Проверяет:
- Успешную сборку контейнера
- Регистрацию всех сервисов
- Доступность ViewModels
"""

from unittest.mock import patch

import pytest

from codelab.client.application.session_coordinator import SessionCoordinator
from codelab.client.infrastructure.di_bootstrapper import DIBootstrapper
from codelab.client.infrastructure.di_container import DIContainer
from codelab.client.infrastructure.events.bus import EventBus
from codelab.client.infrastructure.repositories import InMemorySessionRepository
from codelab.client.infrastructure.services.acp_transport_service import ACPTransportService
from codelab.client.presentation.chat_view_model import ChatViewModel
from codelab.client.presentation.session_view_model import SessionViewModel
from codelab.client.presentation.ui_view_model import UIViewModel


class TestDIBootstrapper:
    """Тесты для DIBootstrapper."""

    def test_build_creates_container(self) -> None:
        """DIBootstrapper.build() создает DIContainer."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        assert isinstance(container, DIContainer)

    def test_build_registers_event_bus(self) -> None:
        """DIBootstrapper регистрирует EventBus."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        event_bus = container.resolve(EventBus)
        assert isinstance(event_bus, EventBus)

    def test_build_registers_transport_service(self) -> None:
        """DIBootstrapper регистрирует ACPTransportService."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        transport = container.resolve(ACPTransportService)
        assert isinstance(transport, ACPTransportService)
        assert transport.host == "localhost"
        assert transport.port == 8000

    def test_build_registers_session_repository(self) -> None:
        """DIBootstrapper регистрирует InMemorySessionRepository."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        repo = container.resolve(InMemorySessionRepository)
        assert isinstance(repo, InMemorySessionRepository)

    def test_build_registers_session_coordinator(self) -> None:
        """DIBootstrapper регистрирует SessionCoordinator."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        coordinator = container.resolve(SessionCoordinator)
        assert isinstance(coordinator, SessionCoordinator)

    def test_build_registers_all_view_models(self) -> None:
        """DIBootstrapper регистрирует все ViewModels."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        ui_vm = container.resolve(UIViewModel)
        session_vm = container.resolve(SessionViewModel)
        chat_vm = container.resolve(ChatViewModel)

        assert isinstance(ui_vm, UIViewModel)
        assert isinstance(session_vm, SessionViewModel)
        assert isinstance(chat_vm, ChatViewModel)

    def test_build_creates_singletons(self) -> None:
        """Все зарегистрированные сервисы - синглтоны."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        # Получаем сервисы несколько раз
        event_bus_1 = container.resolve(EventBus)
        event_bus_2 = container.resolve(EventBus)

        ui_vm_1 = container.resolve(UIViewModel)
        ui_vm_2 = container.resolve(UIViewModel)

        # Проверяем что это одни и те же экземпляры
        assert event_bus_1 is event_bus_2
        assert ui_vm_1 is ui_vm_2

    def test_build_with_different_host_port(self) -> None:
        """DIBootstrapper.build() используется с разными хостом и портом."""
        container1 = DIBootstrapper.build(host="localhost", port=8000)
        container2 = DIBootstrapper.build(host="example.com", port=9000)

        transport1 = container1.resolve(ACPTransportService)
        transport2 = container2.resolve(ACPTransportService)

        assert transport1.host == "localhost"
        assert transport1.port == 8000
        assert transport2.host == "example.com"
        assert transport2.port == 9000

    def test_build_passes_history_dir_to_chat_view_model(self, tmp_path) -> None:
        """DIBootstrapper передает history_dir в ChatViewModel."""
        history_dir = tmp_path / "custom-history"

        container = DIBootstrapper.build(
            host="localhost",
            port=8000,
            history_dir=str(history_dir),
        )
        chat_vm = container.resolve(ChatViewModel)

        assert chat_vm._history_dir == history_dir

    def test_build_handles_errors(self) -> None:
        """DIBootstrapper выбрасывает RuntimeError при ошибке."""
        # Имитируем ошибку при создании сервиса
        with (
            patch(
                "acp_client.infrastructure.di_bootstrapper.EventBus",
                side_effect=Exception("Test error"),
            ),
            pytest.raises(RuntimeError, match="Failed to build DI container"),
        ):
            DIBootstrapper.build(host="localhost", port=8000)


class TestDIBootstrapperIntegration:
    """Интеграционные тесты для DIBootstrapper."""

    def test_bootstrapped_services_are_connected(self) -> None:
        """Собранные сервисы корректно связаны друг с другом."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        coordinator = container.resolve(SessionCoordinator)
        transport = container.resolve(ACPTransportService)
        repo = container.resolve(InMemorySessionRepository)

        # Проверяем что координатор использует нужные сервисы
        assert coordinator.transport is transport
        assert coordinator.session_repo is repo

    def test_view_models_have_correct_dependencies(self) -> None:
        """ViewModels имеют правильные зависимости."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        session_vm = container.resolve(SessionViewModel)
        chat_vm = container.resolve(ChatViewModel)
        event_bus = container.resolve(EventBus)

        # Проверяем что ViewModels получили EventBus
        assert session_vm.event_bus is event_bus
        assert chat_vm.event_bus is event_bus

    def test_container_ready_for_application(self) -> None:
        """Контейнер готов к использованию приложением."""
        container = DIBootstrapper.build(host="localhost", port=8000)

        # Проверяем что все необходимые сервисы доступны
        services = [
            (EventBus, EventBus),
            (ACPTransportService, ACPTransportService),
            (InMemorySessionRepository, InMemorySessionRepository),
            (SessionCoordinator, SessionCoordinator),
            (UIViewModel, UIViewModel),
            (SessionViewModel, SessionViewModel),
            (ChatViewModel, ChatViewModel),
        ]

        for interface, expected_type in services:
            service = container.resolve(interface)
            assert isinstance(service, expected_type), (
                f"Service {interface.__name__} is not registered correctly"
            )
