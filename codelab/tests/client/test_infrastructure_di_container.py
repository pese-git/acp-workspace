"""Тесты для DI контейнера."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pytest

from codelab.client.infrastructure import (
    ContainerBuilder,
    DIContainer,
    DIError,
    Scope,
)


class MyService(ABC):
    """Тестовый интерфейс сервиса."""
    
    @abstractmethod
    def do_something(self) -> str:
        ...


class MyServiceImpl(MyService):
    """Реализация тестового сервиса."""
    
    def do_something(self) -> str:
        return "done"


class AnotherService:
    """Другой тестовый сервис."""
    
    def __init__(self, my_service: MyService | None = None) -> None:
        self.my_service = my_service


class TestDIContainer:
    """Тесты для DIContainer."""
    
    def test_register_and_resolve_class(self) -> None:
        """Тест регистрации и разрешения класса."""
        container = DIContainer()
        container.register(MyService, MyServiceImpl)
        
        service = container.resolve(MyService)
        assert isinstance(service, MyServiceImpl)
        assert service.do_something() == "done"
    
    def test_singleton_scope(self) -> None:
        """Тест что singleton возвращает один и тот же экземпляр."""
        container = DIContainer()
        container.register(MyService, MyServiceImpl, Scope.SINGLETON)
        
        service1 = container.resolve(MyService)
        service2 = container.resolve(MyService)
        
        assert service1 is service2
    
    def test_transient_scope(self) -> None:
        """Тест что transient создает новый экземпляр каждый раз."""
        container = DIContainer()
        container.register(MyService, MyServiceImpl, Scope.TRANSIENT)
        
        service1 = container.resolve(MyService)
        service2 = container.resolve(MyService)
        
        assert service1 is not service2
        assert isinstance(service1, MyServiceImpl)
        assert isinstance(service2, MyServiceImpl)
    
    def test_register_instance(self) -> None:
        """Тест регистрации готового экземпляра."""
        container = DIContainer()
        instance = MyServiceImpl()
        container.register(MyService, instance)
        
        resolved = container.resolve(MyService)
        assert resolved is instance
    
    def test_register_factory(self) -> None:
        """Тест регистрации factory функции."""
        container = DIContainer()
        
        def factory() -> MyService:
            return MyServiceImpl()
        
        container.register(MyService, factory)
        
        service = container.resolve(MyService)
        assert isinstance(service, MyServiceImpl)
    
    def test_unregister_service(self) -> None:
        """Тест удаления регистрации сервиса."""
        container = DIContainer()
        container.register(MyService, MyServiceImpl)
        
        container.unregister(MyService)
        
        with pytest.raises(DIError):
            container.resolve(MyService)
    
    def test_resolve_unregistered_service(self) -> None:
        """Тест что разрешение незарегистрированного сервиса выбрасывает ошибку."""
        container = DIContainer()
        
        with pytest.raises(DIError):
            container.resolve(MyService)
    
    def test_clear_container(self) -> None:
        """Тест очистки контейнера."""
        container = DIContainer()
        container.register(MyService, MyServiceImpl)
        
        container.clear()
        
        with pytest.raises(DIError):
            container.resolve(MyService)


class TestContainerBuilder:
    """Тесты для ContainerBuilder."""
    
    def test_builder_register_singleton(self) -> None:
        """Тест fluent API для регистрации singleton."""
        container = (
            ContainerBuilder()
            .register_singleton(MyService, MyServiceImpl)
            .build()
        )
        
        service1 = container.resolve(MyService)
        service2 = container.resolve(MyService)
        
        assert service1 is service2
    
    def test_builder_register_transient(self) -> None:
        """Тест fluent API для регистрации transient."""
        container = (
            ContainerBuilder()
            .register_transient(MyService, MyServiceImpl)
            .build()
        )
        
        service1 = container.resolve(MyService)
        service2 = container.resolve(MyService)
        
        assert service1 is not service2
    
    def test_builder_multiple_registrations(self) -> None:
        """Тест регистрации нескольких сервисов."""
        container = (
            ContainerBuilder()
            .register_singleton(MyService, MyServiceImpl)
            .register_singleton(AnotherService)
            .build()
        )
        
        service = container.resolve(MyService)
        another = container.resolve(AnotherService)
        
        assert isinstance(service, MyServiceImpl)
        assert isinstance(another, AnotherService)
    
    def test_builder_register_without_implementation(self) -> None:
        """Тест регистрации класса как сам себе реализации."""
        container = (
            ContainerBuilder()
            .register_singleton(MyServiceImpl)
            .build()
        )
        
        service = container.resolve(MyServiceImpl)
        assert isinstance(service, MyServiceImpl)
