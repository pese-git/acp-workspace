"""Dependency Injection Container - управление зависимостями приложения.

DIContainer инкапсулирует создание и управление всеми сервисами,
repositories и use cases. Позволяет легко переключать реализации,
например для тестирования.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any, Generic, TypeVar, cast

import structlog

# Типы для DI
T = TypeVar("T")


class Scope(Enum):
    """Области видимости для создания объектов."""
    
    SINGLETON = "singleton"
    """Один экземпляр на всё время жизни контейнера."""
    
    TRANSIENT = "transient"
    """Новый экземпляр при каждом запросе."""
    
    SCOPED = "scoped"
    """Один экземпляр на scope."""


class DIContainer:
    """Lightweight DI контейнер для управления зависимостями.
    
    Поддерживает:
    - Регистрацию интерфейсов с реализациями
    - Разные области видимости (singleton, transient, scoped)
    - Автоматическое разрешение зависимостей
    - Factories для сложного создания объектов
    """
    
    def __init__(self) -> None:
        """Инициализирует контейнер."""
        self._registrations: dict[type[Any], Registration[Any]] = {}
        self._singletons: dict[type[Any], Any] = {}
        self._logger = structlog.get_logger("di_container")
    
    def register(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T] | T,
        scope: Scope = Scope.SINGLETON,
    ) -> None:
        """Регистрирует сервис в контейнере.
        
        Аргументы:
            interface: Интерфейс (абстрактный класс или Protocol)
            implementation: Реализация (класс, factory функция или экземпляр)
            scope: Область видимости
        
        Примеры:
            # Класс-реализация
            container.register(TransportService, WebSocketTransport)
            
            # Factory функция
            container.register(
                SessionRepository,
                lambda: InMemorySessionRepository(),
                Scope.SINGLETON
            )
            
            # Готовый экземпляр
            logger = MyLogger()
            container.register(Logger, logger, Scope.SINGLETON)
        """
        registration = Registration(implementation, scope)
        self._registrations[interface] = registration
        
        self._logger.debug(
            "registered_service",
            interface=interface.__name__,
            scope=scope.value,
        )
    
    def resolve(self, interface: type[T]) -> T:
        """Разрешает сервис из контейнера.
        
        Аргументы:
            interface: Интерфейс для разрешения
        
        Возвращает:
            Экземпляр сервиса
        
        Raises:
            DIError: Если интерфейс не зарегистрирован
        """
        if interface not in self._registrations:
            msg = f"Service {interface.__name__} not registered"
            self._logger.error("service_not_found", interface=interface.__name__)
            raise DIError(msg)
        
        registration = self._registrations[interface]
        
        # Singleton - возвращаем кэшированный экземпляр
        if registration.scope == Scope.SINGLETON:
            if interface not in self._singletons:
                self._singletons[interface] = registration.create()
            return cast(T, self._singletons[interface])
        
        # Transient - создаем новый экземпляр каждый раз
        if registration.scope == Scope.TRANSIENT:
            return cast(T, registration.create())
        
        # Scoped - в этой реализации работает как singleton
        # TODO: реализовать настоящие scopes для requests
        if interface not in self._singletons:
            self._singletons[interface] = registration.create()
        return cast(T, self._singletons[interface])
    
    def clear(self) -> None:
        """Очищает контейнер и все singleton экземпляры."""
        self._registrations.clear()
        self._singletons.clear()
        self._logger.info("container_cleared")
    
    def unregister(self, interface: type[Any]) -> None:
        """Удаляет регистрацию сервиса.
        
        Аргументы:
            interface: Интерфейс для удаления
        """
        self._registrations.pop(interface, None)
        self._singletons.pop(interface, None)
        
        self._logger.debug("service_unregistered", interface=interface.__name__)
    
    def dispose(self) -> None:
        """Освобождает ресурсы и очищает все singleton экземпляры.
        
        Вызывает cleanup() или close() методы у всех синглтонов, если они существуют.
        Используйте этот метод при завершении приложения для корректной очистки.
        
        Пример:
            >>> container = DIContainer()
            >>> # ... использовать контейнер ...
            >>> container.dispose()  # Очистить перед выходом
        """
        # Пытаемся вызвать cleanup/close методы у синглтонов
        for interface, instance in list(self._singletons.items()):
            try:
                # Пытаемся вызвать cleanup() или __exit__() методы
                if hasattr(instance, "cleanup") and callable(instance.cleanup):
                    self._logger.debug(
                        "calling_cleanup_on_singleton",
                        interface=interface.__name__,
                    )
                    instance.cleanup()
                elif hasattr(instance, "close") and callable(instance.close):
                    self._logger.debug(
                        "calling_close_on_singleton",
                        interface=interface.__name__,
                    )
                    instance.close()
            except Exception as e:
                self._logger.exception(
                    "error_disposing_singleton",
                    interface=interface.__name__,
                    error=str(e),
                )
        
        # Очищаем все синглтоны
        self._singletons.clear()
        self._logger.info("container_disposed")


class Registration(Generic[T]):  # noqa: UP046
    """Регистрация сервиса в контейнере.
    
    Содержит информацию о том, как создать экземпляр сервиса.
    """
    
    def __init__(
        self,
        implementation: type[T] | Callable[..., T] | T,
        scope: Scope,
    ) -> None:
        """Инициализирует регистрацию.
        
        Аргументы:
            implementation: Реализация (класс, factory или экземпляр)
            scope: Область видимости
        """
        self.implementation = implementation
        self.scope = scope
    
    def create(self) -> T:
        """Создает экземпляр сервиса.
        
        Логика:
        1. Если это класс/тип - создаем новый экземпляр без аргументов
        2. Если это callable (factory функция) - вызываем её
        3. Иначе - это готовый экземпляр, возвращаем как есть
        
        Возвращает:
            Новый экземпляр сервиса или готовый экземпляр
        """
        # Если это класс, создаем новый экземпляр без аргументов
        if isinstance(self.implementation, type):
            return cast(T, self.implementation())
        
        # Если это callable функция/factory, вызываем её
        if callable(self.implementation):
            return cast(T, self.implementation())  # type: ignore[misc]
        
        # Иначе это готовый экземпляр - возвращаем как есть
        return cast(T, self.implementation)


class DIError(Exception):
    """Ошибка Dependency Injection контейнера."""
    
    pass


class ContainerBuilder:
    """Builder для удобной конфигурации DIContainer.
    
    Предоставляет fluent API для регистрации сервисов.
    
    Пример:
        container = (
            ContainerBuilder()
            .register_singleton(TransportService, WebSocketTransport)
            .register_singleton(SessionRepository, InMemorySessionRepository)
            .register_transient(CreateSessionUseCase)
            .build()
        )
    """
    
    def __init__(self) -> None:
        """Инициализирует builder."""
        self._container = DIContainer()
    
    def register_singleton(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T] | T | None = None,
    ) -> ContainerBuilder:
        """Регистрирует singleton сервис.
        
        Аргументы:
            interface: Интерфейс
            implementation: Реализация (если None, используется interface как реализация)
        
        Возвращает:
            self для chaining
        """
        impl = implementation if implementation is not None else interface
        self._container.register(interface, impl, Scope.SINGLETON)
        return self
    
    def register_transient(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ) -> ContainerBuilder:
        """Регистрирует transient сервис.
        
        Аргументы:
            interface: Интерфейс
            implementation: Реализация (если None, используется interface как реализация)
        
        Возвращает:
            self для chaining
        """
        impl = implementation if implementation is not None else interface
        self._container.register(interface, impl, Scope.TRANSIENT)
        return self
    
    def register_scoped(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ) -> ContainerBuilder:
        """Регистрирует scoped сервис.
        
        Аргументы:
            interface: Интерфейс
            implementation: Реализация (если None, используется interface как реализация)
        
        Возвращает:
            self для chaining
        """
        impl = implementation if implementation is not None else interface
        self._container.register(interface, impl, Scope.SCOPED)
        return self
    
    def build(self) -> DIContainer:
        """Собирает контейнер.
        
        Возвращает:
            Готовый DIContainer
        """
        return self._container
