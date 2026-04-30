"""Тесты для dishka AppProvider — декларативной конфигурации DI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dishka import Provider, Scope, make_async_container, provide

from codelab.client.application.permission_handler import PermissionHandler
from codelab.client.application.session_coordinator import SessionCoordinator
from codelab.client.infrastructure.app_provider import AppProvider
from codelab.client.infrastructure.events.bus import EventBus
from codelab.client.infrastructure.events.permission_events import PermissionCallbackRegistry
from codelab.client.infrastructure.handlers.file_system_handler import FileSystemHandler
from codelab.client.infrastructure.handlers.terminal_handler import TerminalHandler
from codelab.client.infrastructure.repositories import InMemorySessionRepository
from codelab.client.infrastructure.services.acp_transport_service import ACPTransportService
from codelab.client.infrastructure.services.file_system_executor import FileSystemExecutor
from codelab.client.infrastructure.services.terminal_executor import TerminalExecutor
from codelab.client.presentation.chat_view_model import ChatViewModel
from codelab.client.presentation.file_viewer_view_model import FileViewerViewModel
from codelab.client.presentation.filesystem_view_model import FileSystemViewModel
from codelab.client.presentation.permission_view_model import PermissionViewModel
from codelab.client.presentation.plan_view_model import PlanViewModel
from codelab.client.presentation.session_view_model import SessionViewModel
from codelab.client.presentation.terminal_log_view_model import TerminalLogViewModel
from codelab.client.presentation.terminal_view_model import TerminalViewModel
from codelab.client.presentation.ui_view_model import UIViewModel


@pytest.fixture
def host() -> str:
    return "localhost"


@pytest.fixture
def port() -> int:
    return 8765


@pytest.fixture
def cwd() -> str:
    return "/tmp"


@pytest.fixture
def provider(host: str, port: int, cwd: str) -> AppProvider:
    return AppProvider(host=host, port=port, cwd=cwd)


@pytest.fixture
async def container(provider: AppProvider):
    async with make_async_container(provider) as ctx:
        yield ctx


class TestAppProviderInfrastructure:
    """Тесты инфраструктурных сервисов."""

    @pytest.mark.asyncio
    async def test_event_bus_resolved(self, container):
        event_bus = await container.get(EventBus)
        assert isinstance(event_bus, EventBus)

    @pytest.mark.asyncio
    async def test_permission_callback_registry_resolved(self, container):
        registry = await container.get(PermissionCallbackRegistry)
        assert isinstance(registry, PermissionCallbackRegistry)

    @pytest.mark.asyncio
    async def test_transport_resolved(self, container):
        transport = await container.get(ACPTransportService)
        assert isinstance(transport, ACPTransportService)
        assert transport.host == "localhost"
        assert transport.port == 8765

    @pytest.mark.asyncio
    async def test_session_repository_resolved(self, container):
        repo = await container.get(InMemorySessionRepository)
        assert isinstance(repo, InMemorySessionRepository)

    @pytest.mark.asyncio
    async def test_fs_executor_resolved(self, container):
        executor = await container.get(FileSystemExecutor)
        assert isinstance(executor, FileSystemExecutor)
        assert executor.base_path == Path("/tmp")

    @pytest.mark.asyncio
    async def test_terminal_executor_resolved(self, container):
        executor = await container.get(TerminalExecutor)
        assert isinstance(executor, TerminalExecutor)

    @pytest.mark.asyncio
    async def test_fs_handler_resolved(self, container):
        handler = await container.get(FileSystemHandler)
        assert isinstance(handler, FileSystemHandler)

    @pytest.mark.asyncio
    async def test_terminal_handler_resolved(self, container):
        handler = await container.get(TerminalHandler)
        assert isinstance(handler, TerminalHandler)


class TestAppProviderApplication:
    """Тесты application слоя."""

    @pytest.mark.asyncio
    async def test_permission_handler_resolved(self, container):
        handler = await container.get(PermissionHandler)
        assert isinstance(handler, PermissionHandler)

    @pytest.mark.asyncio
    async def test_session_coordinator_resolved(self, container):
        coordinator = await container.get(SessionCoordinator)
        assert isinstance(coordinator, SessionCoordinator)

    @pytest.mark.asyncio
    async def test_coordinator_has_permission_handler(self, container):
        coordinator = await container.get(SessionCoordinator)
        assert coordinator._permission_handler is not None
        assert isinstance(coordinator._permission_handler, PermissionHandler)

    @pytest.mark.asyncio
    async def test_no_circular_dependency(self, container):
        """Циклическая зависимость разорвана через EventBus."""
        coordinator = await container.get(SessionCoordinator)
        permission_handler = await container.get(PermissionHandler)
        transport = await container.get(ACPTransportService)

        # SessionCoordinator имеет PermissionHandler
        assert coordinator._permission_handler is permission_handler

        # PermissionHandler НЕ имеет SessionCoordinator (разорван цикл)
        # Вместо этого использует EventBus
        assert not hasattr(permission_handler, '_coordinator')

        # ACPTransportService НЕ имеет PermissionHandler (разорван цикл)
        # Вместо этого использует EventBus и PermissionCallbackRegistry
        assert not hasattr(transport, '_permission_handler')


class TestAppProviderViewModels:
    """Тесты ViewModels."""

    @pytest.mark.asyncio
    async def test_ui_view_model_resolved(self, container):
        vm = await container.get(UIViewModel)
        assert isinstance(vm, UIViewModel)

    @pytest.mark.asyncio
    async def test_session_view_model_resolved(self, container):
        vm = await container.get(SessionViewModel)
        assert isinstance(vm, SessionViewModel)

    @pytest.mark.asyncio
    async def test_plan_view_model_resolved(self, container):
        vm = await container.get(PlanViewModel)
        assert isinstance(vm, PlanViewModel)

    @pytest.mark.asyncio
    async def test_chat_view_model_resolved(self, container):
        vm = await container.get(ChatViewModel)
        assert isinstance(vm, ChatViewModel)

    @pytest.mark.asyncio
    async def test_terminal_view_model_resolved(self, container):
        vm = await container.get(TerminalViewModel)
        assert isinstance(vm, TerminalViewModel)

    @pytest.mark.asyncio
    async def test_filesystem_view_model_resolved(self, container):
        vm = await container.get(FileSystemViewModel)
        assert isinstance(vm, FileSystemViewModel)

    @pytest.mark.asyncio
    async def test_file_viewer_view_model_resolved(self, container):
        vm = await container.get(FileViewerViewModel)
        assert isinstance(vm, FileViewerViewModel)

    @pytest.mark.asyncio
    async def test_permission_view_model_resolved(self, container):
        vm = await container.get(PermissionViewModel)
        assert isinstance(vm, PermissionViewModel)

    @pytest.mark.asyncio
    async def test_terminal_log_view_model_resolved(self, container):
        vm = await container.get(TerminalLogViewModel)
        assert isinstance(vm, TerminalLogViewModel)


class TestAppProviderLifecycle:
    """Тесты lifecycle и async cleanup."""

    @pytest.mark.asyncio
    async def test_container_closes_cleanly(self, host, port, cwd):
        """Контейнер закрывается без ошибок, вызывая async cleanup."""
        provider = AppProvider(host=host, port=port, cwd=cwd)
        async with make_async_container(provider) as ctx:
            # Разрешаем все сервисы
            await ctx.get(ACPTransportService)
            await ctx.get(TerminalExecutor)

        # Контейнер закрыт — async cleanup вызван


class TestAppProviderWithTestOverrides:
    """Тесты с переопределением зависимостей для тестирования."""

    @pytest.mark.asyncio
    async def test_mock_transport_override(self, cwd):
        """Можно переопределить transport mock для тестирования."""

        class TestProvider(Provider):
            scope = Scope.APP

            @provide
            def transport(self) -> ACPTransportService:
                mock = MagicMock(spec=ACPTransportService)
                mock.host = "test"
                mock.port = 9999
                return mock

        app_provider = AppProvider(host="localhost", port=8765, cwd=cwd)
        test_provider = TestProvider()

        async with make_async_container(app_provider, test_provider) as ctx:
            transport = await ctx.get(ACPTransportService)
            assert transport.host == "test"
            assert transport.port == 9999
