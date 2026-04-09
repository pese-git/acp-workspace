# Руководство по миграции с Legacy API на Clean Architecture

Полное руководство по переходу с простого API старой версии на новую Clean Architecture с MVVM в acp-client.

## Содержание

1. [Введение](#введение)
2. [Почему был нужен рефакторинг](#почему-был-нужен-рефакторинг)
3. [Обзор изменений](#обзор-изменений)
4. [Breaking Changes](#breaking-changes)
5. [Миграция компонентов](#миграция-компонентов)
6. [Пошаговая миграция](#пошаговая-миграция)
7. [Примеры миграции](#примеры-миграции)
8. [Совместимость](#совместимость)
9. [Checklist миграции](#checklist-миграции)
10. [Troubleshooting](#troubleshooting)
11. [Дополнительные ресурсы](#дополнительные-ресурсы)

---

## Введение

### Что произошло

acp-client прошел масштабный рефакторинг от простого клиента к **Clean Architecture** с **MVVM** паттерном. Это был больший, но необходимый переход для обеспечения масштабируемости, тестируемости и поддерживаемости кода.

### Для кого это руководство

Если вы:
- Разрабатывали код с использованием старого API acp-client
- Используете функции из `client.py`, `helpers/`, или `tui/managers/`
- Встраивали acp-client в ваше приложение
- Тестировали компоненты TUI

...то это руководство для вас.

### Ключевые сроки

- **Старый API**: До фазы 4
- **Новая архитектура**: Фаза 4 (текущая версия)
- **Поддержка старого API**: Постепенная отработка (deprecated warnings)

---

## Почему был нужен рефакторинг

### Проблемы старой архитектуры

**Слабые места:**
- **Нет разделения слоев**: Бизнес-логика смешана с UI логикой
- **Сложный тестинг**: Менеджеры жестко связаны с транспортом и UI
- **Нет DI**: Зависимости захардкодены, сложно подменять для тестов
- **Нет реактивности**: UI обновляется императивно через `refresh()`
- **Нет Observer pattern**: Каждый компонент отвечает за свои обновления
- **Сложно масштабировать**: Добавление новой функции требует изменений повсюду

### Преимущества новой архитектуры

**Улучшения:**
- ✅ **Clean Architecture**: Четкое разделение на 5 слоев
- ✅ **Тестируемость**: Каждый слой тестируется отдельно
- ✅ **DI Container**: Все зависимости управляются централизованно
- ✅ **Observable pattern**: Реактивные обновления UI
- ✅ **MVVM**: UI отделена от логики через ViewModels
- ✅ **Event-driven**: Слабая связанность через Event Bus
- ✅ **Масштабируемость**: Легко добавлять новые функции

---

## Обзор изменений

### Что изменилось на высоком уровне

| Аспект | Было | Стало |
|--------|------|-------|
| **Архитектура** | Слои не разделены | Clean Architecture (5 слоев) |
| **Бизнес-логика** | В менеджерах | В Use Cases |
| **Управление зависимостями** | Захардкодено | DI Container |
| **Обновление UI** | Императивное (`refresh()`) | Декларативное (Observable) |
| **Паттерн UI** | MVC (слабо) | MVVM |
| **Связанность** | Высокая | Низкая (через интерфейсы) |
| **Реактивность** | Нет | Event Bus + Observable |
| **Тестирование** | Сложное | Простое (через DI) |

### Архитектура: До и После

**Старая архитектура (плоская):**
```
┌─────────────────────────────────────┐
│         TUI (Textual)               │
│  Напрямую вызывает менеджеры        │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌─────▼───────┐
│  Managers   │  │  Helpers    │
│ (Business   │  │ (Auth,      │
│  Logic)     │  │  Session)   │
└──────┬──────┘  └─────┬───────┘
       │                │
       └───────┬────────┘
               │
        ┌──────▼──────┐
        │   client.py │
        │   (TCP/WS)  │
        └─────────────┘
```

**Новая архитектура (Clean Architecture 5 слоев):**
```
┌────────────────────────────────────┐
│    TUI Layer (Textual)             │
│    Components + Navigation          │
└────────────┬───────────────────────┘
             │ использует
             ▼
┌────────────────────────────────────┐
│  Presentation Layer (MVVM)         │
│  ViewModels + Observable           │
└────────────┬───────────────────────┘
             │ использует
             ▼
┌────────────────────────────────────┐
│  Application Layer                 │
│  Use Cases + DTOs                  │
└────────────┬───────────────────────┘
             │ использует
             ▼
┌────────────────────────────────────┐
│  Infrastructure Layer              │
│  DI + Transport + Repositories     │
└────────────┬───────────────────────┘
             │ реализует
             ▼
┌────────────────────────────────────┐
│  Domain Layer                      │
│  Entities + Events + Interfaces    │
└────────────────────────────────────┘
```

---

## Breaking Changes

### Таблица изменений API

| Старый компонент | Новый компонент | Тип изменения | Комментарий |
|-----------------|-----------------|---------------|-----------|
| `client.send_request()` | `UseCase.execute()` | BREAKING | Используйте Use Cases из Application Layer |
| `ConnectionManager` | `ConnectUseCase` + `ACPTransportService` | BREAKING | Разделение: логика (Use Case) и транспорт (Service) |
| `SessionManager` | `CreateSessionUseCase` + `SessionViewModel` | BREAKING | Use Case для создания, ViewModel для состояния |
| Прямой доступ к `transport` | Через `TransportService` интерфейс | BREAKING | Инверсия управления зависимостями |
| Менеджеры с методами `update_data()` | ViewModels с Observable свойствами | BREAKING | Реактивный подход вместо императивного |
| Нет DI контейнера | `DIContainer` + `DIBootstrapper` | BREAKING | Все зависимости через контейнер |
| `helpers.auth.create_session()` | `CreateSessionUseCase` | DEPRECATED | Используйте `container.resolve(CreateSessionUseCase)` |
| `handlers/` функции | Event Bus подписки | DEPRECATED | Используйте `event_bus.subscribe(EventType, handler)` |
| `tui/managers/` классы | ViewModels + Navigation Manager | DEPRECATED | Состояние в ViewModels, навигация в NavigationManager |
| `messages.py` протоколь | `messages.py` (без изменений) | COMPATIBLE | Остается совместим, но оборачивается в DTOs |

### Ключевые различия

#### 1. Вызов функционала

**Было (старый API):**
```python
from acp_client.client import ACPClient

client = ACPClient("ws://localhost:8000")
await client.connect()
response = await client.send_request({
    "method": "session/new",
    "params": {"name": "My Session"}
})
```

**Стало (новый API):**
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import CreateSessionUseCase
from acp_client.application.dto import CreateSessionRequest

container = DIBootstrapper.build(host="localhost", port=8000)
use_case = container.resolve(CreateSessionUseCase)

request = CreateSessionRequest(name="My Session")
response = await use_case.execute(request)
```

#### 2. Управление состоянием UI

**Было (старый API):**
```python
class ChatView(Widget):
    def __init__(self):
        self.messages = []
    
    def add_message(self, message):
        self.messages.append(message)
        self.refresh()  # Явное обновление
```

**Стало (новый API):**
```python
class ChatView(Widget):
    def __init__(self, view_model: ChatViewModel):
        self.view_model = view_model
        # Автоматическое обновление при изменении
        self.view_model.subscribe(self._on_state_changed)
    
    def _on_state_changed(self):
        # Перерисовка при изменении ViewModel
        self.refresh()
```

#### 3. Обработка событий

**Было (старый API):**
```python
# handlers/filesystem.py
async def handle_filesystem_event(event):
    # Прямая обработка события
    pass

# В коде где-то
await handle_filesystem_event(event)
```

**Стало (новый API):**
```python
from acp_client.infrastructure.events.bus import EventBus
from acp_client.domain.events import FileSystemEvent

# В инициализации
event_bus = container.resolve(EventBus)
event_bus.subscribe(FileSystemEvent, handle_filesystem_event)

# Где-то в коде
event_bus.publish(FileSystemEvent(...))
```

---

## Миграция компонентов

### 3.1 Миграция транспорта и подключения

#### Старый подход

```python
from acp_client.client import ACPClient

# Создание клиента
client = ACPClient("ws://localhost:8000")

# Подключение
await client.connect()

# Отправка запроса
response = await client.send_request({
    "method": "initialize",
    "params": {}
})
```

#### Новый подход

```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import InitializeUseCase

# Инициализация DI контейнера
container = DIBootstrapper.build(host="localhost", port=8000)

# Получение use case
initialize_use_case = container.resolve(InitializeUseCase)

# Выполнение
result = await initialize_use_case.execute()
print(f"Server: {result.protocol_version}")
```

#### Что происходит за кулисами

1. **DIBootstrapper.build()** регистрирует все компоненты:
   - EventBus - шина событий
   - ACPTransportService - низкоуровневая коммуникация
   - SessionRepository - хранилище сессий
   - SessionCoordinator - оркестрация
   - ViewModels - слой представления

2. **InitializeUseCase** использует TransportService для подключения:
   ```python
   class InitializeUseCase(UseCase):
       def __init__(self, transport: TransportService):
           self._transport = transport
       
       async def execute(self):
           await self._transport.connect()
           # Отправка initialize запроса
           # Получение ответа
   ```

3. **ACPTransportService** инкапсулирует WebSocket логику

### 3.2 Миграция управления сессиями

#### Старый подход

```python
from acp_client.helpers.session import create_session, list_sessions

# Создание сессии
session_id = await create_session(client, "My Session")

# Список сессий
sessions = await list_sessions(client)

# Загрузка сессии
session = await load_session(client, session_id)
```

#### Новый подход

```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import (
    CreateSessionUseCase,
    ListSessionsUseCase,
    LoadSessionUseCase,
)
from acp_client.application.dto import CreateSessionRequest

container = DIBootstrapper.build(host="localhost", port=8000)

# Создание сессии
create_use_case = container.resolve(CreateSessionUseCase)
session = await create_use_case.execute(
    CreateSessionRequest(name="My Session")
)

# Список сессий
list_use_case = container.resolve(ListSessionsUseCase)
sessions = await list_use_case.execute()

# Загрузка сессии
load_use_case = container.resolve(LoadSessionUseCase)
loaded = await load_use_case.execute(session.id)
```

#### Структура данных

**Старый формат (dict):**
```python
{
    "id": "session-123",
    "name": "My Session",
    "created_at": "2024-01-01T00:00:00Z",
}
```

**Новый формат (Entity + DTO):**
```python
# Domain Entity (в памяти)
Session(
    id="session-123",
    name="My Session",
    created_at=datetime.now(),
    state=SessionState.INITIALIZED,
)

# DTO (для передачи между слоями)
CreateSessionResponse(
    session_id="session-123",
    name="My Session",
)
```

### 3.3 Миграция UI компонентов

#### Старый подход (MVC/прямой доступ к данным)

```python
from textual.app import ComposeResult
from textual.widgets import Static

class ChatView(Static):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []
        self.manager = ChatManager()
    
    def compose(self) -> ComposeResult:
        # Рендеринг UI
        yield RichLog()
    
    async def load_messages(self):
        # Прямой вызов менеджера
        self.messages = await self.manager.get_messages()
        self.refresh()  # Явное обновление UI
```

#### Новый подход (MVVM с Observable)

```python
from textual.app import ComposeResult
from textual.widgets import Static
from acp_client.presentation.chat_view_model import ChatViewModel

class ChatView(Static):
    def __init__(self, view_model: ChatViewModel):
        super().__init__()
        self.view_model = view_model
        
        # Подписка на изменения
        self.view_model.messages.subscribe(self._on_messages_changed)
        self.view_model.status.subscribe(self._on_status_changed)
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="chat_log")
    
    def _on_messages_changed(self):
        """Вызывается автоматически при изменении messages"""
        messages = self.view_model.messages.value
        # Обновление отображения
        self.refresh()
    
    def _on_status_changed(self):
        """Вызывается автоматически при изменении status"""
        status = self.view_model.status.value
        # Обновление статуса
        self.refresh()
```

#### ViewModel (Business Logic)

```python
from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable

class ChatViewModel(BaseViewModel):
    def __init__(self, send_prompt_use_case: SendPromptUseCase):
        super().__init__()
        self._send_prompt_use_case = send_prompt_use_case
        
        # Observable свойства
        self.messages = Observable[list[Message]]([])
        self.status = Observable[str]("idle")
    
    async def send_message(self, prompt: str) -> None:
        """Отправить сообщение (бизнес-логика)"""
        self.status.value = "loading"
        
        try:
            result = await self._send_prompt_use_case.execute(
                SendPromptRequest(prompt=prompt)
            )
            self.messages.value.append(result.message)
        finally:
            self.status.value = "idle"
```

#### Observable Pattern

Observable - это реактивное свойство, которое уведомляет подписчиков об изменениях:

```python
from acp_client.presentation.observable import Observable

# Создание Observable
counter = Observable(0)

# Подписка на изменения
unsubscribe = counter.subscribe(lambda value: print(f"Counter: {value}"))

# Изменение значения -> автоматическое уведомление
counter.value = 1  # Выведет: Counter: 1
counter.value = 2  # Выведет: Counter: 2

# Отписка
unsubscribe()
counter.value = 3  # Ничего не выведет
```

### 3.4 Миграция обработчиков событий

#### Старый подход (прямые вызовы)

```python
# handlers/filesystem.py
async def handle_filesystem_event(event):
    print(f"File changed: {event.path}")

# handlers/permissions.py
async def handle_permission_request(event):
    print(f"Permission needed: {event.type}")

# Где-то в коде TUI
from acp_client.handlers.filesystem import handle_filesystem_event
await handle_filesystem_event(event)
```

#### Новый подход (Event Bus)

```python
from acp_client.infrastructure.events.bus import EventBus
from acp_client.domain.events import FileSystemEvent, PermissionEvent

# В инициализации контейнера
container = DIBootstrapper.build(host="localhost", port=8000)
event_bus = container.resolve(EventBus)

# Подписка на события
event_bus.subscribe(FileSystemEvent, handle_filesystem_event)
event_bus.subscribe(PermissionEvent, handle_permission_request)

# Публикация события (происходит в Use Cases)
event_bus.publish(FileSystemEvent(path="/home/user/file.txt"))
```

#### Структура события

**Старый формат:**
```python
event = {
    "type": "filesystem",
    "data": {
        "path": "/home/user/file.txt",
        "action": "modified"
    }
}
```

**Новый формат (Domain Event):**
```python
from acp_client.domain.events import FileSystemEvent

event = FileSystemEvent(
    path="/home/user/file.txt",
    action="modified"
)
```

---

## Пошаговая миграция

### Шаг 1: Инициализация DI контейнера

Это первый и критический шаг. DIBootstrapper регистрирует все компоненты приложения.

```python
# main.py или __main__.py
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

async def main():
    # Создание контейнера
    container = DIBootstrapper.build(
        host="localhost",
        port=8000,
    )
    
    # Теперь можно использовать контейнер для получения компонентов
    # container.resolve(SomeUseCase)
```

**Что регистрируется:**
- EventBus - шина событий
- ACPTransportService - транспорт
- SessionRepository - хранилище сессий
- SessionCoordinator - оркестрация
- ViewModelFactory - создание ViewModels
- Все Use Cases

**Преимущества:**
- Централизованная конфигурация
- Легкий перейти на другой транспорт (TCP → WebSocket)
- Легко подменять имплементации для тестов

### Шаг 2: Замена прямых вызовов клиента на Use Cases

Все операции теперь через Use Cases. Это обеспечивает единый интерфейс.

**Было:**
```python
client = ACPClient("ws://localhost:8000")
await client.connect()
response = await client.send_request(...)
```

**Стало:**
```python
container = DIBootstrapper.build(host="localhost", port=8000)
use_case = container.resolve(SomeUseCase)
response = await use_case.execute(request)
```

**Какие Use Cases доступны:**
- `InitializeUseCase` - инициализация соединения
- `CreateSessionUseCase` - создание сессии
- `ListSessionsUseCase` - получение списка сессий
- `LoadSessionUseCase` - загрузка сессии
- `SendPromptUseCase` - отправка промпта
- `CancelSessionUseCase` - отмена операции

Полный список смотрите в [`acp_client/application/use_cases.py`](acp-client/src/acp_client/application/use_cases.py:1).

### Шаг 3: Добавление ViewModels для UI компонентов

ViewModels отделяют логику представления от логики бизнеса. Используйте Observable для реактивных обновлений.

**Было:**
```python
class MyWidget(Widget):
    def __init__(self):
        self.data = None
    
    async def load_data(self):
        self.data = await manager.get_data()
        self.refresh()
```

**Стало:**
```python
class MyWidget(Widget):
    def __init__(self, view_model: MyViewModel):
        self.view_model = view_model
        self.view_model.data.subscribe(self._on_data_changed)
    
    def _on_data_changed(self):
        self.refresh()
```

**Доступные ViewModels:**
- `ChatViewModel` - управление чатом
- `SessionViewModel` - управление сессиями
- `FileSystemViewModel` - управление файловой системой
- `PermissionViewModel` - управление разрешениями
- `TerminalViewModel` - управление терминалом
- `PlanViewModel` - управление планом

Смотрите [`acp_client/presentation/`](acp-client/src/acp_client/presentation/:1) для всех доступных ViewModels.

### Шаг 4: Использование Event Bus для событий

Event Bus обеспечивает слабую связанность между компонентами. Вместо прямых вызовов - публикация/подписка.

**Было:**
```python
await handle_event(event)
```

**Стало:**
```python
event_bus = container.resolve(EventBus)
event_bus.subscribe(FileSystemEvent, handle_event)

# Где-то в коде
event_bus.publish(FileSystemEvent(...))
```

**Доступные события:**
- `FileSystemEvent` - события файловой системы
- `PermissionEvent` - события разрешений
- `TerminalEvent` - события терминала
- `SessionEvent` - события сессий

Смотрите [`acp_client/domain/events.py`](acp-client/src/acp_client/domain/events.py:1) для всех событий.

---

## Примеры миграции

### Пример 1: Подключение к серверу и инициализация

**Старый код:**
```python
from acp_client.client import ACPClient

async def connect_to_server():
    client = ACPClient("ws://localhost:8000")
    await client.connect()
    
    response = await client.send_request({
        "method": "initialize",
        "params": {}
    })
    
    return response
```

**Новый код:**
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import InitializeUseCase

async def connect_to_server():
    container = DIBootstrapper.build(
        host="localhost",
        port=8000
    )
    
    initialize_use_case = container.resolve(InitializeUseCase)
    response = await initialize_use_case.execute()
    
    return response
```

**Преимущества:**
- Use Case инкапсулирует всю логику подключения
- DI контейнер управляет зависимостями
- Легко добавить логирование/мониторинг
- Легко тестировать (подменить TransportService)

### Пример 2: Создание и работа с сессией

**Старый код:**
```python
from acp_client.client import ACPClient
from acp_client.helpers.session import create_session

async def work_with_session():
    client = ACPClient("ws://localhost:8000")
    await client.connect()
    
    # Создание сессии
    session_id = await create_session(client, "Test Session")
    
    # Отправка промпта
    response = await client.send_request({
        "method": "session/prompt",
        "params": {
            "session_id": session_id,
            "prompt": "Hello, how are you?"
        }
    })
    
    return response
```

**Новый код:**
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import (
    CreateSessionUseCase,
    SendPromptUseCase
)
from acp_client.application.dto import (
    CreateSessionRequest,
    SendPromptRequest
)

async def work_with_session():
    container = DIBootstrapper.build(
        host="localhost",
        port=8000
    )
    
    # Инициализация (обязательно перед созданием сессии)
    init_use_case = container.resolve(InitializeUseCase)
    await init_use_case.execute()
    
    # Создание сессии
    create_session_use_case = container.resolve(CreateSessionUseCase)
    session = await create_session_use_case.execute(
        CreateSessionRequest(name="Test Session")
    )
    
    # Отправка промпта
    send_prompt_use_case = container.resolve(SendPromptUseCase)
    response = await send_prompt_use_case.execute(
        SendPromptRequest(
            session_id=session.id,
            prompt="Hello, how are you?"
        )
    )
    
    return response
```

**Ключевые отличия:**
- Структурированные DTOs вместо dict
- Use Cases для каждой операции
- DI контейнер управляет всем
- Явная обработка ошибок через исключения

### Пример 3: UI компонент с MVVM и Observable

**Старый код (MVC-style):**
```python
from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from acp_client.tui.managers.session import SessionManager

class SessionListView(Static):
    def __init__(self):
        super().__init__()
        self.sessions = []
        self.manager = SessionManager()
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="sessions")
    
    async def on_mount(self):
        await self.refresh_sessions()
    
    async def refresh_sessions(self):
        self.sessions = await self.manager.get_sessions()
        self._render_sessions()
    
    def _render_sessions(self):
        log = self.query_one("#sessions", RichLog)
        log.clear()
        for session in self.sessions:
            log.write(f"[blue]{session['name']}[/blue]")
```

**Новый код (MVVM with Observable):**
```python
from textual.widgets import Static, RichLog
from textual.app import ComposeResult
from acp_client.presentation.session_view_model import SessionViewModel
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

class SessionListView(Static):
    def __init__(self, view_model: SessionViewModel):
        super().__init__()
        self.view_model = view_model
        
        # Автоматическое обновление при изменении Observable
        self.view_model.sessions.subscribe(self._on_sessions_changed)
        self.view_model.is_loading.subscribe(self._on_loading_changed)
    
    def compose(self) -> ComposeResult:
        yield RichLog(id="sessions")
    
    async def on_mount(self):
        # ViewModel сам загружает данные при необходимости
        await self.view_model.load_sessions()
    
    def _on_sessions_changed(self):
        """Вызывается автоматически при изменении sessions"""
        self._render_sessions()
    
    def _on_loading_changed(self):
        """Вызывается автоматически при изменении is_loading"""
        pass  # Можно показать/скрыть loading indicator
    
    def _render_sessions(self):
        log = self.query_one("#sessions", RichLog)
        log.clear()
        
        if self.view_model.is_loading.value:
            log.write("Loading...")
            return
        
        for session in self.view_model.sessions.value:
            log.write(f"[blue]{session.name}[/blue]")

# В main.py
async def main():
    container = DIBootstrapper.build(host="localhost", port=8000)
    view_model = container.resolve(SessionViewModel)
    view = SessionListView(view_model)
```

**Преимущества MVVM:**
- UI компонент не знает о транспорте
- ViewModel содержит всю логику обновления
- Observable обеспечивает реактивность
- Легко тестировать (подменить ViewModel в тесте)

### Пример 4: Обработка событий через Event Bus

**Старый код (прямые вызовы):**
```python
# handlers/permissions.py
async def handle_permission_request(event_data):
    print(f"Permission requested: {event_data['type']}")
    # Обновить UI напрямую
    await show_permission_dialog(event_data)

# В тесте или основном коде
from acp_client.handlers.permissions import handle_permission_request
await handle_permission_request({"type": "read_file"})
```

**Новый код (Event Bus):**
```python
from acp_client.infrastructure.events.bus import EventBus
from acp_client.domain.events import PermissionRequestEvent

# Регистрация обработчика (в инициализации)
container = DIBootstrapper.build(host="localhost", port=8000)
event_bus = container.resolve(EventBus)

async def handle_permission_request(event: PermissionRequestEvent):
    print(f"Permission requested: {event.permission_type}")
    await show_permission_dialog(event)

event_bus.subscribe(PermissionRequestEvent, handle_permission_request)

# Публикация события (в Use Case или другом месте)
event_bus.publish(PermissionRequestEvent(
    permission_type="read_file",
    resource="/path/to/file"
))
```

**Преимущества Event Bus:**
- Слабая связанность (publisher не знает subscribers)
- Легко добавлять новых слушателей
- Централизованное управление событиями
- Асинхронная обработка событий

### Пример 5: Интеграция в существующее приложение

**Старый код (встроенный клиент):**
```python
class MyApp:
    def __init__(self):
        self.acp_client = ACPClient("ws://localhost:8000")
    
    async def connect(self):
        await self.acp_client.connect()
    
    async def send_message(self, msg):
        response = await self.acp_client.send_request({
            "method": "session/prompt",
            "params": {"prompt": msg}
        })
        return response
```

**Новый код (с DI контейнером):**
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import SendPromptUseCase
from acp_client.application.dto import SendPromptRequest

class MyApp:
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.container = DIBootstrapper.build(host=host, port=port)
        self._session_id = None
    
    async def initialize(self):
        """Инициализация соединения"""
        from acp_client.application.use_cases import InitializeUseCase
        init_use_case = self.container.resolve(InitializeUseCase)
        await init_use_case.execute()
    
    async def create_session(self, name: str):
        """Создание сессии"""
        from acp_client.application.use_cases import CreateSessionUseCase
        from acp_client.application.dto import CreateSessionRequest
        
        create_use_case = self.container.resolve(CreateSessionUseCase)
        session = await create_use_case.execute(
            CreateSessionRequest(name=name)
        )
        self._session_id = session.id
        return session
    
    async def send_message(self, msg: str):
        """Отправка сообщения в текущую сессию"""
        if not self._session_id:
            raise RuntimeError("No active session")
        
        send_use_case = self.container.resolve(SendPromptUseCase)
        response = await send_use_case.execute(
            SendPromptRequest(
                session_id=self._session_id,
                prompt=msg
            )
        )
        return response

# Использование
async def main():
    app = MyApp(host="localhost", port=8000)
    
    await app.initialize()
    session = await app.create_session("My Chat")
    
    response = await app.send_message("Hello, AI!")
    print(response)
```

**Преимущества такого подхода:**
- Контейнер управляет всеми зависимостями
- Легко менять host/port без изменения кода
- Для тестов можно подставить mock контейнер
- Четкий интерфейс приложения

---

## Совместимость

### Что осталось без изменений

✅ **Протокол ACP** (`messages.py`)
- Сообщения и формат остаются совместимы
- Используется та же сериализация JSON
- Методы протокола не изменились

✅ **CLI интерфейс** (`cli.py`)
- Команды остаются те же
- Интеграция с новой архитектурой
- Обратная совместимость сохранена

✅ **Базовые типы**
- Типы сессий
- Типы сообщений
- Типы событий

### Что deprecated (будет удалено)

⚠️ **Модули (будут удалены в следующем major릴ease):**
- `client.py` - используйте Use Cases
- `helpers/auth.py` - используйте Use Cases
- `helpers/session.py` - используйте Use Cases
- `tui/managers/` - используйте ViewModels и NavigationManager
- `handlers/` - используйте Event Bus

**Миграция к Use Cases:**
```python
# Было
from acp_client.helpers.session import create_session
session_id = await create_session(client, name)

# Стало
from acp_client.application.use_cases import CreateSessionUseCase
use_case = container.resolve(CreateSessionUseCase)
session = await use_case.execute(CreateSessionRequest(name=name))
```

### Что удалено полностью

❌ **Старые менеджеры:**
- `ConnectionManager` → `InitializeUseCase` + `ACPTransportService`
- `SessionManager` → `CreateSessionUseCase` + `SessionViewModel`
- `FilesystemManager` → `FileSystemViewModel` + Event Bus
- `PermissionManager` → `PermissionViewModel` + Event Bus
- `TerminalManager` → `TerminalViewModel` + Event Bus

### Матрица совместимости

| Компонент | Версия 3.x | Версия 4.0 | Версия 4.1+ | Примечание |
|-----------|-----------|-----------|------------|-----------|
| `client.py` | ✅ Active | ⚠️ Deprecated | ❌ Removed | Используйте Use Cases |
| `helpers/` | ✅ Active | ⚠️ Deprecated | ❌ Removed | Используйте Use Cases |
| `tui/managers/` | ✅ Active | ⚠️ Deprecated | ❌ Removed | Используйте ViewModels |
| `messages.py` | ✅ Active | ✅ Active | ✅ Active | Совместим |
| `cli.py` | ✅ Active | ✅ Active | ✅ Active | Обновлен, совместим |
| Use Cases | ❌ Missing | ✅ New | ✅ Active | Новая архитектура |
| ViewModels | ❌ Missing | ✅ New | ✅ Active | Новая архитектура |
| DI Container | ❌ Missing | ✅ New | ✅ Active | Управление зависимостями |

---

## Checklist миграции

Используйте этот checklist для отслеживания прогресса миграции вашего кода.

### Подготовка

- [ ] Прочитать документацию [`ARCHITECTURE-LAYERS.md`](acp-client/ARCHITECTURE-LAYERS.md)
- [ ] Прочитать документацию [`DEVELOPING.md`](acp-client/DEVELOPING.md)
- [ ] Прочитать документацию [`TESTING-STRATEGY.md`](acp-client/TESTING-STRATEGY.md)
- [ ] Просмотреть примеры в `acp-client/tests/`
- [ ] Создать ветку для миграции

### Фаза 1: Инфраструктура

- [ ] Заменить инициализацию клиента на `DIBootstrapper.build()`
- [ ] Добавить конфигурацию (хост, порт, логирование)
- [ ] Проверить, что контейнер инициализируется без ошибок
- [ ] Добавить логирование операций

### Фаза 2: Основные операции

- [ ] Заменить `client.connect()` на `InitializeUseCase`
- [ ] Заменить `client.send_request()` на Use Cases
- [ ] Заменить `helpers.session` на `CreateSessionUseCase` и др.
- [ ] Заменить `helpers.auth` на `InitializeUseCase` + аутентификацию
- [ ] Проверить все Use Cases

### Фаза 3: UI компоненты

- [ ] Добавить ViewModels для каждого компонента
- [ ] Заменить직접 доступ к данным на `view_model.property.value`
- [ ] Добавить подписку на Observable: `subscribe(callback)`
- [ ] Убрать явные `refresh()` где это возможно
- [ ] Протестировать UI обновления

### Фаза 4: События

- [ ] Заменить прямые вызовы обработчиков на Event Bus
- [ ] Зарегистрировать обработчики через `event_bus.subscribe()`
- [ ] Заменить вызовы `handle_event()` на `event_bus.publish()`
- [ ] Проверить, что события доходят до слушателей

### Фаза 5: Тестирование

- [ ] Написать unit тесты для Use Cases (использовать моки)
- [ ] Написать MVVM тесты для ViewModels
- [ ] Написать интеграционные тесты (реальный контейнер)
- [ ] Проверить coverage тестами
- [ ] Запустить `make check` из корня репозитория

### Фаза 6: Очистка

- [ ] Удалить неиспользуемый код из `helpers/`
- [ ] Удалить неиспользуемые менеджеры
- [ ] Удалить неиспользуемые обработчики
- [ ] Обновить импорты (удалить старые)
- [ ] Обновить документацию проекта

### Финализация

- [ ] Проверить все коммиты (одна функция = один коммит)
- [ ] Создать Pull Request с описанием изменений
- [ ] Убедиться, что все тесты проходят
- [ ] Получить review от команды
- [ ] Мерж в main ветку

---

## Troubleshooting

### Ошибка: "Cannot resolve dependency"

**Симптомы:**
```
RuntimeError: Cannot resolve SomeUseCase: dependency TransportService not found
```

**Причины:**
- Зависимость не зарегистрирована в DIContainer
- Контейнер не инициализирован правильно

**Решение:**
```python
# Неправильно
container = DIContainer()
use_case = container.resolve(SomeUseCase)  # ❌ Ошибка

# Правильно
container = DIBootstrapper.build(host="localhost", port=8000)  # ✅
use_case = container.resolve(SomeUseCase)
```

**Проверка:**
- Убедитесь, что используете `DIBootstrapper.build()` вместо `DIContainer()`
- Проверьте, что все зависимости зарегистрированы в `DIBootstrapper`

### Ошибка: "Observable не обновляется"

**Симптомы:**
```python
view_model.data.value = new_value  # Меняем значение
# Но _on_data_changed() не вызывается
```

**Причины:**
- Забыли подписаться на Observable
- Не подписались правильно

**Решение:**
```python
# Неправильно
class MyWidget:
    def __init__(self, view_model):
        self.view_model = view_model
        # ❌ Забыли subscribe!

# Правильно
class MyWidget:
    def __init__(self, view_model):
        self.view_model = view_model
        # ✅ Подписываемся на изменения
        self.view_model.data.subscribe(self._on_data_changed)
    
    def _on_data_changed(self):
        self.refresh()
```

**Проверка:**
- Убедитесь, что вызвали `subscribe()` в `__init__`
- Проверьте, что callback правильно определен

### Ошибка: "Use Case не выполняется"

**Симптомы:**
```python
result = await use_case.execute(request)  # Зависает или ошибка
```

**Причины:**
- Забыли инициализировать соединение
- Неправильный формат request
- Сервер не запущен

**Решение:**
```python
# Инициализируем контейнер
container = DIBootstrapper.build(host="localhost", port=8000)

# Инициализируем соединение ПЕРЕД использованием сессий
init_use_case = container.resolve(InitializeUseCase)
await init_use_case.execute()

# Теперь можно использовать другие Use Cases
create_use_case = container.resolve(CreateSessionUseCase)
result = await create_use_case.execute(request)
```

**Проверка:**
- Убедитесь, что вызвали `InitializeUseCase` перед операциями с сессией
- Проверьте, что сервер запущен и доступен
- Проверьте, что request имеет правильный формат (используйте DTOs)

### Ошибка: "Тесты падают после миграции"

**Симптомы:**
```
FAILED test_my_feature.py - RuntimeError: Cannot resolve dependency
```

**Причины:**
- Старые тесты используют старый API
- Тесты используют реальный контейнер вместо моков

**Решение:**
```python
# Было (старый тест)
def test_create_session():
    client = ACPClient("ws://localhost:8000")
    session_id = await create_session(client, "Test")
    assert session_id

# Стало (новый тест с моками)
@pytest.mark.asyncio
async def test_create_session(mock_transport_service):
    # Используем DIBootstrapper с мокированным TransportService
    container = DIBootstrapper.build(host="localhost", port=8000)
    
    # Подменяем реальный сервис на мок
    mock_transport = AsyncMock()
    mock_transport.send.return_value = {...}
    mock_transport.receive.return_value = {...}
    
    # Или используйте fixture из conftest.py
    use_case = container.resolve(CreateSessionUseCase)
    
    # Проверяем результат
    result = await use_case.execute(CreateSessionRequest(name="Test"))
    assert result.session_id
```

**Проверка:**
- Используйте fixtures из `conftest.py`
- Создавайте моки через `unittest.mock.AsyncMock`
- Проверьте примеры в `tests/`

### Ошибка: "EventBus не публикует события"

**Симптомы:**
```python
event_bus.publish(MyEvent(...))  # Событие не доходит до подписчиков
```

**Причины:**
- Обработчик не зарегистрирован перед публикацией
- Неправильный тип события

**Решение:**
```python
# Неправильно
event_bus.publish(MyEvent(...))
event_bus.subscribe(MyEvent, handle_event)  # ❌ Подписали ПОСЛЕ

# Правильно
event_bus.subscribe(MyEvent, handle_event)  # ✅ Подписали ПЕРЕД
event_bus.publish(MyEvent(...))
```

**Проверка:**
- Убедитесь, что подписались ДО публикации события
- Убедитесь, что используете правильный тип события
- Проверьте, что обработчик асинхронный (если требуется)

### Ошибка: "DI контейнер не освобождает ресурсы"

**Симптомы:**
```python
container = DIBootstrapper.build(...)
# ... использование ...
# ❌ Контейнер не очищает ресурсы (WebSocket остается открытым)
```

**Решение:**
```python
# Используйте context manager
async with DIBootstrapper.build(host="localhost", port=8000) as container:
    use_case = container.resolve(SomeUseCase)
    await use_case.execute(...)
# ✅ Ресурсы автоматически освобождены

# Или явный cleanup
container = DIBootstrapper.build(host="localhost", port=8000)
try:
    # использование
    pass
finally:
    container.dispose()  # ✅ Очистка ресурсов
```

**Проверка:**
- Используйте `async with` для контейнера
- Или вызывайте `dispose()` явно
- Проверьте, что WebSocket закрыт (в логах)

### Ошибка: "Импорты из старых модулей"

**Симптомы:**
```python
from acp_client.client import ACPClient  # ❌ Модуль удален
from acp_client.helpers.session import create_session  # ❌ Модуль удален
```

**Решение:**
```python
# Было
from acp_client.client import ACPClient
from acp_client.helpers.session import create_session

# Стало
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import (
    InitializeUseCase,
    CreateSessionUseCase,
)
```

**Проверка:**
- Используйте IDE для поиска неиспользуемых импортов
- Запустите `ruff check` для проверки импортов
- Обновите импорты в соответствии с новой архитектурой

### Ошибка: "Type checking ошибки"

**Симптомы:**
```
error: Argument 1 to "execute" has incompatible type "dict"; expected "CreateSessionRequest"
```

**Причины:**
- Использование dict вместо DTO
- Неправильный тип параметра

**Решение:**
```python
# Неправильно (старый стиль)
result = await use_case.execute({  # ❌ dict
    "name": "Test"
})

# Правильно (новый стиль)
from acp_client.application.dto import CreateSessionRequest

result = await use_case.execute(  # ✅ DTO
    CreateSessionRequest(name="Test")
)
```

**Проверка:**
- Используйте IDE для автодополнения (Ctrl+Space)
- Запустите `ty check` из корня репозитория
- Проверьте типы параметров в docstring Use Case

---

## Дополнительные ресурсы

### Документация проекта

- [`acp-client/ARCHITECTURE-LAYERS.md`](acp-client/ARCHITECTURE-LAYERS.md) - полное описание архитектуры и 5 слоев
- [`acp-client/DEVELOPING.md`](acp-client/DEVELOPING.md) - руководство разработчика (настройка, запуск, отладка)
- [`acp-client/TESTING-STRATEGY.md`](acp-client/TESTING-STRATEGY.md) - стратегия тестирования (unit, integration, MVVM)
- [`acp-client/DI_IMPROVEMENTS.md`](acp-client/DI_IMPROVEMENTS.md) - улучшения DI контейнера

### Исходный код

**Application Layer:**
- [`acp-client/src/acp_client/application/use_cases.py`](acp-client/src/acp_client/application/use_cases.py:1) - все Use Cases
- [`acp-client/src/acp_client/application/dto.py`](acp-client/src/acp_client/application/dto.py:1) - Data Transfer Objects

**Presentation Layer:**
- [`acp-client/src/acp_client/presentation/observable.py`](acp-client/src/acp_client/presentation/observable.py:1) - Observable pattern
- [`acp-client/src/acp_client/presentation/`](acp-client/src/acp_client/presentation/:1) - все ViewModels

**Infrastructure Layer:**
- [`acp-client/src/acp_client/infrastructure/di_bootstrapper.py`](acp-client/src/acp_client/infrastructure/di_bootstrapper.py:1) - DI конфигурация
- [`acp-client/src/acp_client/infrastructure/di_container.py`](acp-client/src/acp_client/infrastructure/di_container.py:1) - DI контейнер
- [`acp-client/src/acp_client/infrastructure/events/bus.py`](acp-client/src/acp_client/infrastructure/events/bus.py:1) - Event Bus

**Domain Layer:**
- [`acp-client/src/acp_client/domain/entities.py`](acp-client/src/acp_client/domain/entities.py:1) - Domain entities
- [`acp-client/src/acp_client/domain/events.py`](acp-client/src/acp_client/domain/events.py:1) - Domain events

**Tests:**
- [`acp-client/tests/`](acp-client/tests/) - примеры тестов (unit, integration, MVVM)
- [`acp-client/tests/conftest.py`](acp-client/tests/conftest.py:1) - fixtures для тестов

### Отчеты о рефакторинге

- [`doc/PHASE_4_PART9_COMPLETION_REPORT.md`](doc/PHASE_4_PART9_COMPLETION_REPORT.md) - отчет о завершении рефакторинга

### Протокол ACP

- [`doc/ACP/`](doc/ACP/) - спецификация ACP протокола

### Полезные команды

```bash
# Проверка кода
make check

# Или локальная проверка (из acp-client)
uv run --directory acp-client ruff check .
uv run --directory acp-client ty check
uv run --directory acp-client python -m pytest

# Запуск конкретного теста
uv run --directory acp-client python -m pytest tests/test_di_bootstrapper.py -v

# Запуск TUI (для ручного тестирования)
uv run --directory acp-client acp-client-tui --host localhost --port 8000
```

### Best Practices

1. **Используйте DIBootstrapper** вместо прямого создания зависимостей
2. **Используйте Use Cases** для всех бизнес-операций
3. **Используйте ViewModels** для управления состоянием UI
4. **Используйте Observable** для реактивных обновлений
5. **Используйте Event Bus** для слабой связанности
6. **Тестируйте через DI контейнер** с моками
7. **Следуйте Dependency Rule**: зависимости только внутрь

---

## Заключение

Миграция на новую архитектуру требует времени и внимания, но результат стоит того:

✅ **Более чистый и понятный код**
✅ **Легче писать тесты**
✅ **Легче добавлять новые функции**
✅ **Лучше разделение ответственности**
✅ **Более надежное приложение**

Если у вас есть вопросы или возникли проблемы, обратитесь к документации или посмотрите примеры в `tests/`.

**Удачи с миграцией! 🚀**
