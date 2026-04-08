# План рефакторинга acp-client

**Дата:** Апрель 2026  
**Цель:** Трансформация monolithic приложения в модульную, расширяемую архитектуру на базе SOLID принципов и Clean Architecture  
**Статус:** Planning Phase

---

## Резюме проблем

### Критические проблемы
- **ACPClient** (654 строки): множественная ответственность — сочетание транспорт-слоя и бизнес-логики
- **ACPClientApp** (962 строки): God Object — управление состоянием, UI, сессиями, разрешениями, терминалом
- Жесткая привязка к WebSocket транспорту — невозможно подменить
- Отсутствие Dependency Injection — все зависимости захардкодированы
- Handlers как функции вместо классов — нет общего интерфейса, дублирование логики
- Дублирование парсинга и валидации сообщений

### Затронутые области
- Нарушения SOLID (12 проблем)
- Дублирование кода (4 области)
- Слабая типизация (3 места)
- Плохое разделение ответственности (3 области)
- Жесткие связи (3 компонента)
- Отсутствие абстракций (3 типа)
- Проблемы расширяемости (3 области)
- Сложность тестирования (3 проблемы)

---

## 1. Целевая архитектура

### 1.1 Слои архитектуры

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│  (CLI, TUI Components, WebSocket Handlers)              │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────v───────────────────────────────────────┐
│                 Application Layer                        │
│  (Use Cases, Orchestration, State Management)           │
│  - SessionUseCase, PromptUseCase, PermissionUseCase    │
│  - StateOrchestrator, EventDispatcher                   │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────v───────────────────────────────────────┐
│                   Domain Layer                           │
│  (Business Logic, Entities, Value Objects)              │
│  - Session, Message, Permission, ToolCall               │
│  - SessionRepository, TransportService Interfaces       │
└─────────────────┬───────────────────────────────────────┘
                  │
┌─────────────────v───────────────────────────────────────┐
│               Infrastructure Layer                       │
│  (Implementations, External Services)                   │
│  - WebSocketTransport, ACPClientSession                 │
│  - InMemorySessionRepository, FileSystemService         │
│  - TerminalService, MessageParser                       │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Ключевые паттерны проектирования

| Паттерн | Применение | Цель |
|---------|-----------|------|
| **Repository Pattern** | SessionRepository, HistoryRepository | Абстрактный доступ к данным |
| **Dependency Injection** | DIContainer (Pydantic, dataclass-based) | Управление зависимостями, тестируемость |
| **Strategy Pattern** | TransportStrategy, HandlerStrategy | Подменяемые реализации транспорта |
| **Observer/Event-Driven** | EventDispatcher, message handlers | Слабая связь между компонентами |
| **Factory Pattern** | HandlerFactory, TransportFactory | Создание компонентов без привязки к конкретным классам |
| **Adapter Pattern** | TUIAdapter, CLIAdapter | Преобразование протокола ACP для разных UI |
| **Command Pattern** | ACPCommand, CommandBuilder | Инкапсуляция запросов как объектов |

### 1.3 Ответственность каждого слоя

**Domain Layer:**
- Определение сущностей (Session, Message, Permission)
- Бизнес-правила и валидация
- Интерфейсы репозиториев и сервисов
- Нет зависимостей от других слоев

**Application Layer:**
- Use Cases (SessionUseCase, PromptUseCase)
- Оркестрация между Domain и Infrastructure
- State Management (State Machines)
- Управление транзакциями

**Presentation Layer:**
- TUI компоненты (базирующиеся на Textual)
- CLI команды
- Форматирование вывода
- Обработка пользовательского ввода

**Infrastructure Layer:**
- WebSocket/TCP транспорт
- JSON парсинг и сериализация
- Файловая система (читать/писать)
- Терминальные операции
- Логирование

---

## 2. Фаза 1: Quick Wins (1-2 недели)

### Цель
Устранить критические проблемы, не меняя архитектуру. Подготовить базу для дальнейшего рефакторинга.

### 2.1 Задача 1: Ekstract Transport Abstraction

**Приоритет:** 🔴 CRITICAL  
**Затронутые файлы:**
- `transport/websocket.py` → переименовать в `transport/ws_session.py`
- Создать `transport/base.py` с интерфейсом
- `client.py` → обновить зависимость

**Что делать:**
1. Создать `TransportSession` ABC в `transport/base.py`
   ```python
   class TransportSession(ABC):
       async def connect(self) -> None: ...
       async def send(self, message: dict) -> None: ...
       async def receive(self) -> dict: ...
       async def close(self) -> None: ...
   ```
2. Сделать `ACPClientWSSession` наследником `TransportSession`
3. Обновить `ACPClient.__init__` чтобы принимать `TransportSession` вместо параметров host/port
4. Добавить Factory-функцию для создания WebSocket сессии

**Ожидаемый результат:**
- `ACPClient` больше не привязан к WebSocket
- Возможно создавать mock транспорты для тестирования
- Готово к TCP и gRPC вариантам в будущем

**Критерии приемки:**
- [ ] `TransportSession` интерфейс создан
- [ ] `ACPClient` принимает `TransportSession`
- [ ] Все существующие тесты проходят
- [ ] Написаны unit-тесты для mock транспорта

---

### 2.2 Задача 2: Extract Message Parser Service

**Приоритет:** 🟠 HIGH  
**Затронутые файлы:**
- Создать `parsers/base.py`
- Создать `parsers/acp_parser.py`
- `messages.py` → переместить парсеры в новый модуль
- `client.py` → обновить использование

