# Фаза 3: Event-Driven Architecture и Plugin System 📡

**Статус:** Планирование  
**Дата начала:** 8 апреля 2026  
**Ожидаемый результат:** Event-driven система с поддержкой плагинов

---

## 📋 Общий обзор Phase 3

### Цели
1. Реализовать **Event-Driven архитектуру** для слабой связанности компонентов
2. Создать **Plugin System** для расширяемости функционала
3. Рефакторить **TUI** на основе ViewModel паттерна
4. Обеспечить **100% backwards compatibility** с Phase 2

### Почему это нужно?

**Event-Driven Architecture:**
- ✅ Слабая связанность между компонентами
- ✅ Легче добавлять новые обработчики без изменения кода
- ✅ Асинхронная обработка событий
- ✅ Историю событий можно логировать и воспроизводить

**Plugin System:**
- ✅ Расширяемость без изменения ядра
- ✅ Third-party плагины для новых handlers
- ✅ Динамическая загрузка функционала
- ✅ Изоляция функционала в отдельных модулях

**TUI Refactoring:**
- ✅ Отделение UI логики от бизнес-логики
- ✅ Более легкое тестирование
- ✅ Переиспользуемые ViewModels
- ✅ Reaktive UI updates

---

## 🏗️ Архитектурная диаграмма Phase 3

```
┌─────────────────────────────────────────────────────────┐
│           Presentation Layer (TUI/CLI)                   │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  ViewModels (SessionVM, ChatVM, UIVM)               │ │
│  │  ├─ Слушают события через EventBus                  │ │
│  │  ├─ Управляют UI state                              │ │
│  │  └─ Обновляют компоненты через callbacks            │ │
│  └─────────────────────────────────────────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────v────────────────────────────────────┐
│         Application Layer (Use Cases)                    │
│  ├─ Use Cases (CreateSession, SendPrompt, etc.)         │
│  ├─ SessionCoordinator (orchestration)                  │
│  └─ EventPublisher (publishes domain events)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │   Event Bus    │  ◄─── Новый компонент!
            │   (Publish/    │
            │    Subscribe)  │
            └────────────────┘
                     ▲
                     │
        ┌────────────┴─────────────┐
        │                          │
        ▼                          ▼
┌───────────────────┐    ┌──────────────────┐
│  Event Handlers   │    │  Plugin System   │  ◄─── Новая система!
│  ├─ UI Updates    │    │  ├─ PluginBase   │
│  ├─ Cache Updates │    │  ├─ PluginContext│
│  ├─ Logging       │    │  └─ PluginMgr   │
│  └─ Notifications │    └──────────────────┘
└───────────────────┘
        ▲
        │
┌───────v──────────────────────────────────────┐
│    Infrastructure Layer                      │
│  ├─ Repositories & Services (Phase 2)        │
│  ├─ Transport, Handlers, Parser              │
│  └─ DI Container (updated for events)        │
└───────────────────────────────────────────────┘
        ▲
        │
┌───────v──────────────────────────────────────┐
│    Domain Layer (Phase 2)                    │
│  ├─ Entities, Repositories, Services (ABC)   │
│  └─ DomainEvents (новое!)                    │
└───────────────────────────────────────────────┘
```

---

## 📦 Task 3.1: Event-Driven Architecture

### 3.1.1 DomainEvent Base Class

**Файл:** `acp-client/src/acp_client/domain/events.py`

```python
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class DomainEvent(ABC):
    """Базовый класс для всех доменных событий."""
    # Идентификатор агрегата, который генерировал событие
    aggregate_id: str
    # Когда произошло событие
    occurred_at: datetime
    
    def __hash__(self) -> int:
        return hash((self.aggregate_id, self.occurred_at))
```

### 3.1.2 Конкретные события

