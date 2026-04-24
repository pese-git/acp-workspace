"""Тесты для DIContainer.dispose() - очистки ресурсов.

Проверяет:
- Корректное вызывание cleanup/close методов
- Обработку ошибок при очистке
- Полную очистку синглтонов после dispose
"""

import pytest

from codelab.client.infrastructure.di_container import DIContainer, Scope


class ServiceWithCleanup:
    """Тестовый сервис с методом cleanup."""

    def __init__(self):
        self.cleanup_called = False

    def cleanup(self) -> None:
        """Метод очистки."""
        self.cleanup_called = True


class ServiceWithClose:
    """Тестовый сервис с методом close."""

    def __init__(self):
        self.close_called = False

    def close(self) -> None:
        """Метод закрытия."""
        self.close_called = True


class ServiceWithoutCleanup:
    """Тестовый сервис без методов очистки."""

    def __init__(self):
        self.value = "test"


class TestDIContainerDispose:
    """Тесты для DIContainer.dispose()."""

    def test_dispose_calls_cleanup_method(self) -> None:
        """dispose() вызывает cleanup() метод у синглтонов."""
        container = DIContainer()
        service = ServiceWithCleanup()
        container.register(ServiceWithCleanup, service, Scope.SINGLETON)

        # Получаем сервис чтобы он попал в _singletons
        resolved = container.resolve(ServiceWithCleanup)
        assert not resolved.cleanup_called

        # Вызываем dispose
        container.dispose()

        # Проверяем что cleanup был вызван
        assert resolved.cleanup_called

    def test_dispose_calls_close_method(self) -> None:
        """dispose() вызывает close() метод если cleanup не существует."""
        container = DIContainer()
        service = ServiceWithClose()
        container.register(ServiceWithClose, service, Scope.SINGLETON)

        # Получаем сервис чтобы он попал в _singletons
        resolved = container.resolve(ServiceWithClose)
        assert not resolved.close_called

        # Вызываем dispose
        container.dispose()

        # Проверяем что close был вызван
        assert resolved.close_called

    def test_dispose_ignores_services_without_cleanup(self) -> None:
        """dispose() корректно обрабатывает сервисы без cleanup/close методов."""
        container = DIContainer()
        service = ServiceWithoutCleanup()
        container.register(ServiceWithoutCleanup, service, Scope.SINGLETON)

        # dispose() не должен выбросить исключение
        container.dispose()

        # Сервис остается неизменным
        assert service.value == "test"

    def test_dispose_clears_all_singletons(self) -> None:
        """dispose() очищает все синглтоны после очистки."""
        container = DIContainer()
        # Регистрируем классы (не экземпляры) чтобы они создавались при resolve
        container.register(ServiceWithCleanup, ServiceWithCleanup, Scope.SINGLETON)
        container.register(ServiceWithClose, ServiceWithClose, Scope.SINGLETON)

        # Получаем первые экземпляры синглтонов
        service1 = container.resolve(ServiceWithCleanup)
        service2 = container.resolve(ServiceWithClose)

        # Убеждаемся что это синглтоны (повторный resolve возвращает те же объекты)
        assert container.resolve(ServiceWithCleanup) is service1
        assert container.resolve(ServiceWithClose) is service2

        # Вызываем dispose
        container.dispose()

        # После dispose все синглтоны должны быть удалены
        # Новый resolve должен создать новый экземпляр
        new_service1 = container.resolve(ServiceWithCleanup)
        new_service2 = container.resolve(ServiceWithClose)

        # Это должны быть разные объекты
        assert new_service1 is not service1
        assert new_service2 is not service2

    def test_dispose_handles_cleanup_errors(self) -> None:
        """dispose() обрабатывает ошибки при вызове cleanup() методов."""

        class ServiceWithBrokenCleanup:
            def cleanup(self) -> None:
                raise RuntimeError("Cleanup failed!")

        container = DIContainer()
        service = ServiceWithBrokenCleanup()
        container.register(ServiceWithBrokenCleanup, service, Scope.SINGLETON)

        # dispose() не должен выбросить исключение даже если cleanup() падает
        try:
            container.dispose()
        except Exception:
            pytest.fail("dispose() should not propagate cleanup exceptions")

    def test_dispose_with_multiple_services(self) -> None:
        """dispose() обрабатывает несколько сервисов корректно."""
        container = DIContainer()

        # Регистрируем классы чтобы они создавались при resolve
        container.register(ServiceWithCleanup, ServiceWithCleanup, Scope.SINGLETON)
        container.register(ServiceWithClose, ServiceWithClose, Scope.SINGLETON)
        container.register(ServiceWithoutCleanup, ServiceWithoutCleanup, Scope.SINGLETON)

        # Получаем первые экземпляры
        service1 = container.resolve(ServiceWithCleanup)
        service2 = container.resolve(ServiceWithClose)
        service3 = container.resolve(ServiceWithoutCleanup)

        # Все сервисы должны быть зарегистрированы как синглтоны
        assert container.resolve(ServiceWithCleanup) is service1
        assert container.resolve(ServiceWithClose) is service2
        assert container.resolve(ServiceWithoutCleanup) is service3

        # Вызываем dispose
        container.dispose()

        # Проверяем что cleanup методы были вызваны
        assert service1.cleanup_called
        assert service2.close_called

        # После dispose все синглтоны удалены
        new_service1 = container.resolve(ServiceWithCleanup)
        new_service2 = container.resolve(ServiceWithClose)
        new_service3 = container.resolve(ServiceWithoutCleanup)

        assert new_service1 is not service1
        assert new_service2 is not service2
        assert new_service3 is not service3

    def test_dispose_is_idempotent(self) -> None:
        """dispose() можно вызвать несколько раз безопасно."""
        container = DIContainer()
        # Регистрируем класс
        container.register(ServiceWithCleanup, ServiceWithCleanup, Scope.SINGLETON)

        # Получаем сервис
        service = container.resolve(ServiceWithCleanup)

        # Вызываем dispose несколько раз
        container.dispose()
        container.dispose()  # Не должно быть ошибки

        # Сервис должен быть в таком же состоянии
        assert service.cleanup_called

    def test_dispose_does_not_affect_registrations(self) -> None:
        """dispose() очищает синглтоны но оставляет регистрации."""
        container = DIContainer()
        # Регистрируем класс (не экземпляр)
        container.register(ServiceWithCleanup, ServiceWithCleanup, Scope.SINGLETON)

        # Получаем первый экземпляр
        service = container.resolve(ServiceWithCleanup)

        # Вызываем dispose
        container.dispose()

        # Регистрация должна остаться - мы все еще можем разрешить тип
        new_service = container.resolve(ServiceWithCleanup)
        assert isinstance(new_service, ServiceWithCleanup)
        assert new_service is not service  # Но это новый экземпляр
