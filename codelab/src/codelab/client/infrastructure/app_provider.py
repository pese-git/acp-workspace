"""dishka Provider — декларативная конфигурация зависимостей клиентского приложения.

Заменяет самописный DIContainer + DIBootstrapper + ViewModelFactory.
Dishka автоматически разрешает зависимости по аннотациям типов.
Async lifecycle (AsyncIterator) гарантирует корректное закрытие ресурсов.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import structlog
from dishka import Provider, Scope, provide

from codelab.client.application.permission_handler import PermissionHandler
from codelab.client.application.session_coordinator import SessionCoordinator
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

logger = structlog.get_logger("app_provider")


class AppProvider(Provider):
    """Декларативный провайдер всех зависимостей приложения.

    Dishka автоматически разрешает зависимости по аннотациям типов.
    Async lifecycle (AsyncIterator) гарантирует корректное закрытие ресурсов.
    """

    scope = Scope.APP  # Все сервисы — singleton на время жизни приложения

    def __init__(self, host: str, port: int, cwd: str, history_dir: str | None = None):
        super().__init__()
        self._host = host
        self._port = port
        self._cwd = cwd
        self._history_dir = history_dir

    # --- Инфраструктурные сервисы ---

    @provide
    def event_bus(self) -> EventBus:
        return EventBus()

    @provide
    def permission_callback_registry(self) -> PermissionCallbackRegistry:
        return PermissionCallbackRegistry()

    @provide
    async def transport(
        self,
        event_bus: EventBus,
        permission_callback_registry: PermissionCallbackRegistry,
    ) -> AsyncIterator[ACPTransportService]:
        """Транспортный сервис с гарантированным async закрытием."""
        service = ACPTransportService(
            host=self._host,
            port=self._port,
            event_bus=event_bus,
            permission_callback_registry=permission_callback_registry,
        )
        yield service
        # Этот код выполнится при завершении приложения:
        await service.disconnect()
        logger.debug("transport_closed")

    @provide
    def session_repository(self) -> InMemorySessionRepository:
        return InMemorySessionRepository()

    @provide
    def fs_executor(self) -> FileSystemExecutor:
        return FileSystemExecutor(base_path=Path(self._cwd))

    @provide
    async def terminal_executor(self) -> AsyncIterator[TerminalExecutor]:
        executor = TerminalExecutor()
        yield executor
        await executor.cleanup_all()
        logger.debug("terminal_executor_cleaned_up")

    # --- Обработчики ---

    @provide
    def fs_handler(
        self,
        executor: FileSystemExecutor,
    ) -> FileSystemHandler:
        return FileSystemHandler(executor=executor)

    @provide
    def terminal_handler(self, executor: TerminalExecutor) -> TerminalHandler:
        return TerminalHandler(executor)

    # --- Application слой ---

    @provide
    def session_coordinator(
        self,
        transport: ACPTransportService,
        session_repo: InMemorySessionRepository,
        permission_handler: PermissionHandler,
    ) -> SessionCoordinator:
        """Цикл разорван: SessionCoordinator получает PermissionHandler напрямую."""
        return SessionCoordinator(
            transport=transport,
            session_repo=session_repo,
            permission_handler=permission_handler,
        )

    @provide
    def permission_handler(
        self,
        event_bus: EventBus,
        permission_callback_registry: PermissionCallbackRegistry,
    ) -> PermissionHandler:
        """Цикл разорван: PermissionHandler общается через EventBus."""
        return PermissionHandler(
            event_bus=event_bus,
            permission_callback_registry=permission_callback_registry,
            logger=logger,
        )

    # --- ViewModels ---

    @provide
    def ui_view_model(self, event_bus: EventBus) -> UIViewModel:
        return UIViewModel(event_bus=event_bus, logger=logger)

    @provide
    def session_view_model(
        self, coordinator: SessionCoordinator, event_bus: EventBus
    ) -> SessionViewModel:
        return SessionViewModel(coordinator=coordinator, event_bus=event_bus, logger=logger)

    @provide
    def plan_view_model(self, event_bus: EventBus) -> PlanViewModel:
        return PlanViewModel(event_bus=event_bus, logger=logger)

    @provide
    def chat_view_model(
        self,
        coordinator: SessionCoordinator,
        event_bus: EventBus,
        fs_executor: FileSystemExecutor,
        terminal_executor: TerminalExecutor,
        plan_vm: PlanViewModel,
    ) -> ChatViewModel:
        return ChatViewModel(
            coordinator=coordinator,
            event_bus=event_bus,
            logger=logger,
            history_dir=self._history_dir,
            fs_executor=fs_executor,
            terminal_executor=terminal_executor,
            plan_vm=plan_vm,
        )

    @provide
    def terminal_view_model(self, event_bus: EventBus) -> TerminalViewModel:
        return TerminalViewModel(event_bus=event_bus, logger=logger)

    @provide
    def filesystem_view_model(self, event_bus: EventBus) -> FileSystemViewModel:
        return FileSystemViewModel(event_bus=event_bus, logger=logger)

    @provide
    def file_viewer_view_model(self, event_bus: EventBus) -> FileViewerViewModel:
        return FileViewerViewModel(event_bus=event_bus, logger=logger)

    @provide
    def permission_view_model(self, event_bus: EventBus) -> PermissionViewModel:
        return PermissionViewModel(event_bus=event_bus, logger=logger)

    @provide
    def terminal_log_view_model(self, event_bus: EventBus) -> TerminalLogViewModel:
        return TerminalLogViewModel(event_bus=event_bus, logger=logger)