```python
# Session events
@dataclass(frozen=True)
class SessionCreatedEvent(DomainEvent):
    """Сессия была создана."""
    session_id: str
    server_host: str
    server_port: int

@dataclass(frozen=True)
class SessionInitializedEvent(DomainEvent):
    """Сессия была инициализирована."""
    session_id: str
    capabilities: dict[str, Any]

@dataclass(frozen=True)
class SessionClosedEvent(DomainEvent):
    """Сессия была закрыта."""
    session_id: str
    reason: str

# Prompt events
@dataclass(frozen=True)
class PromptStartedEvent(DomainEvent):
    """Начался prompt turn."""
    session_id: str
    prompt_text: str

@dataclass(frozen=True)
class PromptCompletedEvent(DomainEvent):
    """Prompt turn завершился."""
    session_id: str
    stop_reason: str

# Permission events
@dataclass(frozen=True)
class PermissionRequestedEvent(DomainEvent):
    """Запрошено разрешение на действие."""
    session_id: str
    action: str
    resource: str

@dataclass(frozen=True)
class PermissionGrantedEvent(DomainEvent):
    """Разрешение было дано."""
    session_id: str
    action: str

# Error events
@dataclass(frozen=True)
class ErrorOccurredEvent(DomainEvent):
    """Произошла ошибка."""
    error_message: str
    error_type: str
```

### 3.1.3 EventBus

**Файл:** `acp-client/src/acp_client/infrastructure/events/bus.py`

```python
from typing import Callable, Type, TypeVar
from asyncio import gather
import structlog

T = TypeVar('T', bound=DomainEvent)

class EventBus:
    """Publish-Subscribe шина для доменных событий."""
    
    def __init__(self) -> None:
        self._subscribers: dict[Type[DomainEvent], list[Callable]] = {}
        self._logger = structlog.get_logger()
    
    def subscribe(
        self, 
        event_type: Type[T], 
        handler: Callable[[T], None | Awaitable[None]]
    ) -> None:
        """Подписаться на события определённого типа.
        
        Args:
            event_type: Тип события (класс)
            handler: Функция-обработчик (может быть async)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        
    def unsubscribe(
        self, 
        event_type: Type[T], 
        handler: Callable
    ) -> None:
        """Отписаться от событий."""
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)
    
    async def publish(self, event: T) -> None:
        """Опубликовать событие всем подписчикам.
        
        Args:
            event: Событие для публикации
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        
        self._logger.info(
            'event_published',
            event_type=event_type.__name__,
            aggregate_id=event.aggregate_id,
            num_handlers=len(handlers)
        )
        
        # Выполнить все обработчики параллельно
        tasks = []
        for handler in handlers:
            result = handler(event)
            if hasattr(result, '__await__'):
                tasks.append(result)
        
        if tasks:
            await gather(*tasks)
```

### 3.1.4 Event Handlers

**Файл:** `acp-client/src/acp_client/infrastructure/events/handlers.py`

```python
# Примеры обработчиков событий:

class UIUpdateEventHandler:
    """Обновляет UI при изменении состояния."""
    
    async def on_session_created(self, event: SessionCreatedEvent) -> None:
        # Обновить UI с новой сессией
        pass
    
    async def on_permission_requested(self, event: PermissionRequestedEvent) -> None:
        # Показать modal для запроса разрешения
        pass

class CacheEventHandler:
    """Обновляет кэш при событиях."""
    
    async def on_prompt_completed(self, event: PromptCompletedEvent) -> None:
        # Сохранить результат в кэш
        pass

class LoggingEventHandler:
    """Логирует все события."""
    
    async def on_any_event(self, event: DomainEvent) -> None:
        # Залогировать событие в файл/БД
        pass
```

---

## 🔌 Task 3.2: Plugin System

### 3.2.1 Plugin Base Classes

**Файл:** `acp-client/src/acp_client/infrastructure/plugins/base.py`

```python
from abc import ABC, abstractmethod
from typing import Any

class Plugin(ABC):
    """Базовый класс для всех плагинов."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя плагина."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Версия плагина (семантическое версионирование)."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание плагина."""
        pass
    
    @abstractmethod
    async def initialize(self, context: 'PluginContext') -> None:
        """Инициализировать плагин.
        
        Args:
            context: Контекст с доступом к приложению
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Корректно завершить работу плагина."""
        pass

class HandlerPlugin(Plugin):
    """Плагин, который добавляет handlers (permission, filesystem, terminal)."""
    
    @abstractmethod
    def get_handlers(self) -> dict[str, 'Handler']:
        """Вернуть словарь обработчиков.
        
        Returns:
            {'permission': PermissionHandler, 'filesystem': FSHandler}
        """
        pass

class EventPlugin(Plugin):
    """Плагин, который добавляет обработчики событий."""
    
    @abstractmethod
    def get_event_handlers(self) -> dict[type[DomainEvent], Callable]:
        """Вернуть обработчики событий.
        
        Returns:
            {SessionCreatedEvent: handler_func, ...}
        """
        pass
```

