# Анализ DI и инициализации в acp-client

## Статус: ❌ Найдены проблемы

Дата анализа: 2026-04-08

---

## 🔴 Критические проблемы

### 1. **DIContainer.Registration.create() - логическая ошибка в определении типа**

**Файл:** [`acp-client/src/acp_client/infrastructure/di_container.py:159-176`](acp-client/src/acp_client/infrastructure/di_container.py:159)

**Проблема:**
```python
def create(self) -> T:
    # Если это уже готовый экземпляр, возвращаем его
    if not isinstance(self.implementation, type) and not callable(self.implementation):
        return cast(T, self.implementation)
    
    # Если это класс, создаем экземпляр
    if isinstance(self.implementation, type):
        return cast(T, self.implementation())
    
    # Если это callable (factory), вызываем её
    return cast(T, self.implementation())  # type: ignore[misc]
```

**Почему это неправильно:**
1. Первая проверка `not isinstance(self.implementation, type) and not callable(self.implementation)` неправильна
   - Классы (`type`) всегда callable, поэтому условие может быть непредсказуемым
   - Если registrieren готовый экземпляр который имеет `__call__`, он не будет распознан как готовый экземпляр
   - Проверка `not callable(self.implementation)` слишком частая - большинство объектов в Python не callable

2. Логика должна быть:
   - Если `isinstance(type)` → создать
   - Иначе если `callable` → вызвать как factory
   - Иначе → вернуть готовый экземпляр

**Риск:** Неправильное создание объектов, особенно при регистрации готовых экземпляров с методом `__call__`.

---

### 2. **ViewModelFactory - готовые экземпляры регистрируются как singletons без управления жизненным циклом**

**Файл:** [`acp-client/src/acp_client/presentation/view_model_factory.py:64-106`](acp-client/src/acp_client/presentation/view_model_factory.py:64)

**Проблема:**
```python
# Регистрируем готовый экземпляр
ui_vm = UIViewModel(event_bus=event_bus, logger=logger)
container.register(UIViewModel, ui_vm, Scope.SINGLETON)
```

**Почему это проблема:**
1. UIViewModel создается внутри factory, но никто не отвечает за его очистку (cleanup)
2. Если UIViewModel содержит ресурсы (файлы, соединения, subscriptions), они не будут очищены
3. DIContainer не знает о жизненном цикле ViewModels и не может их правильно завершить

**Рекомендация:**
- Либо регистрировать классы с Scope.SINGLETON, чтобы DIContainer управлял созданием
- Либо добавить механизм очистки в DIContainer при `dispose()`

---

### 3. **ACPClientApp.__init__() - зависимости создаются вручную, не через DIContainer**

**Файл:** [`acp-client/src/acp_client/tui/app.py:171-229`](acp-client/src/acp_client/tui/app.py:171)

**Проблема:**
```python
def __init__(self, *, host: str, port: int) -> None:
    # ... много инициализации ...
    
    # Зависимости создаются вручную
    self._event_bus = EventBus()
    transport_service = ACPTransportService(host=host, port=port)
    session_repository = InMemorySessionRepository()
    self._session_coordinator = SessionCoordinator(
        transport=transport_service,
        session_repo=session_repository,
    )
    
    # DIContainer инициализируется только для ViewModels
    self._container = DIContainer()
    ViewModelFactory.register_view_models(
        self._container,
        session_coordinator=self._session_coordinator,
        event_bus=self._event_bus,
        logger=self._app_logger,
    )
```

**Почему это проблема:**
1. ❌ DIContainer не используется для других сервисов (EventBus, TransportService, SessionRepository, SessionCoordinator)
2. ❌ Нет единой точки конфигурации зависимостей
3. ❌ Сложно тестировать - нельзя легко подменить зависимости
4. ❌ Нарушает принцип DI - большинство зависимостей создаются вручную, не инжектируются
5. ❌ SessionCoordinator не зарегистрирован в контейнере, но его уже нельзя разрешить из контейнера

**Текущая архитектура:**
```
ACPClientApp.__init__()
├── EventBus (создан вручную)
├── ACPTransportService (создан вручную)
├── InMemorySessionRepository (создан вручную)
├── SessionCoordinator (создан вручную с выше зависимостями)
└── DIContainer (только для ViewModels)
    ├── UIViewModel → event_bus, logger
    ├── SessionViewModel → coordinator, event_bus, logger
    └── ChatViewModel → coordinator, event_bus, logger
```

**Результат:** Смешанное управление - часть зависимостей в DIContainer, часть создаются вручную.

---

### 4. **ViewModels не имеют проверки на успешное разрешение из контейнера**

**Файл:** [`acp-client/src/acp_client/tui/app.py:227-229`](acp-client/src/acp_client/tui/app.py:227)

**Проблема:**
```python
# Извлекаем все ViewModels без проверок
self._ui_vm = self._container.resolve(UIViewModel)      # Может быть None если не зарегистрирован
self._session_vm = self._container.resolve(SessionViewModel)  # Может быть None
self._chat_vm = self._container.resolve(ChatViewModel)  # Может быть None
```

