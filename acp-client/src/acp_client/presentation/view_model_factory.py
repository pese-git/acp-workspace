"""ViewModelFactory для регистрации ViewModels в DIContainer.

Предоставляет единую точку входа для настройки всех ViewModels
и их регистрации в Dependency Injection контейнере.
"""

from typing import Any

import structlog

from acp_client.infrastructure.di_container import DIContainer, Scope
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.session_view_model import SessionViewModel
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
        chat_vm = ChatViewModel(
            coordinator=session_coordinator,
            event_bus=event_bus,
            logger=logger,
        )
        container.register(ChatViewModel, chat_vm, Scope.SINGLETON)
        logger.debug(
            "registered_view_model",
            vm_class="ChatViewModel",
            scope="SINGLETON",
        )
        
        logger.info("view_models_registered", count=3)