**Что делать:**
1. Создать `MessageParser` ABC:
   ```python
   class MessageParser(ABC):
       def parse_authenticate_result(self, data: dict) -> AuthenticateResult: ...
       def parse_initialize_result(self, data: dict) -> InitializeResult: ...
       # ... остальные методы парсинга
   ```
2. Создать `ACPMessageParser` реализацию
3. Перенести всю логику из `helpers/` в парсеры
4. Удалить дублирование в `client.py`

**Ожидаемый результат:**
- Логика парсинга в одном месте
- Легко добавлять новые форматы сообщений
- Слабая связь между парсингом и логикой клиента

**Критерии приемки:**
- [ ] `MessageParser` интерфейс создан
- [ ] Все существующие парсеры мигрированы
- [ ] Дублирование устранено
- [ ] Тесты для парсеров написаны

---

### 2.3 Задача 3: Extract Handler Registry

**Приоритет:** 🟠 HIGH  
**Затронутые файлы:**
- Создать `handlers/base.py`
- Создать `handlers/registry.py`
- `handlers/` → рефактор существующих handlers
- `tui/managers/handlers.py` → обновить использование

**Что делать:**
1. Создать `Handler` Protocol:
   ```python
   class Handler(Protocol):
       async def handle(self, request: dict) -> str | None: ...
       @property
       def name(self) -> str: ...
   ```
2. Создать `HandlerRegistry`:
   ```python
   class HandlerRegistry:
       def register(self, name: str, handler: Handler) -> None: ...
       def get(self, name: str) -> Handler | None: ...
       def get_all(self) -> dict[str, Handler]: ...
   ```
3. Преобразовать функции в классы:
   - `handle_permission_request()` → `PermissionHandler` класс
   - `handle_fs_read()` → `FileSystemReadHandler` класс
   - `handle_terminal_*()` → `TerminalHandler` класс

**Ожидаемый результат:**
- Единая Registry для всех обработчиков
- Легко регистрировать новые handlers
- Нет магических строк в коде

**Критерии приемки:**
- [ ] `Handler` Protocol создан
- [ ] `HandlerRegistry` реализован
- [ ] Все handlers переписаны как классы
- [ ] Используется Registry во всех местах

---

### 2.4 Задача 4: Fix Type Annotations

**Приоритет:** 🟡 MEDIUM  
**Затронутые файлы:**
- `client.py` (строки 34-41)
- `tui/app.py` (type hints)
- `tui/managers/*.py` (неполные аннотации)

**Что делать:**
1. Заменить type aliases на Protocol/TypedDict:
   ```python
   class PermissionRequest(TypedDict):
       resource: str
       action: str
   ```
2. Добавить полные аннотации для всех функций
3. Запустить `mypy --strict` в CI

**Ожидаемый результат:**
- `mypy --strict` проходит
- IDE intellisense работает лучше
- Меньше runtime ошибок

**Критерии приемки:**
- [ ] Все type hints добавлены
- [ ] `mypy --strict` проходит
- [ ] Нет `Any` типов без причины

---

### 2.5 Задача 5: Add Comprehensive Logging

**Приоритет:** 🟡 MEDIUM  
**Затронутые файлы:**
- `logging.py` → расширить конфигурацию
- Все модули → добавить логирование в critical points

**Что делать:**
1. Добавить structured logging для:
   - Отправки/получения сообщений
   - Ошибок транспорта
   - State transitions
   - Handler выполнения
2. Использовать structlog с JSON output

**Ожидаемый результат:**
- Легко дебажить проблемы
- Видны все state transitions
- Performance metrics собираются

---

### 2.6 Итоги Фазы 1

После Фазы 1:
✅ ACPClient больше не привязан к WebSocket  
✅ Message parsing в одном месте  
✅ Handlers имеют общий интерфейс  
✅ Лучшая типизация  
✅ Лучше логирование  
✅ Все существующие тесты проходят  

**Обратная совместимость:** 100% (только внутренние изменения)

---

## 3. Фаза 2: Архитектурный рефакторинг (2-4 недели)

### Цель
Внедрить слоистую архитектуру, Repository Pattern, Dependency Injection.

### 3.1 Задача 1: Domain Layer Setup

**Затронутые файлы:**
- Создать `domain/` директорию
- `domain/entities/`
- `domain/repositories/`
- `domain/services/`

**Что делать:**
1. Создать Entity классы:
   ```python
   # domain/entities/session.py
   @dataclass
   class Session(Entity):
       id: str
       server_config: ServerConfig
       client_capabilities: ClientCapabilities
       status: SessionStatus
       created_at: datetime
   
   # domain/entities/message.py
   @dataclass
   class Message:
       id: str
       type: str
       content: dict[str, Any]
       metadata: MessageMetadata
   ```

2. Создать Repository интерфейсы:
   ```python
   # domain/repositories/session_repository.py
   class SessionRepository(ABC):
       async def save(self, session: Session) -> None: ...
       async def load(self, session_id: str) -> Session | None: ...
       async def delete(self, session_id: str) -> None: ...
       async def list_all(self) -> list[Session]: ...
   ```

3. Создать Service интерфейсы:
   ```python
   # domain/services/transport_service.py
   class TransportService(ABC):
       async def request(self, method: str, params: dict) -> dict: ...
       async def listen(self) -> AsyncIterator[dict]: ...
   ```

**Результат:**
- Чистая Domain слой без зависимостей
- Легко тестировать бизнес-логику
- Ясные контракты интерфейсов

---

### 3.2 Задача 2: Application Layer Use Cases

**Затронутые файлы:**
- Создать `application/use_cases/`
- `application/dto/`
- `application/services/`

