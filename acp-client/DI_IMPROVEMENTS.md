# DI-контейнер: Улучшения и рекомендации

Документ описывает улучшения в системе Dependency Injection (DI) и рекомендации для использования.

## 📋 Содержание

1. [Выполненные исправления](#выполненные-исправления)
2. [Новые компоненты](#новые-компоненты)
3. [Использование DIBootstrapper](#использование-dibootstrapper)
4. [Рекомендации](#рекомендации)
5. [Примеры кода](#примеры-кода)

---

## ✅ Выполненные исправления

### 1. DIContainer.Registration.create() - исправлена логика определения типов

**Что было:** Условия проверки были в неправильном порядке, что могло привести к неправильному созданию объектов.

**Как исправлено:**
```python
# Правильный порядок:
1. isinstance(self.implementation, type) → создать экземпляр класса
2. callable(self.implementation) → вызвать factory функцию
3. иначе → вернуть готовый экземпляр
```

**Файл:** [`src/acp_client/infrastructure/di_container.py`](src/acp_client/infrastructure/di_container.py)

---

### 2. BaseViewModel.on_event() - выброс исключения вместо молчания

**Что было:** Если EventBus был None, метод молча игнорировал попытку подписки на события.

**Как исправлено:**
```python
if not self.event_bus:
    raise RuntimeError(
        f"Cannot subscribe to events in {self.__class__.__name__}: "
        "EventBus is not initialized..."
    )
```

**Файл:** [`src/acp_client/presentation/base_view_model.py`](src/acp_client/presentation/base_view_model.py)

**Преимущества:**
- Ошибка видна сразу во время разработки
- Понятное сообщение об ошибке
- Упрощает отладку

---

### 3. ViewModelFactory - session_coordinator обязателен

**Что было:** `session_coordinator` был опциональным параметром, но на практике требуется для SessionViewModel и ChatViewModel.

**Как исправлено:**
```python
# До
def register_view_models(
    container: DIContainer,
    session_coordinator: Any | None = None,  # опционально
    ...
) -> None:

# После
def register_view_models(
    container: DIContainer,
    session_coordinator: Any,  # ОБЯЗАТЕЛЬНО
    ...
) -> None:
    if session_coordinator is None:
        raise TypeError("session_coordinator is required...")
```

**Файл:** [`src/acp_client/presentation/view_model_factory.py`](src/acp_client/presentation/view_model_factory.py)

---

### 4. ACPClientApp.__init__() - добавлены проверки ошибок

**Что было:** Отсутствовала обработка ошибок при инициализации DIContainer и разрешении ViewModels.

**Как исправлено:**
```python
# Регистрация с проверкой
try:
    ViewModelFactory.register_view_models(
        self._container,
        session_coordinator=self._session_coordinator,
        event_bus=self._event_bus,
        logger=self._app_logger,
    )
    self._app_logger.info("view_models_registered")
except (TypeError, RuntimeError) as e:
    self._app_logger.error("failed_to_register_view_models", error=str(e))
    raise

# Разрешение с проверкой
try:
    self._ui_vm = self._container.resolve(UIViewModel)
    self._session_vm = self._container.resolve(SessionViewModel)
    self._chat_vm = self._container.resolve(ChatViewModel)
except Exception as e:
    self._app_logger.error("failed_to_resolve_view_models", error=str(e))
    raise RuntimeError(f"Failed to initialize ViewModels: {e}...") from e
```

**Файл:** [`src/acp_client/tui/app.py`](src/acp_client/tui/app.py)

---

## 🆕 Новые компоненты

### DIBootstrapper - централизованная инициализация

**Назначение:** Упрощает инициализацию DIContainer с правильным порядком регистрации сервисов.

**Что делает:**
- Инициализирует EventBus
- Создает TransportService с заданным хостом и портом
- Регистрирует SessionRepository
- Инициализирует SessionCoordinator с нужными зависимостями
- Регистрирует все ViewModels

**Файл:** [`src/acp_client/infrastructure/di_bootstrapper.py`](src/acp_client/infrastructure/di_bootstrapper.py)

**Тесты:** [`tests/test_di_bootstrapper.py`](tests/test_di_bootstrapper.py)

---

## 🚀 Использование DIBootstrapper

### Базовое использование

```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

# Собрать контейнер
container = DIBootstrapper.build(host="localhost", port=8000)

# Получить сервисы из контейнера
from acp_client.infrastructure.events.bus import EventBus
event_bus = container.resolve(EventBus)

from acp_client.presentation.ui_view_model import UIViewModel
ui_vm = container.resolve(UIViewModel)
```

### Использование в приложении

```python
class MyApp:
    def __init__(self, host: str, port: int):
        # Собираем весь контейнер одной строкой
        self._container = DIBootstrapper.build(host=host, port=port)
        
        # Получаем все нужные сервисы
        self._event_bus = self._container.resolve(EventBus)
        self._coordinator = self._container.resolve(SessionCoordinator)
        self._ui_vm = self._container.resolve(UIViewModel)
        
        # Вместо ручного создания:
        # self._event_bus = EventBus()
        # transport_service = ACPTransportService(host, port)
        # session_repo = InMemorySessionRepository()
        # self._coordinator = SessionCoordinator(transport, repo)
        # ... и т.д.
```

### С кастомным логгером

```python
import structlog

logger = structlog.get_logger("my_app")
container = DIBootstrapper.build(
    host="localhost",
    port=8000,
    logger=logger,
)
```

---

## 📝 Рекомендации

### ✅ Что делать

1. **Использовать DIBootstrapper** для инициализации контейнера вместо ручного создания сервисов
2. **Передавать EventBus везде**, где нужна подписка на события
3. **Проверять ошибки** при регистрации и разрешении сервисов
4. **Логировать** процесс инициализации для отладки

### ❌ Чего избегать

1. **Не создавать зависимости вне DIContainer** - это усложняет тестирование
2. **Не игнорировать ошибки EventBus** - теперь они выбрасываются явно
3. **Не забывать передавать session_coordinator** при регистрации ViewModels

---

## 💡 Примеры кода

### Пример 1: Инициализация в тестах

```python
import pytest
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

@pytest.fixture
def di_container():
    """Fixture для DIContainer в тестах."""
    return DIBootstrapper.build(host="localhost", port=8000)

def test_view_model_initialization(di_container):
    """Тест инициализации ViewModel."""
    from acp_client.presentation.ui_view_model import UIViewModel
    
    ui_vm = di_container.resolve(UIViewModel)
    assert ui_vm is not None
```

### Пример 2: Работа с EventBus

```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.presentation.ui_view_model import UIViewModel

container = DIBootstrapper.build(host="localhost", port=8000)

# UIViewModel автоматически получит EventBus
ui_vm = container.resolve(UIViewModel)

# Теперь можно подписываться на события
from acp_client.domain.events import SessionCreatedEvent

def on_session_created(event: SessionCreatedEvent):
    print(f"Session created: {event.session_id}")

# Это будет работать, потому что EventBus инициализирован
ui_vm.on_event(SessionCreatedEvent, on_session_created)
```

### Пример 3: Обработка ошибок при инициализации

```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
import structlog

logger = structlog.get_logger(__name__)

try:
    container = DIBootstrapper.build(
        host="localhost",
        port=8000,
        logger=logger,
    )
    logger.info("di_container_ready")
except RuntimeError as e:
    logger.error("failed_to_initialize_di", error=str(e))
    raise
```

---

## 📊 Статистика улучшений

| Проблема | Статус | Тесты |
|----------|--------|-------|
| DIContainer.create() логика | ✅ Исправлена | 12 тестов |
| BaseViewModel молчание | ✅ Исправлено | Включено |
| ViewModelFactory параметры | ✅ Исправлено | 17 тестов |
| ACPClientApp проверки | ✅ Добавлены | Включено |
| DIBootstrapper | ✅ Добавлен | 12 тестов |
| **ВСЕГО** | **✅ 41 тест** | **ПРОЙДЕНЫ** |

---

## 🔗 Связанные документы

- [`DI_ANALYSIS_REPORT.md`](DI_ANALYSIS_REPORT.md) - полный анализ проблем и решений
- [`src/acp_client/infrastructure/di_container.py`](src/acp_client/infrastructure/di_container.py) - DIContainer
- [`src/acp_client/infrastructure/di_bootstrapper.py`](src/acp_client/infrastructure/di_bootstrapper.py) - DIBootstrapper
- [`tests/test_di_bootstrapper.py`](tests/test_di_bootstrapper.py) - тесты DIBootstrapper

---

**Документ актуален на:** 2026-04-08