**Почему это проблема:**
1. `DIContainer.resolve()` вызывает исключение DIError если сервис не найден, но нет try-catch
2. Если ViewModelFactory.register_view_models() проигнорировал session_coordinator, SessionViewModel не будет зарегистрирован
3. Ошибка при разрешении ViewModels приведет к краху __init__(), и это сложно отладить

**Рекомендация:**
```python
try:
    self._ui_vm = self._container.resolve(UIViewModel)
    self._session_vm = self._container.resolve(SessionViewModel)
    self._chat_vm = self._container.resolve(ChatViewModel)
except DIError as e:
    self._app_logger.error("failed_to_resolve_viewmodels", error=str(e))
    raise
```

---

## 🟡 Серьезные проблемы

### 5. **ViewModelFactory.register_view_models() - молчаливые пропуски**

**Файл:** [`acp-client/src/acp_client/presentation/view_model_factory.py:71-86`](acp-client/src/acp_client/presentation/view_model_factory.py:71)

**Проблема:**
```python
if session_coordinator is not None:
    session_vm = SessionViewModel(...)
    container.register(SessionViewModel, session_vm, Scope.SINGLETON)
else:
    logger.warning(
        "session_coordinator not provided, skipping SessionViewModel registration"
    )
```

**Почему это проблема:**
1. Если session_coordinator не передан, SessionViewModel просто не регистрируется
2. Позже код попытается разрешить SessionViewModel из контейнера и получит DIError
3. Это скрытая зависимость - не очевидно при вызове, что SessionViewModel требует coordinator

**Результат:** В ACPClientApp SessionViewModel и ChatViewModel могут не быть зарегистрированы, и код упадет при попытке разрешить их.

---

### 6. **ContainerBuilder используется, но не применен везде**

**Файл:** [`acp-client/src/acp_client/infrastructure/di_container.py:185-264`](acp-client/src/acp_client/infrastructure/di_container.py:185)

**Проблема:**
```python
class ContainerBuilder:
    # Builder паттерн с fluent API
    # Но он не используется в приложении!
```

**Почему это проблема:**
1. ContainerBuilder паттерн создан, но нигде не применяется
2. DIContainer инициализируется вручную в ACPClientApp без использования builder
3. Нет central bootstrap точки для всего контейнера

**Пример неиспользования:**
```python
# Есть builder, но не используется
self._container = DIContainer()
ViewModelFactory.register_view_models(...)
```

**Вместо:**
```python
# Мог бы быть используемый builder
self._container = (
    ContainerBuilder()
    .register_singleton(EventBus)
    .register_singleton(ACPTransportService)
    .register_singleton(InMemorySessionRepository)
    .register_singleton(SessionCoordinator)
    # ... + ViewModels
    .build()
)
```

---

### 7. **EventBus передается опционально везде - скрытая зависимость**

**Файлы:**
- [`acp-client/src/acp_client/presentation/view_model_factory.py:39`](acp-client/src/acp_client/presentation/view_model_factory.py:39)
- [`acp-client/src/acp_client/presentation/ui_view_model.py:52`](acp-client/src/acp_client/presentation/ui_view_model.py:52)
- [`acp-client/src/acp_client/presentation/base_view_model.py:42`](acp-client/src/acp_client/presentation/base_view_model.py:42)

**Проблема:**
```python
# ViewModelFactory
def register_view_models(
    container: DIContainer,
    session_coordinator: Any | None = None,
    event_bus: Any | None = None,  # Опционально!
    logger: Any | None = None,
) -> None:
```

**Почему это проблема:**
1. EventBus может быть None, но это не очевидно из сигнатуры
2. ViewModels работают иначе с event_bus и без него (см. BaseViewModel.on_event())
3. Нет гарантии что EventBus инициализирован при необходимости
4. Код молчит при отсутствии EventBus:
   ```python
   def on_event(self, event_type, handler) -> None:
       if not self.event_bus:
           self.logger.warning("EventBus not available, event subscription ignored")
           return  # Молча возвращает!
   ```

**Результат:** Если EventBus не передан, подписки на события просто не будут работать, и это не будет отмечено как ошибка.

---

### 8. **BaseViewModel.on_event() - молчаливое игнорирование отсутствия EventBus**

**Файл:** [`acp-client/src/acp_client/presentation/base_view_model.py:55-80`](acp-client/src/acp_client/presentation/base_view_model.py:55)

**Проблема:**
```python
def on_event(self, event_type: type[DomainEvent], handler: Callable) -> None:
    if not self.event_bus:
        self.logger.warning("EventBus not available, event subscription ignored")
        return  # Молча возвращает!

    try:
        self.event_bus.subscribe(event_type, handler)
```

**Почему это проблема:**
1. Если EventBus None, метод молча не регистрирует обработчик
2. Код не знает, что подписка не работает
3. Сложно отладить - событие не будет обработано, но никаких ошибок

**Рекомендация:**
```python
def on_event(self, event_type, handler) -> None:
    if not self.event_bus:
        raise RuntimeError(
            f"Cannot subscribe to events: EventBus not initialized. "
            f"Make sure EventBus is passed to {self.__class__.__name__}"
        )
    # ... регистрация ...
```