**Что делать:**
1. Создать Use Cases:
   ```python
   # application/use_cases/session_use_case.py
   class CreateSessionUseCase:
       def __init__(
           self,
           transport: TransportService,
           session_repo: SessionRepository,
           logger: Logger
       ): ...
       
       async def execute(self, config: ServerConfig) -> Session:
           # Orchestration logic
   
   class LoadSessionUseCase:
       async def execute(self, session_id: str) -> Session: ...
   
   class PromptTurnUseCase:
       async def execute(self, session_id: str, prompt: str) -> PromptResult: ...
   ```

2. Создать Data Transfer Objects (DTO):
   ```python
   @dataclass
   class CreateSessionRequest:
       server_host: str
       server_port: int
       auth_method: str | None
   
   @dataclass
   class CreateSessionResponse:
       session_id: str
       server_capabilities: ServerCapabilities
   ```

3. Создать Application Services для оркестрации:
   ```python
   class ApplicationService:
       def __init__(self, container: DIContainer): ...
       
       async def create_session(self, request: CreateSessionRequest) -> CreateSessionResponse:
           use_case = self.container.resolve(CreateSessionUseCase)
           return await use_case.execute(...)
   ```

**Результат:**
- Clearly defined use cases
- DTO для типизированного обмена данными
- Легко добавлять новые use cases

---

### 3.3 Задача 3: Dependency Injection Container

**Затронутые файлы:**
- Создать `infrastructure/di/container.py`
- `infrastructure/di/providers.py`
- Обновить entry points

**Что делать:**
1. Создать DIContainer:
   ```python
   class DIContainer:
       def register(
           self,
           interface: type[T],
           implementation: type[T] | Callable[..., T],
           scope: Scope = Scope.SINGLETON
       ) -> None: ...
       
       def resolve(self, interface: type[T]) -> T: ...
   
   # Использование:
   container = DIContainer()
   container.register(TransportService, WebSocketTransport, Scope.SINGLETON)
   container.register(SessionRepository, InMemorySessionRepository, Scope.SINGLETON)
   container.register(CreateSessionUseCase, CreateSessionUseCase)
   
   use_case = container.resolve(CreateSessionUseCase)
   ```

2. Создать Provider конфигурацию:
   ```python
   class InfrastructureProvider:
       @staticmethod
       def provide_transport_service(config: ServerConfig) -> TransportService:
           return WebSocketTransport(config.host, config.port)
       
       @staticmethod
       def provide_session_repository() -> SessionRepository:
           return InMemorySessionRepository()
   ```

3. Обновить entry points (CLI, TUI):
   ```python
   async def main_cli():
       container = DIContainer()
       setup_infrastructure(container)
       app_service = container.resolve(ApplicationService)
       # Use app_service
   ```

**Результат:**
- Все зависимости управляются контейнером
- Легко переключаться на mock реализации в тестах
- Чистая инъекция зависимостей

---

### 3.4 Задача 4: Split ACPClient into Modules

**Затронутые файлы:**
- `client.py` → разбить на:
  - `infrastructure/transport/client_session.py` (низкоуровневый транспорт)
  - `infrastructure/services/acp_transport_service.py` (сервис)
  - `application/services/session_coordinator.py` (оркестрация)

**Что делать:**
1. Оставить `ACPClient` для обратной совместимости — обернуть новую архитектуру
2. Создать `ACPTransportService` который инкапсулирует низкоуровневую коммуникацию
3. Создать `SessionCoordinator` для управления жизненным циклом сессии

**Результат:**
- `ACPClient` остается стабильным API
- Внутренняя реализация на Clean Architecture
- Возможна постепенная миграция

---

### 3.5 Задача 5: State Machine для UI State

**Затронутые файлы:**
- Обновить `tui/managers/ui_state.py`
- Создать `application/state_machines/`

**Что делать:**
1. Создать State Machine:
   ```python
   class UIState(Enum):
       INITIAL = "initial"
       CONNECTED = "connected"
       SESSION_ACTIVE = "session_active"
       WAITING_RESPONSE = "waiting_response"
       PERMISSION_PENDING = "permission_pending"
       ERROR = "error"
   
   class UIStateMachine:
       def __init__(self):
           self.current_state = UIState.INITIAL
           self.transitions = {
               UIState.INITIAL: [UIState.CONNECTED, UIState.ERROR],
               UIState.CONNECTED: [UIState.SESSION_ACTIVE, UIState.ERROR],
               # ...
           }
       
       def can_transition(self, next_state: UIState) -> bool:
           return next_state in self.transitions.get(self.current_state, [])
       
       def transition(self, next_state: UIState) -> None:
           if self.can_transition(next_state):
               self.current_state = next_state
   ```

2. Добавить Event Dispatch:
   ```python
   class StateChangeEvent:
       previous_state: UIState
       new_state: UIState
       timestamp: datetime
   
   class EventDispatcher:
       def on_state_change(self, event: StateChangeEvent) -> None: ...
   ```

**Результат:**
- Предсказуемые state transitions
- Меньше bugs связанных с состоянием
- Легче дебажить

---

### 3.6 Итоги Фазы 2

После Фазы 2:
✅ Domain слой полностью определен  
✅ Application Use Cases реализованы  
✅ Dependency Injection работает  
✅ State Machine управляет UI состоянием  
✅ Все tests проходят  
✅ Обратная совместимость сохранена  

**Обратная совместимость:** 100% (новая архитектура параллельно со старой)

---

## 4. Фаза 3: Clean Architecture и Plugin System (1-2 месяца)

### 4.1 Задача 1: Event-Driven Architecture