### 3.2.2 Plugin Context

**Файл:** `acp-client/src/acp_client/infrastructure/plugins/context.py`

```python
from dataclasses import dataclass

@dataclass
class PluginContext:
    """Контекст выполнения плагина."""
    
    # Доступ к DI контейнеру
    di_container: 'DIContainer'
    
    # Доступ к EventBus для публикации событий
    event_bus: 'EventBus'
    
    # Доступ к HandlerRegistry для регистрации handlers
    handler_registry: 'HandlerRegistry'
    
    # Логгер для плагина
    logger: Any
```

### 3.2.3 Plugin Manager

**Файл:** `acp-client/src/acp_client/infrastructure/plugins/manager.py`

```python
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

class PluginManager:
    """Управляет загрузкой и выполнением плагинов."""
    
    def __init__(self, context: PluginContext) -> None:
        self._context = context
        self._plugins: dict[str, Plugin] = {}
        self._logger = structlog.get_logger()
    
    def load_plugin(self, plugin_path: Path) -> Plugin:
        """Динамически загрузить плагин из файла.
        
        Args:
            plugin_path: Путь к файлу плагина (plugin.py)
            
        Returns:
            Загруженный и инициализированный плагин
        """
        spec = spec_from_file_location("plugin_module", plugin_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Найти класс, наследующий Plugin
        plugin_class = None
        for item in vars(module).values():
            if isinstance(item, type) and issubclass(item, Plugin) and item != Plugin:
                plugin_class = item
                break
        
        if not plugin_class:
            raise ValueError(f"No Plugin class found in {plugin_path}")
        
        plugin = plugin_class()
        self._plugins[plugin.name] = plugin
        return plugin
    
    async def initialize_all(self) -> None:
        """Инициализировать все загруженные плагины."""
        for plugin in self._plugins.values():
            await plugin.initialize(self._context)
            self._logger.info('plugin_initialized', plugin_name=plugin.name)
    
    async def shutdown_all(self) -> None:
        """Корректно завершить все плагины."""
        for plugin in self._plugins.values():
            await plugin.shutdown()
            self._logger.info('plugin_shutdown', plugin_name=plugin.name)
    
    def list_plugins(self) -> list[tuple[str, str]]:
        """Вернуть список (name, version) всех плагинов."""
        return [(p.name, p.version) for p in self._plugins.values()]
```

---

## 🎨 Task 3.3: TUI Refactoring with ViewModels

### 3.3.1 ViewModel Base Class

**Файл:** `acp-client/src/acp_client/presentation/tui/viewmodels/base.py`

```python
from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar

T = TypeVar('T')

class ViewModel(ABC, Generic[T]):
    """Базовый ViewModel для TUI компонентов."""
    
    def __init__(self) -> None:
        self._state: T | None = None
        self._observers: list[Callable[[T], None]] = []
    
    def add_observer(self, callback: Callable[[T], None]) -> None:
        """Подписаться на изменения состояния."""
        self._observers.append(callback)
    
    def remove_observer(self, callback: Callable[[T], None]) -> None:
        """Отписаться от изменений состояния."""
        self._observers.remove(callback)
    
    def notify_observers(self, state: T) -> None:
        """Уведомить всех observers об изменении состояния."""
        for observer in self._observers:
            observer(state)
    
    @property
    def state(self) -> T | None:
        return self._state
```

### 3.3.2 SessionViewModel

```python
from dataclasses import dataclass

@dataclass
class SessionState:
    session_id: str | None = None
    is_connected: bool = False
    capabilities: dict[str, Any] | None = None
    error: str | None = None

class SessionViewModel(ViewModel[SessionState]):
    """ViewModel для управления текущей сессией."""
    
    def __init__(self, session_coordinator: SessionCoordinator) -> None:
        super().__init__()
        self._coordinator = session_coordinator
        self._state = SessionState()
        
        # Подписаться на события
        self._coordinator.event_bus.subscribe(
            SessionCreatedEvent,
            self._on_session_created
        )
    
    async def create_session(self, cwd: str) -> None:
        """Создать новую сессию."""
        try:
            session_id = await self._coordinator.create_session(cwd)
            self._state.session_id = session_id
            self._state.is_connected = True
            self.notify_observers(self._state)
        except Exception as e:
            self._state.error = str(e)
            self.notify_observers(self._state)
    
    async def _on_session_created(self, event: SessionCreatedEvent) -> None:
        """Обработчик события создания сессии."""
        self._state.session_id = event.session_id
        self._state.is_connected = True
        self.notify_observers(self._state)
```

