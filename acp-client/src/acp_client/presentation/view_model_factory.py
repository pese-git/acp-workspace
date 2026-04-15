"""ViewModelFactory для регистрации ViewModels в DIContainer.

Предоставляет единую точку входа для настройки всех ViewModels
и их регистрации в Dependency Injection контейнере.
"""

from pathlib import Path
from typing import Any

import structlog

from acp_client.infrastructure.di_container import DIContainer, Scope
from acp_client.infrastructure.services.file_system_executor import FileSystemExecutor
from acp_client.infrastructure.services.terminal_executor import TerminalExecutor
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.file_viewer_view_model import FileViewerViewModel
from acp_client.presentation.filesystem_view_model import FileSystemViewModel
from acp_client.presentation.permission_view_model import PermissionViewModel
from acp_client.presentation.plan_view_model import PlanViewModel
from acp_client.presentation.session_view_model import SessionViewModel
from acp_client.presentation.terminal_log_view_model import TerminalLogViewModel
from acp_client.presentation.terminal_view_model import TerminalViewModel
from acp_client.presentation.ui_view_model import UIViewModel


class ViewModelFactory:
    """Factory для регистрации всех ViewModels в DIContainer.

    Обеспечивает:
    - Централизованную регистрацию всех ViewModels
    - Конфигурацию с опциональным EventBus
    - Singleton scope для ViewModels (один экземпляр на приложение)

    Пример использования:
        >>> container = DIContainer()
        >>> ViewModelFactory.register_view_models(container, event_bus=event_bus)
        >>>
        >>> # Получить ViewModel из контейнера
        >>> ui_vm = container.resolve(UIViewModel)
        >>> session_vm = container.resolve(SessionViewModel)
        >>> chat_vm = container.resolve(ChatViewModel)
    """

    @staticmethod
    def register_view_models(
        container: DIContainer,
        session_coordinator: Any,  # Обязательный параметр
        event_bus: Any | None = None,
        logger: Any | None = None,
        history_dir: Path | str | None = None,
    ) -> None:
        """Регистрирует все ViewModels как singletons в контейнере.

        Создает и регистрирует три основных ViewModels:
        - UIViewModel: управление глобальным UI состоянием (соединение, ошибки, модалы)
        - SessionViewModel: управление сессиями (список, выбор, операции)
        - ChatViewModel: управление чатом (сообщения, streaming, tool calls)

        Args:
            container: DIContainer для регистрации ViewModels
            session_coordinator: SessionCoordinator для ViewModels (ТРЕБУЕТСЯ)
            event_bus: EventBus для публикации/подписки на события (опционально)
            logger: Logger для структурированного логирования (опционально)
            history_dir: Директория локального persistence истории чата (опционально)

        Raises:
            TypeError: Если session_coordinator не передан или None
        """
        if session_coordinator is None:
            raise TypeError(
                "session_coordinator is required for ViewModelFactory.register_view_models(). "
                "Cannot create SessionViewModel and ChatViewModel without coordinator."
            )

        if logger is None:
            logger = structlog.get_logger("view_model_factory")

        logger.info(
            "registering_view_models",
            event_bus_present=event_bus is not None,
        )

        # Регистрируем UIViewModel - синглтон для глобального UI состояния
        ui_vm = UIViewModel(event_bus=event_bus, logger=logger)
        container.register(UIViewModel, ui_vm, Scope.SINGLETON)
        logger.debug("registered_view_model", vm_class="UIViewModel", scope="SINGLETON")

        # Регистрируем SessionViewModel - синглтон для управления сессиями
        session_vm = SessionViewModel(
            coordinator=session_coordinator,
            event_bus=event_bus,
            logger=logger,
        )
        container.register(SessionViewModel, session_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="SessionViewModel",
            scope="SINGLETON",
        )

        # Регистрируем ChatViewModel - синглтон для управления чатом
        fs_executor = container.resolve(FileSystemExecutor)
        terminal_executor = container.resolve(TerminalExecutor)
        chat_vm = ChatViewModel(
            coordinator=session_coordinator,
            event_bus=event_bus,
            logger=logger,
            history_dir=history_dir,
            fs_executor=fs_executor,
            terminal_executor=terminal_executor,
        )
        container.register(ChatViewModel, chat_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="ChatViewModel",
            scope="SINGLETON",
        )

        # Регистрируем PlanViewModel - синглтон для управления планом
        plan_vm = PlanViewModel(event_bus=event_bus, logger=logger)
        container.register(PlanViewModel, plan_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="PlanViewModel",
            scope="SINGLETON",
        )

        # Регистрируем TerminalViewModel - синглтон для управления терминалом
        terminal_vm = TerminalViewModel(event_bus=event_bus, logger=logger)
        container.register(TerminalViewModel, terminal_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="TerminalViewModel",
            scope="SINGLETON",
        )

        # Регистрируем FileSystemViewModel - синглтон для управления файловой системой
        filesystem_vm = FileSystemViewModel(event_bus=event_bus, logger=logger)
        container.register(FileSystemViewModel, filesystem_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="FileSystemViewModel",
            scope="SINGLETON",
        )

        # Регистрируем FileViewerViewModel - синглтон для просмотра файлов
        file_viewer_vm = FileViewerViewModel(event_bus=event_bus, logger=logger)
        container.register(FileViewerViewModel, file_viewer_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="FileViewerViewModel",
            scope="SINGLETON",
        )

        # Регистрируем PermissionViewModel - синглтон для управления разрешениями
        permission_vm = PermissionViewModel(event_bus=event_bus, logger=logger)
        container.register(PermissionViewModel, permission_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="PermissionViewModel",
            scope="SINGLETON",
        )

        # Регистрируем TerminalLogViewModel - синглтон для просмотра логов терминала
        terminal_log_vm = TerminalLogViewModel(event_bus=event_bus, logger=logger)
        container.register(TerminalLogViewModel, terminal_log_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="TerminalLogViewModel",
            scope="SINGLETON",
        )

        logger.info("view_models_registered", count=9)