**Что делать:**
1. Создать Event-шина:
   ```python
   class DomainEvent(ABC):
       aggregate_id: str
       occurred_at: datetime
   
   class SessionCreatedEvent(DomainEvent):
       session_id: str
       server_config: ServerConfig
   
   class EventBus:
       async def publish(self, event: DomainEvent) -> None: ...
       def subscribe(self, event_type: type[T], handler: Callable) -> None: ...
   ```

2. Переписать обработчики на Event-driven:
   ```python
   class PermissionGrantedEventHandler:
       async def handle(self, event: PermissionGrantedEvent) -> None:
           # Update UI, cache, etc.
   ```

**Результат:**
- Слабая связь между компонентами
- Легко добавлять новые обработчики событий

---

### 4.2 Задача 2: Plugin System

**Что делать:**
1. Создать Plugin интерфейс:
   ```python
   class Plugin(ABC):
       @property
       def name(self) -> str: ...
       
       @property
       def version(self) -> str: ...
       
       async def initialize(self, context: PluginContext) -> None: ...
       
       async def shutdown(self) -> None: ...
   
   class HandlerPlugin(Plugin):
       def get_handlers(self) -> dict[str, Handler]: ...
   ```

2. Создать PluginManager:
   ```python
   class PluginManager:
       def load_plugin(self, path: Path) -> Plugin: ...
       def list_plugins(self) -> list[Plugin]: ...
   ```

3. Позволить загружать handlers через плагины

**Результат:**
- Extensible система для добавления функционала
- Плагины могут быть в отдельных пакетах

---

### 4.3 Задача 3: Переписать TUI на новой архитектуре

**Затронутые файлы:**
- `tui/app.py` → разбить на слой представления и бизнес-логики
- `tui/components/` → обновить на новый API
- `tui/managers/` → переместить в Application слой

**Что делать:**
1. Создать `presentation/tui/` структуру
2. Отделить UI компоненты от бизнес-логики
3. Использовать DI для инъекции зависимостей

**Результат:**
- TUI полностью отделена от бизнес-логики
- Легче тестировать поведение

---

### 4.4 Итоги Фазы 3

После Фазы 3:
✅ Event-Driven архитектура полностью внедрена  
✅ Plugin System работает  
✅ TUI переписана на Clean Architecture  
✅ Полная модульность  
✅ Готово к масштабированию  

---

## 5. Новая структура проекта

```
acp-client/
├── src/acp_client/
│   ├── __init__.py
│   │
│   ├── domain/                          # Domain Layer (изолированная бизнес-логика)
│   │   ├── __init__.py
│   │   ├── entities/
│   │   │   ├── __init__.py
│   │   │   ├── session.py               # Сущность Session
│   │   │   ├── message.py               # Сущность Message
│   │   │   ├── permission.py            # Сущность Permission
│   │   │   └── tool_call.py             # Сущность ToolCall
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── session_repository.py    # SessionRepository ABC
│   │   │   ├── history_repository.py    # HistoryRepository ABC
│   │   │   └── cache_repository.py      # CacheRepository ABC
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── transport_service.py     # TransportService ABC
│   │   │   ├── filesystem_service.py    # FileSystemService ABC
│   │   │   └── terminal_service.py      # TerminalService ABC
│   │   │
│   │   ├── exceptions.py                # Domain-specific исключения
│   │   └── value_objects.py             # Value Objects (ServerConfig, etc.)
│   │
│   ├── application/                     # Application Layer (Use Cases)
│   │   ├── __init__.py
│   │   ├── dto/
│   │   │   ├── __init__.py
│   │   │   ├── session_dto.py           # SessionCreateRequest/Response
│   │   │   ├── prompt_dto.py            # PromptRequest/Response
│   │   │   └── permission_dto.py        # PermissionRequest/Response
│   │   │
│   │   ├── use_cases/
│   │   │   ├── __init__.py
│   │   │   ├── session_use_case.py      # CreateSession, LoadSession
│   │   │   ├── prompt_use_case.py       # PromptTurn, CancelPrompt
│   │   │   ├── permission_use_case.py   # RequestPermission, ApprovePermission
│   │   │   └── config_use_case.py       # SetConfigOption, GetConfigOptions
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── application_service.py   # Main Application Service (Orchestrator)
│   │   │   ├── session_coordinator.py   # Session lifecycle management
│   │   │   └── event_publisher.py       # Event publishing service
│   │   │
│   │   ├── state_machines/
│   │   │   ├── __init__.py
│   │   │   ├── ui_state_machine.py      # UI State Machine
│   │   │   └── session_state_machine.py # Session State Machine
│   │   │
│   │   └── exceptions.py                # Application-level исключения
│   │
│   ├── infrastructure/                  # Infrastructure Layer (Implementations)
│   │   ├── __init__.py
│   │   │
│   │   ├── di/
│   │   │   ├── __init__.py
│   │   │   ├── container.py             # DIContainer
│   │   │   ├── providers.py             # DI провайдеры
│   │   │   └── scopes.py                # Scope enum (SINGLETON, TRANSIENT)
│   │   │
│   │   ├── transport/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # TransportSession ABC
│   │   │   ├── websocket.py             # WebSocketTransport
│   │   │   ├── tcp.py                   # TCPTransport (future)
│   │   │   └── transport_service_impl.py # ACPTransportService реализация
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── memory_session_repo.py   # InMemorySessionRepository
│   │   │   ├── file_session_repo.py     # FileSystemSessionRepository (future)
│   │   │   └── history_repo_impl.py     # HistoryRepository реализация
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── filesystem_service_impl.py
│   │   │   ├── terminal_service_impl.py
│   │   │   ├── permission_service.py
│   │   │   └── cache_service.py
│   │   │
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── message_parser.py        # MessageParser ABC
│   │   │   └── acp_parser.py            # ACPMessageParser реализация
│   │   │
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # Handler Protocol
│   │   │   ├── registry.py              # HandlerRegistry
│   │   │   ├── permission_handler.py    # PermissionHandler реализация
│   │   │   ├── filesystem_handler.py    # FileSystemHandler реализация
│   │   │   └── terminal_handler.py      # TerminalHandler реализация
│   │   │
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # DomainEvent ABC
│   │   │   ├── bus.py                   # EventBus реализация
│   │   │   └── handlers.py              # Event обработчики
│   │   │
│   │   ├── plugins/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # Plugin ABC
│   │   │   └── manager.py               # PluginManager
│   │   │
│   │   └── logging.py                   # Логирование конфигурация
│   │
│   ├── presentation/                    # Presentation Layer (UI)
│   │   ├── __init__.py
│   │   │
│   │   ├── cli/
│   │   │   ├── __init__.py
│   │   │   ├── commands.py              # CLI команды
│   │   │   └── formatter.py             # Форматирование вывода
│   │   │
│   │   └── tui/
│   │       ├── __init__.py
│   │       ├── app.py                   # TUI приложение (thin wrapper)
│   │       ├── config.py                # TUI конфигурация
│   │       │
│   │       ├── components/
│   │       │   ├── __init__.py
│   │       │   ├── chat_view.py
│   │       │   ├── file_tree.py
│   │       │   ├── terminal_output.py
│   │       │   └── ... (остальные компоненты)
│   │       │
│   │       ├── viewmodels/              # NEW: ViewModel слой для TUI
│   │       │   ├── __init__.py
│   │       │   ├── session_viewmodel.py
│   │       │   ├── chat_viewmodel.py
│   │       │   └── ui_viewmodel.py
│   │       │
│   │       └── styles/
│   │           └── app.tcss
│   │
│   ├── client.py                        # Facade (обратная совместимость)
│   ├── cli.py                           # CLI Entry point (обратная совместимость)
│   ├── messages.py                      # Message типы (обратная совместимость)
│   └── logging.py                       # Logging setup (обратная совместимость)
│
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   │   ├── test_entities.py
│   │   │   ├── test_repositories.py
│   │   │   └── test_services.py
│   │   │
│   │   ├── application/
│   │   │   ├── test_use_cases.py
│   │   │   ├── test_state_machine.py
│   │   │   └── test_event_bus.py
│   │   │
│   │   └── infrastructure/
│   │       ├── test_transport.py
│   │       ├── test_parsers.py
│   │       ├── test_handlers.py
│   │       └── test_di_container.py
│   │
│   ├── integration/
│   │   ├── test_session_workflow.py
│   │   ├── test_prompt_workflow.py
│   │   └── test_with_server.py
│   │
│   ├── e2e/
│   │   ├── test_cli.py
│   │   ├── test_tui_workflows.py
│   │   └── test_full_session.py
│   │
│   ├── fixtures/
│   │   ├── mock_transport.py
│   │   ├── mock_repositories.py
│   │   └── test_data.py
│   │
│   └── conftest.py
│
├── pyproject.toml
└── README.md
```