### 3.3.3 ChatViewModel

```python
@dataclass
class ChatState:
    messages: list[Message] = field(default_factory=list)
    is_loading: bool = False
    error: str | None = None

class ChatViewModel(ViewModel[ChatState]):
    """ViewModel для управления чатом."""
    
    def __init__(self, session_coordinator: SessionCoordinator) -> None:
        super().__init__()
        self._coordinator = session_coordinator
        self._state = ChatState()
        
        # Подписаться на события
        self._coordinator.event_bus.subscribe(
            PromptCompletedEvent,
            self._on_prompt_completed
        )
    
    async def send_prompt(self, text: str, session_id: str) -> None:
        """Отправить prompt."""
        try:
            self._state.is_loading = True
            self.notify_observers(self._state)
            
            result = await self._coordinator.send_prompt(session_id, text)
            # Результат будет получен через PromptCompletedEvent
        except Exception as e:
            self._state.error = str(e)
            self._state.is_loading = False
            self.notify_observers(self._state)
    
    async def _on_prompt_completed(self, event: PromptCompletedEvent) -> None:
        """Обработчик завершения prompt."""
        self._state.is_loading = False
        self.notify_observers(self._state)
```

### 3.3.4 UIViewModel

```python
@dataclass
class UIState:
    current_tab: str = "chat"
    show_permissions_modal: bool = False
    show_error_modal: bool = False
    error_message: str | None = None

class UIViewModel(ViewModel[UIState]):
    """ViewModel для глобального UI состояния."""
    
    def __init__(self, event_bus: EventBus) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._state = UIState()
        
        self._event_bus.subscribe(
            PermissionRequestedEvent,
            self._on_permission_requested
        )
        self._event_bus.subscribe(
            ErrorOccurredEvent,
            self._on_error_occurred
        )
    
    async def _on_permission_requested(
        self, 
        event: PermissionRequestedEvent
    ) -> None:
        """Показать modal для запроса разрешения."""
        self._state.show_permissions_modal = True
        self.notify_observers(self._state)
    
    async def _on_error_occurred(self, event: ErrorOccurredEvent) -> None:
        """Показать modal с ошибкой."""
        self._state.show_error_modal = True
        self._state.error_message = event.error_message
        self.notify_observers(self._state)
```

---

## 🔗 Integration with DIContainer

EventBus и PluginManager должны регистрироваться в DIContainer как SINGLETON:

```python
container_builder = (
    ContainerBuilder()
    .register_singleton(EventBus, lambda: EventBus())
    .register_singleton(
        PluginManager, 
        lambda di: PluginManager(
            PluginContext(
                di_container=di,
                event_bus=di.resolve(EventBus),
                handler_registry=di.resolve(HandlerRegistry),
                logger=structlog.get_logger()
            )
        )
    )
    .register_singleton(SessionViewModel, lambda di: SessionViewModel(
        di.resolve(SessionCoordinator)
    ))
    .build()
)
```

---

## 📊 Summary Table

| Task | Files | Tests | Status |
|------|-------|-------|--------|
| 3.1: Event-Driven | domain/events.py, infra/events/ | 15+ | 📋 Planning |
| 3.2: Plugin System | infra/plugins/ | 12+ | 📋 Planning |
| 3.3: TUI RefactorVM | presentation/tui/viewmodels/ | 10+ | 📋 Planning |
| **Total** | **15+ files** | **37+** | **📋 Planning** |

---

## ⏭️ Next Steps

1. ✅ **План создан** - Вы читаете это прямо сейчас!
2. 🔜 **Одобрение** - Нравится ли вам план? Хотите ли изменения?
3. 🚀 **Реализация** - Переход в Code режим для реализации
4. ✨ **Тестирование** - Интеграционное тестирование и документация

---

## ❓ Вопросы для обсуждения

1. **Асинхронная обработка событий** - Правильный ли подход с `gather()`?
2. **Plugin загрузка** - Нужна ли поддержка загрузки из zip-архивов?
3. **ViewModel паттерн** - Достаточно ли Observer паттерна или нужен Reactive (observables)?
4. **Backwards compatibility** - Нужно ли сохранять старые классы как фасады?
