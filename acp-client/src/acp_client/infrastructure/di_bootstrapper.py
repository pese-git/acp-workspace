"""DIBootstrapper - централизованная конфигурация Dependency Injection контейнера.

Обеспечивает единую точку входа для инициализации всех сервисов,
repositories и ViewModels приложения.

Пример использования:
    >>> container = DIBootstrapper.build(host="localhost", port=8000, cwd="/path/to/project")
    >>> app = ACPClientApp(host="localhost", port=8000, cwd="/path/to/project", container=container)
"""

import os
from pathlib import Path
from typing import Any

import structlog

from acp_client.application.permission_handler import PermissionHandler
from acp_client.application.session_coordinator import SessionCoordinator
from acp_client.infrastructure.di_container import ContainerBuilder
from acp_client.infrastructure.events.bus import EventBus
from acp_client.infrastructure.handlers import FileSystemHandler, TerminalHandler
from acp_client.infrastructure.repositories import InMemorySessionRepository
from acp_client.infrastructure.services.acp_transport_service import ACPTransportService
from acp_client.infrastructure.services.file_system_executor import FileSystemExecutor
from acp_client.infrastructure.services.terminal_executor import TerminalExecutor
from acp_client.presentation.view_model_factory import ViewModelFactory


class DIBootstrapper:
    """Инициализирует и конфигурирует DIContainer для приложения.

    Регистрирует все необходимые сервисы в порядке их зависимостей:
    1. EventBus - шина событий
    2. TransportService - низкоуровневая коммуникация
    3. SessionRepository - хранилище сессий
    4. PermissionHandler - обработка permission requests
    5. SessionCoordinator - оркестрация операций
    6. ViewModels - слой представления
    """

    @staticmethod
    def build(
        host: str,
        port: int,
        cwd: str | None = None,
        history_dir: str | None = None,
        logger: Any | None = None,
    ) -> Any:
        """Собирает и конфигурирует DIContainer.

        Регистрирует все сервисы и ViewModels в правильном порядке.

        Args:
            host: Адрес сервера ACP
            port: Порт сервера ACP
            cwd: Абсолютный путь к рабочей директории проекта (если None, используется текущая)
            history_dir: Путь к директории локальной истории чата (опционально)
            logger: Logger для структурированного логирования (опционально)

        Returns:
            Готовый и полностью сконфигурированный DIContainer

        Raises:
            RuntimeError: Если произойдет ошибка при конфигурации контейнера
        """
        if logger is None:
            logger = structlog.get_logger("di_bootstrapper")

        # Если cwd не передан, используем текущую рабочую директорию
        if cwd is None:
            cwd = os.getcwd()

        logger.info("building_di_container", host=host, port=port, cwd=cwd)

        try:
            builder = ContainerBuilder()

            # 1. Регистрируем EventBus - шина событий для слабой связанности
            logger.debug("registering_event_bus")
            event_bus = EventBus()
            builder.register_singleton(EventBus, event_bus)

            # 2. Регистрируем TransportService - низкоуровневая коммуникация
            # Сначала без permission_handler, добавим позже
            logger.debug("registering_transport_service", host=host, port=port)
            transport_service = ACPTransportService(host=host, port=port)
            builder.register_singleton(ACPTransportService, transport_service)

            # 3. Регистрируем SessionRepository - хранилище сессий в памяти
            logger.debug("registering_session_repository")
            session_repo = InMemorySessionRepository()
            builder.register_singleton(InMemorySessionRepository, session_repo)

            # 4. Регистрируем FileSystem Executor и Handler
            logger.debug("registering_file_system_executor_and_handler")
            fs_executor = FileSystemExecutor(base_path=Path(cwd))
            fs_handler = FileSystemHandler(fs_executor)
            builder.register_singleton(FileSystemExecutor, fs_executor)
            builder.register_singleton(FileSystemHandler, fs_handler)

            # 5. Регистрируем Terminal Executor и Handler
            logger.debug("registering_terminal_executor_and_handler")
            term_executor = TerminalExecutor()
            term_handler = TerminalHandler(term_executor)
            builder.register_singleton(TerminalExecutor, term_executor)
            builder.register_singleton(TerminalHandler, term_handler)

            # 6. Регистрируем SessionCoordinator - оркестрация операций
            # Требует TransportService и SessionRepository
            # PermissionHandler добавим позже (circular dependency resolution)
            logger.debug("registering_session_coordinator")
            coordinator = SessionCoordinator(
                transport=transport_service,
                session_repo=session_repo,
                permission_handler=None,  # Добавим после создания PermissionHandler
            )
            builder.register_singleton(SessionCoordinator, coordinator)

            # 7. Регистрируем PermissionHandler - обработка permission requests
            # Требует SessionCoordinator и TransportService
            logger.debug("registering_permission_handler")
            permission_handler = PermissionHandler(
                coordinator=coordinator,
                transport=transport_service,
                logger=logger,
            )
            builder.register_singleton(PermissionHandler, permission_handler)

            # 8. Обновляем зависимости - добавляем PermissionHandler в
            # SessionCoordinator и TransportService
            # Это разрешает циклическую зависимость:
            # - PermissionHandler зависит от SessionCoordinator и TransportService
            # - SessionCoordinator и TransportService зависят от PermissionHandler
            logger.debug("updating_permission_handler_dependencies")
            coordinator._permission_handler = permission_handler
            transport_service._permission_handler = permission_handler

            # 9. Собираем контейнер и регистрируем ViewModels
            container = builder.build()

            logger.debug("registering_view_models")
            ViewModelFactory.register_view_models(
                container,
                session_coordinator=coordinator,
                event_bus=event_bus,
                logger=logger,
                history_dir=history_dir,
            )

            logger.info("di_container_built_successfully")
            return container

        except Exception as e:
            logger.error(
                "failed_to_build_di_container",
                error=str(e),
            )
            raise RuntimeError(
                f"Failed to build DI container: {e}. Check logs for detailed error information."
            ) from e