---

## 6. Примеры кода для ключевых компонентов

### 6.1 Transport Abstraction

**File:** `infrastructure/transport/base.py`
```python
from abc import ABC, abstractmethod
from typing import AsyncIterator

class TransportSession(ABC):
    """Абстрактный интерфейс для транспорта ACP-клиента.
    
    Позволяет подменять WebSocket на TCP, gRPC и другие протоколы.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Установить соединение с сервером."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Отключиться от сервера."""
        pass

    @abstractmethod
    async def send(self, message: dict) -> None:
        """Отправить сообщение серверу.
        
        Args:
            message: JSON-сериализуемый словарь
            
        Raises:
            TransportError: если соединение потеряно
        """
        pass

    @abstractmethod
    async def receive(self) -> dict:
        """Получить следующее сообщение от сервера.
        
        Returns:
            JSON-десериализованный словарь
            
        Raises:
            TransportError: если соединение потеряно
        """
        pass

    @abstractmethod
    async def listen(self) -> AsyncIterator[dict]:
        """Слушать входящие сообщения (итератор).
        
        Yields:
            JSON-десериализованные сообщения
        """
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Проверить статус соединения."""
        pass
```

**File:** `infrastructure/transport/websocket.py`
```python
import asyncio
import json
from typing import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from .base import TransportSession


class WebSocketTransport(TransportSession):
    """WebSocket реализация транспорта."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.connection: ClientConnection | None = None
        self._connected = False

    async def connect(self) -> None:
        """Подключиться к WebSocket серверу."""
        try:
            self.connection = await websockets.asyncio.client.connect(self.uri)
            self._connected = True
        except Exception as e:
            raise TransportError(f"Failed to connect to {self.uri}: {e}")

    async def disconnect(self) -> None:
        """Отключиться от WebSocket сервера."""
        if self.connection:
            await self.connection.close()
            self._connected = False

    async def send(self, message: dict) -> None:
        """Отправить JSON сообщение."""
        if not self._connected or not self.connection:
            raise TransportError("Not connected")
        
        try:
            await self.connection.send(json.dumps(message))
        except Exception as e:
            self._connected = False
            raise TransportError(f"Send failed: {e}")

    async def receive(self) -> dict:
        """Получить JSON сообщение."""
        if not self._connected or not self.connection:
            raise TransportError("Not connected")
        
        try:
            message = await self.connection.recv()
            return json.loads(message)
        except Exception as e:
            self._connected = False
            raise TransportError(f"Receive failed: {e}")

    async def listen(self) -> AsyncIterator[dict]:
        """Слушать входящие сообщения."""
        if not self._connected or not self.connection:
            raise TransportError("Not connected")
        
        try:
            async for message in self.connection:
                yield json.loads(message)
        except Exception as e:
            self._connected = False
            raise TransportError(f"Listen failed: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected


class TransportError(Exception):
    """Ошибка транспорта."""
    pass
```

