"""Базовый класс для всех ViewModels.

BaseViewModel предоставляет механизмы для интеграции с EventBus,
логирования и управления lifecycle.
"""

from collections.abc import Callable
from contextlib import suppress
from typing import Any

import structlog

# Типы для событий (из Phase 3)
try:
    from acp_client.domain.events import DomainEvent
except ImportError:
    # Fallback если domain модуль еще не доступен
    DomainEvent = Any


class BaseViewModel:
    """Базовый класс для всех ViewModels.
    
    Предоставляет:
    - Интеграцию с EventBus для реактивных обновлений
    - Структурированное логирование
    - Управление subscriptions на события
    
    Все ViewModels должны наследоваться от этого класса.
    
    Пример:
        >>> class MyViewModel(BaseViewModel):
        ...     def __init__(self, event_bus=None):
        ...         super().__init__(event_bus)
        ...         self.data = Observable("initial")
        ...         self.on_event(SomeEvent, self._handle_event)
        ...
        ...     def _handle_event(self, event):
        ...         self.data.value = event.data
    """

    def __init__(self, event_bus: Any | None = None, logger: Any | None = None) -> None:
        """Инициализировать ViewModel.
        
        Args:
            event_bus: Шина событий (EventBus) для публикации/подписки на события
            logger: Logger для структурированного логирования
        """
        self.event_bus = event_bus
        self.logger = logger or structlog.get_logger()
        # Храним unsubscribe функции для очистки при уничтожении
        self._subscriptions: dict[str, Callable[[], None]] = {}
        self.logger.debug("ViewModel initialized", vm_class=self.__class__.__name__)

    def on_event(
        self,
        event_type: type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        """Подписаться на доменное событие.
        
        Когда событие опубликуется в EventBus, handler будет вызван.
        
        Args:
            event_type: Тип события для подписки
            handler: Функция-обработчик события
            
        Пример:
            >>> self.on_event(SessionCreatedEvent, self._on_session_created)
        """
        if not self.event_bus:
            self.logger.warning("EventBus not available, event subscription ignored")
            return

        try:
            # EventBus.subscribe возвращает unsubscribe функцию или ничего не возвращает
            # В зависимости от реализации EventBus из Phase 3
            self.event_bus.subscribe(event_type, handler)
            self.logger.debug(
                "Subscribed to event",
                event_type=event_type.__name__,
                handler=handler.__name__,
            )
        except Exception as e:
            self.logger.exception(
                "Error subscribing to event",
                event_type=event_type.__name__,
                error=str(e),
            )

    def publish_event(self, event: DomainEvent) -> None:
        """Опубликовать доменное событие.
        
        Событие будет отправлено всем подписанным observers.
        
        Args:
            event: Событие для публикации
            
        Пример:
            >>> event = SessionCreatedEvent(...)
            >>> self.publish_event(event)
        """
        if not self.event_bus:
            self.logger.warning("EventBus not available, event publication ignored")
            return

        try:
            self.event_bus.publish(event)
            self.logger.debug(
                "Event published",
                event_type=event.__class__.__name__,
                aggregate_id=getattr(event, 'aggregate_id', 'unknown'),
            )
        except Exception as e:
            self.logger.exception(
                "Error publishing event",
                event_type=event.__class__.__name__,
                error=str(e),
            )

    def cleanup(self) -> None:
        """Очистить ресурсы при уничтожении ViewModel.
        
        Должен быть вызван перед удалением ViewModel чтобы
        избежать утечек памяти от невычищенных subscriptions.
        
        Пример:
            >>> vm = MyViewModel(event_bus)
            >>> # ... использовать vm ...
            >>> vm.cleanup()  # Очистить перед удалением
        """
        for unsubscribe_fn in self._subscriptions.values():
            try:
                unsubscribe_fn()
            except Exception as e:
                self.logger.exception(
                    "Error unsubscribing",
                    error=str(e),
                )
        self._subscriptions.clear()
        self.logger.debug("ViewModel cleaned up", vm_class=self.__class__.__name__)

    def __del__(self) -> None:
        """Автоматически очистить при удалении объекта."""
        with suppress(Exception):
            # Не логируем ошибки в __del__ так как logger может быть уже удален
            self.cleanup()