---

### 9. **ACPTransportService имеет TODOs вместо реальной реализации**

**Файл:** [`acp-client/src/acp_client/infrastructure/services/acp_transport_service.py:62-64`](acp-client/src/acp_client/infrastructure/services/acp_transport_service.py:62)

**Проблема:**
```python
async def connect(self) -> None:
    # ... проверки ...
    # TODO: Создать сессию с адресом сервера
    # Пока это заглушка для того, чтобы не ломать существующий код
    self._logger.info("connected_to_server", host=self.host, port=self.port)
```

**Почему это проблема:**
1. connect() не реально подключается, это только логирование
2. SessionCoordinator использует ACPTransportService, думая что он работает
3. При runtime будут ошибки отправки сообщений

---

## 🟢 Хорошие практики

### ✅ DIContainer имеет поддержку разных Scope

- SINGLETON - правильно для stateless сервисов
- TRANSIENT - правильно для factory объектов
- SCOPED - зарезервировано для будущих расширений

### ✅ ViewModels правильно наследуют BaseViewModel

- Все ViewModels используют один базовый класс
- Единая точка для управления lifecycle

### ✅ ViewModelFactory централизирует регистрацию ViewModels

- Все ViewModels регистрируются в одном месте
- Легко видеть какие ViewModels доступны

---

## 📋 Рекомендации

### Приоритет 1 (Критичные)

1. **Исправить DIContainer.Registration.create()** логику
   - Правильно определить тип объекта
   - Тесты в test_infrastructure_di_container.py

2. **Добавить проверку при разрешении ViewModels в ACPClientApp**
   - try-catch при resolve
   - Понятное сообщение об ошибке

3. **Сделать EventBus обязательным параметром**
   - Не может быть None
   - Или выкинуть исключение если None

### Приоритет 2 (Важные)

4. **Переместить всю инициализацию зависимостей в DIContainer**
   ```python
   # Вместо ручного создания, использовать контейнер везде
   self._container = ContainerBuilder()
       .register_singleton(EventBus)
       .register_singleton(ACPTransportService, ...)
       .register_singleton(SessionRepository)
       .register_singleton(SessionCoordinator, ...)
       # ... и ViewModels через factory
       .build()
   ```

5. **Добавить bootstrap метод для инициализации контейнера**
   ```python
   class DIBootstrapper:
       @staticmethod
       def build_container(host, port) -> DIContainer:
           # Централизованная конфигурация
   ```

6. **Исправить BaseViewModel.on_event() на выброс исключения**
   - Будет видно во время разработки что что-то неправильно

### Приоритет 3 (Улучшения)

7. **Использовать ContainerBuilder везде**
   - Убрать ручное создание DIContainer()
   - Использовать fluent API

8. **Добавить DIContainer.dispose()** для очистки ресурсов
   - Особенно для singleton объектов

9. **Документировать зависимости ViewModels**
   - В docstrings указать какие зависимости требуются

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| Критичные проблемы | 4 |
| Серьезные проблемы | 5 |
| Файлов с проблемами | 5 |
| Неиспользуемый код | ContainerBuilder (3 метода) |
| Молчаливые ошибки | 3 (EventBus, DIError, Registration) |

---

## 🔗 Связанные файлы

### DI контейнер и инициализация:
- [`acp-client/src/acp_client/infrastructure/di_container.py`](acp-client/src/acp_client/infrastructure/di_container.py)
- [`acp-client/src/acp_client/presentation/view_model_factory.py`](acp-client/src/acp_client/presentation/view_model_factory.py)
- [`acp-client/src/acp_client/tui/app.py`](acp-client/src/acp_client/tui/app.py)

### Presentation слой:
- [`acp-client/src/acp_client/presentation/base_view_model.py`](acp-client/src/acp_client/presentation/base_view_model.py)
- [`acp-client/src/acp_client/presentation/ui_view_model.py`](acp-client/src/acp_client/presentation/ui_view_model.py)
- [`acp-client/src/acp_client/presentation/session_view_model.py`](acp-client/src/acp_client/presentation/session_view_model.py)
- [`acp-client/src/acp_client/presentation/chat_view_model.py`](acp-client/src/acp_client/presentation/chat_view_model.py)

### Infrastructure:
- [`acp-client/src/acp_client/infrastructure/services/acp_transport_service.py`](acp-client/src/acp_client/infrastructure/services/acp_transport_service.py)
- [`acp-client/src/acp_client/infrastructure/repositories.py`](acp-client/src/acp_client/infrastructure/repositories.py)
- [`acp-client/src/acp_client/infrastructure/events/bus.py`](acp-client/src/acp_client/infrastructure/events/bus.py)
- [`acp-client/src/acp_client/application/session_coordinator.py`](acp-client/src/acp_client/application/session_coordinator.py)

### Тесты:
- [`acp-client/tests/test_infrastructure_di_container.py`](acp-client/tests/test_infrastructure_di_container.py)
- [`acp-client/tests/test_di_container_integration.py`](acp-client/tests/test_di_container_integration.py)

---

**Готово к рефакторингу!**