---

### 6.2 Handler Protocol и Registry

**File:** `infrastructure/handlers/base.py`
```python
from abc import ABC, abstractmethod
from typing import Any, Protocol

class Handler(Protocol):
    """Протокол для обработчиков пермиссий, ФС, терминала."""

    async def handle(self, request: dict[str, Any]) -> str | None:
        """Обработать запрос и вернуть результат.
        
        Args:
            request: Словарь с параметрами запроса
            
        Returns:
            Результат обработки или None
        """
        ...

    @property
    def name(self) -> str:
        """Имя обработчика для логирования."""
        ...
```

**File:** `infrastructure/handlers/registry.py`
```python
from typing import Any

from .base import Handler


class HandlerRegistry:
    """Реестр обработчиков для пермиссий, ФС, терминала."""

    def __init__(self):
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        """Зарегистрировать обработчик.
        
        Args:
            name: Уникальное имя обработчика
            handler: Реализация Handler
        """
        self._handlers[name] = handler

    def unregister(self, name: str) -> None:
        """Отменить регистрацию обработчика."""
        self._handlers.pop(name, None)

    def get(self, name: str) -> Handler | None:
        """Получить обработчик по имени."""
        return self._handlers.get(name)

    def get_all(self) -> dict[str, Handler]:
        """Получить все зарегистрированные обработчики."""
        return self._handlers.copy()

    async def dispatch(self, name: str, request: dict[str, Any]) -> str | None:
        """Отправить запрос нужному обработчику."""
        handler = self.get(name)
        if not handler:
            raise ValueError(f"Handler '{name}' not found")
        return await handler.handle(request)
```

---

### 6.3 Repository Pattern

**File:** `domain/repositories/session_repository.py`
```python
from abc import ABC, abstractmethod
from typing import Optional

from ..entities.session import Session


class SessionRepository(ABC):
    """Абстрактный репозиторий для управления сессиями."""

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Сохранить сессию.
        
        Args:
            session: Объект сессии для сохранения
        """
        pass

    @abstractmethod
    async def load(self, session_id: str) -> Optional[Session]:
        """Загрузить сессию по ID.
        
        Args:
            session_id: Уникальный ID сессии
            
        Returns:
            Объект Session или None если не найдена
        """
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Удалить сессию.
        
        Args:
            session_id: ID сессии для удаления
        """
        pass

    @abstractmethod
    async def list_all(self) -> list[Session]:
        """Получить список всех сохраненных сессий.
        
        Returns:
            Список объектов Session
        """
        pass

    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """Проверить существование сессии."""
        pass
```

**File:** `infrastructure/repositories/memory_session_repo.py`
```python
from typing import Optional

from domain.entities.session import Session
from domain.repositories.session_repository import SessionRepository


class InMemorySessionRepository(SessionRepository):
    """Реализация репозитория сессий в памяти."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    async def save(self, session: Session) -> None:
        """Сохранить сессию в памяти."""
        self._sessions[session.id] = session

    async def load(self, session_id: str) -> Optional[Session]:
        """Загрузить сессию из памяти."""
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        """Удалить сессию из памяти."""
        self._sessions.pop(session_id, None)

    async def list_all(self) -> list[Session]:
        """Получить все сессии."""
        return list(self._sessions.values())

    async def exists(self, session_id: str) -> bool:
        """Проверить наличие сессии."""
        return session_id in self._sessions
```

---

### 6.4 DI Container Setup

**File:** `infrastructure/di/container.py`
```python
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

T = TypeVar('T')


class Scope(Enum):
    """Области видимости для DI контейнера."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class DIContainer:
    """Простой контейнер зависимостей."""

    def __init__(self):
        self._registrations: dict[type, tuple[Callable, Scope]] = {}
        self._singletons: dict[type, Any] = {}

    def register(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T],
        scope: Scope = Scope.SINGLETON
    ) -> None:
        """Зарегистрировать зависимость.
        
        Args:
            interface: Тип интерфейса (ABC или Protocol)
            implementation: Класс реализации или фабрика
            scope: Область видимости (SINGLETON или TRANSIENT)
        """
        factory = implementation if callable(implementation) else implementation
        self._registrations[interface] = (factory, scope)

    def resolve(self, interface: type[T]) -> T:
        """Получить экземпляр по интерфейсу.
        
        Args:
            interface: Тип интерфейса для получения
            
        Returns:
            Экземпляр реализации
            
        Raises:
            KeyError: если интерфейс не зарегистрирован
        """
        if interface not in self._registrations:
            raise KeyError(f"No registration for {interface}")

        factory, scope = self._registrations[interface]

        # Для SINGLETON - возвращаем кэшированный экземпляр
        if scope == Scope.SINGLETON:
            if interface not in self._singletons:
                self._singletons[interface] = self._create_instance(factory)
            return self._singletons[interface]

        # Для TRANSIENT - создаем новый экземпляр каждый раз
        return self._create_instance(factory)

    def _create_instance(self, factory: Callable[..., T]) -> T:
        """Создать экземпляр с автоматической инъекцией зависимостей."""
        # Упрощенная версия - в реальной системе нужна полная inspection сигнатур
        try:
            return factory()
        except TypeError:
            # Если конструктор требует параметров - попытаться инъектировать
            # В реальной системе здесь была бы сложная логика reflection
            raise
```

**File:** `infrastructure/di/providers.py`
```python
from domain.repositories.session_repository import SessionRepository
from domain.services.transport_service import TransportService
from infrastructure.repositories.memory_session_repo import InMemorySessionRepository
from infrastructure.services.acp_transport_service import ACPTransportService
from infrastructure.transport.websocket import WebSocketTransport


class InfrastructureProvider:
    """Провайдер для регистрации Infrastructure зависимостей."""

    @staticmethod
    def register_all(container: DIContainer, host: str, port: int) -> None:
        """Зарегистрировать все Infrastructure сервисы.
        
        Args:
            container: DIContainer для регистрации
            host: Хост ACP сервера
            port: Порт ACP сервера
        """
        # Transport
        container.register(
            TransportService,
            lambda: ACPTransportService(
                WebSocketTransport(host, port)
            ),
            Scope.SINGLETON
        )

        # Repositories
        container.register(
            SessionRepository,
            InMemorySessionRepository,
            Scope.SINGLETON
        )
```

---

### 6.5 Use Case пример

**File:** `application/use_cases/session_use_case.py`
```python
from dataclasses import dataclass

from domain.entities.session import Session
from domain.repositories.session_repository import SessionRepository
from domain.services.transport_service import TransportService


@dataclass
class CreateSessionRequest:
    """DTO для запроса создания сессии."""
    server_host: str
    server_port: int
    auth_method: str | None = None
    api_key: str | None = None


@dataclass
class CreateSessionResponse:
    """DTO для ответа создания сессии."""
    session_id: str
    status: str
    server_capabilities: dict


class CreateSessionUseCase:
    """Use Case для создания новой ACP сессии."""

    def __init__(
        self,
        transport_service: TransportService,
        session_repository: SessionRepository
    ):
        self.transport_service = transport_service
        self.session_repository = session_repository

    async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Выполнить создание сессии.
        
        Args:
            request: Параметры создания сессии
            
        Returns:
            Ответ с информацией о новой сессии
        """
        # 1. Инициализировать транспорт
        await self.transport_service.connect(request.server_host, request.server_port)

        # 2. Выполнить authenticate и initialize
        auth_result = await self.transport_service.authenticate(
            auth_method=request.auth_method,
            api_key=request.api_key
        )

        init_result = await self.transport_service.initialize(
            client_name="acp-client",
            client_version="1.0.0"
        )

        # 3. Создать объект сессии
        session = Session(
            id=init_result.session_id,
            server_config=request,
            status="active",
            created_at=datetime.now()
        )

        # 4. Сохранить в репозитории
        await self.session_repository.save(session)

        return CreateSessionResponse(
            session_id=session.id,
            status="active",
            server_capabilities=init_result.server_capabilities
        )
```

---

## 7. Стратегия тестирования

### 7.1 Unit тесты (Domain Layer)

**File:** `tests/unit/domain/test_entities.py`
```python
import pytest
from datetime import datetime
from acp_client.domain.entities.session import Session


class TestSession:
    """Тесты для сущности Session."""

    def test_session_creation(self):
        """Test создания объекта сессии."""
        session = Session(
            id="test-session",
            server_config={"host": "localhost"},
            status="active",
            created_at=datetime.now()
        )
        
        assert session.id == "test-session"
        assert session.status == "active"

    def test_session_status_validation(self):
        """Test валидации статуса сессии."""
        with pytest.raises(ValueError):
            Session(
                id="test",
                server_config={},
                status="invalid_status",
                created_at=datetime.now()
            )
```

### 7.2 Integration тесты

**File:** `tests/integration/test_session_workflow.py`
```python
import pytest
from acp_client.application.use_cases.session_use_case import CreateSessionUseCase
from acp_client.infrastructure.repositories.memory_session_repo import InMemorySessionRepository
from acp_client.infrastructure.services.mock_transport_service import MockTransportService


@pytest.mark.asyncio
async def test_create_session_workflow():
    """Test полного workflow создания сессии."""
    mock_transport = MockTransportService()
    repository = InMemorySessionRepository()
    use_case = CreateSessionUseCase(mock_transport, repository)

    response = await use_case.execute(
        CreateSessionRequest(
            server_host="localhost",
            server_port=8765,
            auth_method="api_key",
            api_key="test-key"
        )
    )

    assert response.status == "active"
    
    # Проверить что сессия сохранена в репозитории
    saved_session = await repository.load(response.session_id)
    assert saved_session is not None
    assert saved_session.id == response.session_id
```

### 7.3 E2E тесты

**File:** `tests/e2e/test_cli.py`
```python
import subprocess
import json
import pytest


@pytest.mark.e2e
def test_cli_session_list():
    """Test CLI команда для списка сессий."""
    result = subprocess.run(
        ["acp-client", "--method", "session/list"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "sessions" in output
```

### 7.4 Покрытие критичных путей

| Компонент | Critical Paths | Target Coverage |
|-----------|-----------------|-----------------|
| Transport | connect, send, receive, disconnect | 90%+ |
| Repository | save, load, delete, list | 95%+ |
| Use Cases | execute main flow + error cases | 90%+ |
| Handlers | handle, dispatch | 85%+ |
| State Machine | transitions, validation | 95%+ |

---

## 8. Риски и митигация

### 8.1 Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|--------|-----------|
| **Breaking changes в публичном API** | Средняя | Высокое | Создать Facade (старый API оборачивает новый), плавная миграция через deprecation warnings |
| **Performance деградация** | Низкая | Среднее | Профилирование на каждой фазе, бенчмарки для критичных путей |
| **Потеря функциональности** | Низкая | Высокое | Параллельная реализация, feature flags для переключения, comprehensive тестирование |
| **Сложность миграции TUI** | Высокая | Высокое | Постепенная миграция компонентов, ViewModel слой как промежуточный этап |
| **DI контейнер overhead** | Низкая | Низкое | Использовать простой DIContainer, profile на реальных сценариях |

### 8.2 Организационные риски

| Риск | Митигация |
|------|-----------|
| Недостаток ресурсов | Разбить на небольшие фазы, можно делать параллельно с другой работой |
| Отсутствие знаний Clean Architecture | Документирование, code reviews, паттерны из проверенных источников |
| Потеря фокуса | Четкие критерии приемки для каждой фазы, регулярные синхронизации |

### 8.3 Стратегия миграции

1. **Параллельная реализация** (Фаза 1-2)
   - Новая архитектура существует параллельно со старой
   - Facade оборачивает новый код, возвращая старый интерфейс
   - Постепенная миграция компонентов один за другим

2. **Feature Flags** (Фаза 2-3)
   - Использовать feature flags для переключения между старой и новой реализацией
   - Позволяет A/B тестировать на реальных пользователях
   - Быстро откатиться если что-то сломалось

3. **Rollout Strategy** (Фаза 3)
   - Вначале только на развитие (dev версия)
   - Затем на beta тестеры
   - Наконец на production

---

## 9. Инструменты и зависимости

### Новые зависимости (если требуются)

```toml
[dependencies]
# Уже есть:
structlog = "*"
textual = "*"
websockets = "*"

# Дополнительно (optional):
pydantic = "*"  # Для валидации моделей (но можно обойтись)
dependency-injector = "*"  # Или использовать встроенный простой контейнер
pytest-asyncio = "*"  # Уже есть в dev
```

### CI/CD изменения

```bash
# Добавить в Makefile:
make check-typing  # mypy --strict
make check-coverage  # pytest с покрытием
make check-performance  # Бенчмарки
```

---

## 10. Метрики успеха

| Метрика | До рефакторинга | После Фазы 1 | После Фазы 3 | Target |
|---------|-----------------|--------------|--------------|--------|
| **Cyclomatic Complexity (max)** | 15 | 10 | 5 | < 5 |
| **Test Coverage** | 60% | 75% | 90% | >= 90% |
| **Lines per Function (avg)** | 25 | 15 | 10 | <= 10 |
| **Module Coupling** | High | Medium | Low | Low |
| **Time to Add Feature** | Slow | Medium | Fast | Fast |

---

## 11. Temporal Plan

### Фаза 1: Quick Wins
- **Неделя 1:** Tasks 1-2 (Transport, Parser)
- **Неделя 2:** Tasks 3-5 (Registry, Types, Logging)
- **Review & Testing:** 3-4 дня

### Фаза 2: Architecture
- **Неделя 1:** Domain & Application слои
- **Неделя 2:** DI Container, State Machine
- **Неделя 3-4:** ACPClient split, Integration tests
- **Review & Testing:** 1 неделя

### Фаза 3: Clean Architecture
- **Неделя 1-2:** Event-Driven, Plugin System
- **Неделя 3-4:** TUI migration
- **Неделя 5-6:** E2E testing, documentation
- **Review & Stabilization:** 1-2 недели

**Общее время:** 8-10 недель при полной занятости одного разработчика

---

## 12. Контрольные точки и критерии выхода

### Фаза 1 - Выход
- ✅ Transport abstraction работает
- ✅ All message parsers мигрированы в Parser Service
- ✅ Handler Registry работает
- ✅ Type annotations полные
- ✅ Все tests проходят
- ✅ Performance не деградировала
- ✅ Documentation обновлена

### Фаза 2 - Выход
- ✅ Domain Layer полностью определен
- ✅ Application Use Cases реализованы
- ✅ DI Container работает с real инъекциями
- ✅ State Machine работает корректно
- ✅ Integration tests покрывают основные workflow
- ✅ Старый API через Facade работает идентично

### Фаза 3 - Выход
- ✅ Event-Driven полностью внедрен
- ✅ Plugin System работает
- ✅ TUI переписана на новой архитектуре
- ✅ E2E тесты все проходят
- ✅ Documentation complete
- ✅ Ready для production

---

## 13. Документация и kommunication

### Документы для создания/обновления

1. **Architecture Decision Records (ADRs)**
   - `doc/ADR-001-transport-abstraction.md`
   - `doc/ADR-002-clean-architecture-layers.md`
   - `doc/ADR-003-di-container-approach.md`

2. **Developer Guides**
   - `doc/DEVELOPING.md` — как разворачивать окружение
   - `doc/ARCHITECTURE-LAYERS.md` — описание слоев
   - `doc/TESTING-STRATEGY.md` — как писать тесты

3. **Migration Guides**
   - `doc/MIGRATION-FROM-OLD-API.md` — для пользователей старого API
   - `doc/INTERNAL-MIGRATION.md` — для разработчиков

### Статус Updates

- Еженедельные updates в проекте (GitHub issues, Discord)
- Демо new features в конце каждой фазы
- Регулярные code reviews (все PR проверяются)

---

## Заключение

Этот план трансформирует acp-client из monolithic приложения в модульную, тестируемую, расширяемую систему, следуя принципам Clean Architecture и SOLID.

**Ключевые преимущества:**
- ✅ Меньше bugs благодаря лучшей типизации
- ✅ Быстрее добавлять features благодаря Use Cases
- ✅ Проще тестировать благодаря DI и слоистой архитектуре
- ✅ Проще интегрировать новые транспорты (TCP, gRPC)
- ✅ Готово к масштабированию и новым требованиям

**Главное правило:** Каждая фаза кончается **работающим кодом**, готовым к продакшену.
