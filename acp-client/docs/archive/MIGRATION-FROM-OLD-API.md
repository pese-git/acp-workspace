# Руководство по миграции с Legacy API на Clean Architecture

## Содержание

1. [Введение](#введение)
2. [Что изменилось](#что-изменилось)
3. [Таблица изменений API](#таблица-изменений-api)
4. [Примеры миграции](#примеры-миграции)
5. [Пошаговая инструкция](#пошаговая-инструкция)
6. [Checklist миграции](#checklist-миграции)
7. [Troubleshooting](#troubleshooting)
8. [Ресурсы](#ресурсы)

## Введение

### Что произошло

В проекте `acp-client` произошла большая реорганизация кода с целью улучшить архитектуру, тестируемость и масштабируемость. Была реализована Clean Architecture с пятью слоями, что потребовало существенных изменений в API и способе взаимодействия компонентов.

### Для кого это руководство

Это руководство предназначено для разработчиков, которые:
- Работали с **старой версией** acp-client
- Хотят обновить свой код на новую архитектуру
- Нужно интегрировать **внешние компоненты** с новым API
- Нужно понять как работает миграция

### Ключевые сроки

- **Legacy API**: Больше не поддерживается (deprecated)
- **Переход**: Все компоненты должны быть перенесены
- **Deadline**: Конец Q4 2024

---

## Что изменилось

### Проблемы старой архитектуры

Старая архитектура была простой но имела недостатки:

1. **Тесная связанность** — компоненты зависели друг от друга напрямую
2. **Сложно тестировать** — нужны реальные объекты вместо моков
3. **Дублирование логики** — одна логика в разных местах
4. **Сложно расширять** — добавление функции требует изменения многих файлов
5. **Проблемы состояния** — состояние хранилось в разных местах

### Преимущества новой архитектуры

Новая Clean Architecture решает эти проблемы:

1. **Слабая связанность** — слои независимы друг от друга
2. **Легко тестировать** — каждый слой тестируется отдельно
3. **DRY** — логика в одном месте (Use Cases)
4. **Легко расширять** — новая функция = новый Use Case
5. **Явное состояние** — Observable в Presentation слое

---

## Что изменилось на высоком уровне

Новая архитектура имеет 5 слоёв:

```
┌─────────────────────────────────┐
│  TUI Layer (тu/components/)     │  ← Пользовательский интерфейс
├─────────────────────────────────┤
│  Presentation Layer             │  ← Observable, ViewModels
│  (presentation/...)             │
├─────────────────────────────────┤
│  Application Layer              │  ← Use Cases, State Machine
│  (application/...)              │
├─────────────────────────────────┤
│  Infrastructure Layer           │  ← DI, Transport, Repositories
│  (infrastructure/...)           │
├─────────────────────────────────┤
│  Domain Layer                   │  ← Entities, Services, Events
│  (domain/...)                   │
└─────────────────────────────────┘
```

Данные текут от TUI → Presentation → Application → Infrastructure → Domain и обратно.

---

## Таблица изменений API

### Архитектура: До и После

**БЫЛО (старая)**:
```python
# client.py — монолитный класс с всей логикой
class ACPClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.session = None
        self.messages = []
    
    async def send_prompt(self, text):
        # логика тут
        pass
```

**СТАЛО (новая)**:
```python
# Domain слой: интерфейсы
class TransportService(ABC):
    async def send_message(self, msg): pass

# Infrastructure слой: реализация
class WebSocketTransport(TransportService):
    async def send_message(self, msg): pass

# Application слой: бизнес-логика
class SendPromptUseCase(UseCase):
    def __init__(self, transport: TransportService):
        self.transport = transport
    
    async def execute(self, text: str):
        # логика тут
        pass

# Presentation слой: состояние для UI
class ChatViewModel(BaseViewModel):
    def __init__(self, use_case: SendPromptUseCase):
        self.use_case = use_case
    
    async def send_prompt(self, text):
        await self.use_case.execute(text)
```

---

### Таблица изменений API

#### 1. Вызов функционала

**БЫЛО**:
```python
# main.py
client = ACPClient("localhost", 8000)
session = client.load_session("session-id")
response = client.send_prompt("hello")
```

**СТАЛО**:
```python
# main.py
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

async with DIBootstrapper() as bootstrapper:
    # Разрешить Use Cases
    load_session_use_case = bootstrapper.resolve(LoadSessionUseCase)
    send_prompt_use_case = bootstrapper.resolve(SendPromptUseCase)
    
    # Использовать
    session = await load_session_use_case.execute(LoadSessionRequest("session-id"))
    response = await send_prompt_use_case.execute(SendPromptRequest("hello"))
```

#### 2. Управление состоянием UI

**БЫЛО**:
```python
# В каком-то обработчике события
class ChatView:
    def __init__(self, client: ACPClient):
        self.client = client
        self.messages = []
    
    def on_message(self, data):
        self.messages.append(data)  # Изменяем состояние напрямую
        self.render()  # Вручную перерисовываем
```

**СТАЛО**:
```python
# Presentation слой
class ChatViewModel(BaseViewModel):
    def __init__(self, use_case: SendPromptUseCase):
        self.messages: Observable[list] = Observable([])
    
    async def send_prompt(self, text):
        response = await self.use_case.execute(text)
        self.messages.set(self.messages.get() + [response])
        # Автоматически уведомляет подписчиков

# TUI слой
class ChatView(Static):
    def __init__(self, view_model: ChatViewModel):
        self.view_model = view_model
        # Подписаться на изменения
        self.view_model.messages.subscribe(self.on_messages_changed)
    
    def on_messages_changed(self, new_messages):
        self.render(new_messages)  # Автоматически перерисовывается
```

#### 3. Обработка событий

**БЫЛО** (handlers/filesystem.py):
```python
# Было
class FileHandler:
    def __init__(self, client: ACPClient):
        self.client = client
    
    def handle_file_changed(self, path):
        # Обработка события
        self.client.update_file_tree(path)
```

**СТАЛО** (В инициализации):
```python
# Новый подход
from acp_client.infrastructure.events.bus import EventBus

event_bus = EventBus()

# Подписаться на событие
async def on_file_changed(event: FileChangedEvent):
    # Обработка события
    file_tree_vm.update(event.path)

event_bus.subscribe(FileChangedEvent, on_file_changed)
```

---

## Примеры миграции

### Старый подход

```python
# Было (в тесте или основном коде)
client = ACPClient("localhost", 8000)
await client.connect()

# Отправка запроса
response = await client.send_prompt("analyze code")
print(response)
```

### Новый подход

```python
# Стало
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.dto import SendPromptRequest

async with DIBootstrapper() as bootstrapper:
    # Выполнение
    send_prompt_use_case = bootstrapper.resolve(SendPromptUseCase)
    request = SendPromptRequest(text="analyze code")
    response = await send_prompt_use_case.execute(request)
    print(response)
```

---

### Что происходит за кулисами

1. **DIBootstrapper** регистрирует все зависимости
2. **resolve()** создаёт граф зависимостей
3. **Use Case** выполняет бизнес-логику
4. **Response DTO** возвращает результат
5. **Observable** уведомляет об изменениях

---

## Пошаговая инструкция

### Старый подход (MVC/прямой доступ к данным)

```python
class SessionManager:
    def __init__(self, client: ACPClient):
        self.client = client
    
    async def create_session(self, name):
        # Логика смешана с infrastructure
        ws = await self.client.connect()
        response = await ws.send({
            "jsonrpc": "2.0",
            "method": "session/new",
            "params": {"name": name}
        })
        return response["result"]
```

### Новый подход (MVVM с Observable)

```python
class CreateSessionUseCase(UseCase):
    def __init__(self, transport: TransportService, repo: SessionRepository):
        self.transport = transport
        self.repo = repo
    
    async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
        # 1. Domain logic
        session = Session(name=request.name)
        
        # 2. Сохранить в repo
        await self.repo.save(session)
        
        # 3. Отправить на сервер
        server_response = await self.transport.send_message({
            "method": "session/new",
            "params": {"name": request.name}
        })
        
        # 4. Вернуть response DTO
        return CreateSessionResponse(
            session_id=server_response["id"],
            name=request.name
        )

class SessionViewModel(BaseViewModel):
    def __init__(self, use_case: CreateSessionUseCase):
        self.use_case = use_case
        self.sessions: Observable[list] = Observable([])
    
    async def create_session(self, name):
        request = CreateSessionRequest(name=name)
        response = await self.use_case.execute(request)
        # Observable автоматически уведомляет подписчиков
        self.sessions.set(self.sessions.get() + [response])
```

### ViewModel (Business Logic)

ViewModels содержат бизнес-логику для UI:

```python
class ChatViewModel(BaseViewModel):
    def __init__(self, send_prompt_use_case: SendPromptUseCase):
        super().__init__()
        self.use_case = send_prompt_use_case
        
        # Состояние для UI
        self.messages: Observable[list] = Observable([])
        self.is_loading: Observable[bool] = Observable(False)
        self.error: Observable[str] = Observable("")
    
    async def send_prompt(self, text: str) -> None:
        """Отправить промпт на сервер"""
        self.is_loading.set(True)
        self.error.set("")
        
        try:
            request = SendPromptRequest(text=text)
            response = await self.use_case.execute(request)
            
            # Обновить состояние
            messages = self.messages.get()
            messages.append(response)
            self.messages.set(messages)
        except Exception as e:
            self.error.set(str(e))
        finally:
            self.is_loading.set(False)
```

### Observable Pattern

Что это и как использовать:

```python
# Создать observable
messages = Observable([])

# Подписаться на изменения
def on_messages_changed(new_value):
    print(f"Messages changed: {new_value}")

messages.subscribe(on_messages_changed)

# Изменить значение -> автоматическое уведомление
messages.set([...])  # on_messages_changed будет вызвана

# Отписка
messages.unsubscribe(on_messages_changed)
```

---

## Пошаговая инструкция по миграции

### Шаг 1: Инициализация DI контейнера

**Было** (main.py или __main__.py):
```python
# Было
client = ACPClient("localhost", 8000)
app = ChatApplication(client)
```

**Стало**:
```python
# Стало
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

async def main():
    async with DIBootstrapper() as bootstrapper:
        # Контейнер готов
        # Используй resolve() для получения Use Cases
        pass

if __name__ == "__main__":
    asyncio.run(main())
```

### Шаг 2: Замена прямых вызовов клиента на Use Cases

**Было**:
```python
# handlers/filesystem.py
class FileHandler:
    def __init__(self, client: ACPClient):
        self.client = client
    
    async def load_files(self, session_id):
        response = await self.client.request({
            "method": "fs/list",
            "params": {"path": "/"}
        })
        return response["files"]
```

**Стало**:
```python
# application/use_cases.py
class ListFilesUseCase(UseCase):
    def __init__(self, transport: TransportService):
        self.transport = transport
    
    async def execute(self, request: ListFilesRequest) -> ListFilesResponse:
        response = await self.transport.send_message({
            "method": "fs/list",
            "params": {"path": request.path}
        })
        return ListFilesResponse(files=response["files"])

# handlers/filesystem.py (просто вызывает Use Case)
class FileHandler:
    def __init__(self, use_case: ListFilesUseCase):
        self.use_case = use_case
    
    async def load_files(self, session_id):
        request = ListFilesRequest(path="/")
        response = await self.use_case.execute(request)
        return response.files
```

### Шаг 3: Добавление ViewModels для UI компонентов

**Было**:
```python
# tui/components/chat_view.py
class ChatView(Static):
    def __init__(self, client: ACPClient):
        super().__init__()
        self.client = client
        self.messages = []
    
    async def send_message(self, text):
        response = await self.client.send_prompt(text)
        self.messages.append(response)
        self.render()
```

**Стало**:
```python
# presentation/chat_view_model.py
class ChatViewModel(BaseViewModel):
    def __init__(self, use_case: SendPromptUseCase):
        super().__init__()
        self.messages: Observable[list] = Observable([])
    
    async def send_prompt(self, text):
        response = await self.use_case.execute(SendPromptRequest(text))
        self.messages.set(self.messages.get() + [response])

# tui/components/chat_view.py
class ChatView(Static):
    def __init__(self, view_model: ChatViewModel):
        super().__init__()
        self.view_model = view_model
        # Подписаться на изменения
        self.view_model.messages.subscribe(self._on_messages_changed)
    
    async def send_message(self, text):
        await self.view_model.send_prompt(text)
    
    def _on_messages_changed(self, messages):
        self.render()
```

### Шаг 4: Использование Event Bus для событий

**Было** (handlers/permissions.py):
```python
# Было
class PermissionHandler:
    def __init__(self, client: ACPClient):
        self.client = client
        self.client.on_permission_request = self.handle_permission
    
    def handle_permission(self, request):
        # Обработка
        pass
```

**Стало** (В инициализации контейнера):
```python
# infrastructure/di_bootstrapper.py
from acp_client.infrastructure.events.bus import EventBus

# Подписка на события
async def on_permission_request(event: PermissionRequestEvent):
    # Обработка события
    perm_vm.request_permission(event.permission)

event_bus.subscribe(PermissionRequestEvent, on_permission_request)
```

### Структура события

```python
# domain/events.py
@dataclass
class PermissionRequestEvent(DomainEvent):
    permission: str
    details: dict
    
    # Изменение значения -> автоматическое уведомление
    def approve(self):
        self.is_approved = True

# Где-то в коде (handlers/permissions.py)
event_bus.publish(PermissionRequestEvent(
    permission="file_write",
    details={"path": "/home/user/file.txt"}
))
```

---

## Примеры реального кода

### Пример 1: Подключение к серверу и инициализация

**БЫЛО**:
```python
from acp_client.client import ACPClient

async def main():
    client = ACPClient(host="localhost", port=8000)
    
    # Подключение и инициализация
    await client.connect()
    await client.initialize()
    
    # Использование
    sessions = await client.list_sessions()
    print(sessions)
```

**СТАЛО**:
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import ListSessionsUseCase

async def main():
    # Инициализация DI контейнера
    async with DIBootstrapper() as bootstrapper:
        # Получить Use Case
        list_sessions_use_case = bootstrapper.resolve(ListSessionsUseCase)
        
        # Использовать
        sessions = await list_sessions_use_case.execute(ListSessionsRequest())
        print(sessions)
```

---

### Пример 2: Создание и работа с сессией

**БЫЛО**:
```python
# Было
client = ACPClient("localhost", 8000)
await client.connect()

# Создать сессию
session = await client.create_session("my-project")
print(f"Created: {session.id}")

# Загрузить сессию
loaded = await client.load_session(session.id)
print(f"Loaded: {loaded.name}")

# Отправить промпт
response = await client.send_prompt("analyze code")
print(f"Response: {response.text}")
```

**СТАЛО**:
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.application.use_cases import (
    CreateSessionUseCase,
    LoadSessionUseCase,
    SendPromptUseCase
)

async def main():
    async with DIBootstrapper() as bootstrapper:
        # Разрешить Use Cases
        create_uc = bootstrapper.resolve(CreateSessionUseCase)
        load_uc = bootstrapper.resolve(LoadSessionUseCase)
        send_uc = bootstrapper.resolve(SendPromptUseCase)
        
        # Создать сессию
        create_resp = await create_uc.execute(CreateSessionRequest(name="my-project"))
        print(f"Created: {create_resp.session_id}")
        
        # Загрузить сессию
        load_resp = await load_uc.execute(LoadSessionRequest(session_id=create_resp.session_id))
        print(f"Loaded: {load_resp.name}")
        
        # Отправить промпт
        send_resp = await send_uc.execute(SendPromptRequest(text="analyze code"))
        print(f"Response: {send_resp.text}")
```

---

### Пример 3: UI компонент с MVVM и Observable

**БЫЛО**:
```python
# tui/app.py
from textual.app import ComposeResult
from textual.containers import Container
from acp_client.client import ACPClient

class ChatApp(Container):
    def __init__(self):
        super().__init__()
        self.client = ACPClient("localhost", 8000)
        self.messages = []
    
    async def on_mount(self) -> None:
        await self.client.connect()
    
    async def send_message(self, text: str) -> None:
        response = await self.client.send_prompt(text)
        self.messages.append(response)
        self.update_display()
    
    def update_display(self) -> None:
        # Вручную обновляем UI
        display = "\n".join(self.messages)
        self.query_one("#chat_display").update(display)
```

**СТАЛО** (в main.py):
```python
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper

async def main():
    async with DIBootstrapper() as bootstrapper:
        # Получить ViewModels
        chat_vm = bootstrapper.resolve(ChatViewModel)
        file_tree_vm = bootstrapper.resolve(FileTreeViewModel)
        
        # Создать TUI приложение с ViewModels
        app = ChatApp(
            chat_view_model=chat_vm,
            file_tree_view_model=file_tree_vm
        )
        await app.run()
```

```python
# tui/components/chat_view.py
from acp_client.presentation.chat_view_model import ChatViewModel

class ChatView(Static):
    def __init__(self, view_model: ChatViewModel):
        super().__init__()
        self.view_model = view_model
        
        # Подписаться на Observable
        self.view_model.messages.subscribe(self._on_messages_changed)
        self.view_model.is_loading.subscribe(self._on_loading_changed)
    
    def _on_messages_changed(self, messages: list) -> None:
        # Автоматически вызывается при изменении
        display = "\n".join(msg.text for msg in messages)
        self.query_one("#chat_display").update(display)
    
    def _on_loading_changed(self, is_loading: bool) -> None:
        if is_loading:
            self.query_one("#spinner").visible = True
        else:
            self.query_one("#spinner").visible = False
    
    async def send_message(self, text: str) -> None:
        # ViewModel обновляет Observable -> автоматический refresh
        await self.view_model.send_prompt(text)
```

---

### Пример 4: Обработка событий через Event Bus

**БЫЛО**:
```python
# handlers/permissions.py
class PermissionHandler:
    def __init__(self, client: ACPClient):
        self.client = client
        self.client.on_permission_request = self._on_permission
    
    def _on_permission(self, permission_data):
        # Обработка события
        show_modal(f"Permission: {permission_data['type']}")
```

**СТАЛО** (Регистрация обработчика в инициализации):
```python
# infrastructure/di_bootstrapper.py
async def setup_event_handlers(self, event_bus: EventBus):
    # Получить ViewModel для разрешений
    perm_vm = self.resolve(PermissionViewModel)
    
    # Подписаться на события
    async def on_permission_request(event: PermissionRequestEvent):
        await perm_vm.request_permission(event.permission, event.details)
    
    event_bus.subscribe(PermissionRequestEvent, on_permission_request)
```

```python
# Публикация события (в Use Case или другом месте)
# handlers/permissions.py
class HandlePermissionRequestUseCase(UseCase):
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def execute(self, request: PermissionRequest):
        # Публикуем событие
        event = PermissionRequestEvent(
            permission=request.type,
            details=request.details
        )
        await self.event_bus.publish(event)
```

---

### Пример 5: Интеграция в существующее приложение

Если вы уже используете TUI и хотите добавить новую функцию:

1. **Создать Use Case** (application/use_cases.py)
2. **Создать ViewModel** (presentation/view_model.py)
3. **Обновить DIBootstrapper** (infrastructure/di_bootstrapper.py)
4. **Добавить компонент TUI** (tui/components/my_component.py)

Пример: Добавить команду "Export session":

```python
# 1. Use Case
class ExportSessionUseCase(UseCase):
    def __init__(self, repo: SessionRepository):
        self.repo = repo
    
    async def execute(self, request: ExportSessionRequest) -> ExportSessionResponse:
        session = await self.repo.load(request.session_id)
        # Логика экспорта
        return ExportSessionResponse(filename="session.json")

# 2. ViewModel
class ExportViewModel(BaseViewModel):
    def __init__(self, use_case: ExportSessionUseCase):
        self.use_case = use_case
        self.is_exporting: Observable[bool] = Observable(False)
    
    async def export_session(self, session_id: str):
        self.is_exporting.set(True)
        try:
            response = await self.use_case.execute(ExportSessionRequest(session_id))
            return response.filename
        finally:
            self.is_exporting.set(False)

# 3. DIBootstrapper
# Уже регистрирует автоматически (если у вас есть автоматическая регистрация)

# Использование
async with DIBootstrapper() as bootstrapper:
    export_vm = bootstrapper.resolve(ExportViewModel)
    filename = await export_vm.export_session("session-123")
    print(f"Exported to {filename}")
```

---

## Что осталось без изменений

### Что deprecated (будет удалено)

Старый API всё ещё работает но помечен как deprecated:

```python
# Было
@deprecated("Use SendPromptUseCase instead")
async def send_prompt(self, text):
    pass
```

**Что удалено полностью**:

```python
# Было
ACPClient.direct_send()      # Удалено → используй Use Case
Session.direct_update()      # Удалено → используй Use Case
GlobalState.instance()       # Удалено → используй DI контейнер
```

---

## Матрица совместимости

| Компонент | Старая | Новая | Статус |
|-----------|--------|-------|--------|
| Transport | ✅ TCP | WebSocket | Обновлено |
| Sessions | ✅ Simple | Repository pattern | Обновлено |
| Use Cases | ❌ | ✅ | Новое |
| ViewModels | ❌ | ✅ | Новое |
| DI Container | Manual | ✅ Automatic | Новое |
| Event Bus | ❌ | ✅ | Новое |
| Testing | Hard | ✅ Easy | Улучшено |

---

## Checklist миграции

### Подготовка

- [ ] Прочитать ARCHITECTURE.md и DEVELOPING.md
- [ ] Установить зависимости (uv install)
- [ ] Запустить тесты (make check)
- [ ] Запустить TUI (python -m acp_client.tui)

### Фаза 1: Инфраструктура

- [ ] Инициализировать DIBootstrapper в main
- [ ] Проверить что все Use Cases регистрируются
- [ ] Проверить что все ViewModels доступны

### Фаза 2: Основные операции

- [ ] Заменить direct client calls на Use Cases
- [ ] Обновить обработчики событий
- [ ] Добавить DTOs для всех операций

### Фаза 3: UI компоненты

- [ ] Создать ViewModels для каждого компонента
- [ ] Обновить TUI компоненты
- [ ] Использовать Observable для состояния

### Фаза 4: События

- [ ] Определить Domain Events
- [ ] Реализовать EventBus listeners
- [ ] Удалить старые callback-style обработчики

### Фаза 5: Тестирование

- [ ] Unit тесты для Use Cases
- [ ] Unit тесты для ViewModels
- [ ] Integration тесты для сценариев

### Фаза 6: Очистка

- [ ] Удалить старый код (если не используется)
- [ ] Обновить импорты везде
- [ ] Запустить linting и type checking

### Финализация

- [ ] Код review
- [ ] Merge в main
- [ ] Release notes

---

## Troubleshooting

### Ошибка: "Cannot resolve dependency"

**Проблема**:
```python
# Неправильно
send_uc = bootstrapper.resolve(SendPromptUseCase)
# Error: Cannot resolve SendPromptUseCase
```

**Решение**:
```python
# Правильно
# Убедитесь что Use Case зарегистрирован в DIBootstrapper
# infrastructure/di_bootstrapper.py
def _register_use_cases(self):
    self.di_container.register(SendPromptUseCase)

# Или используйте resolve с интерфейсом
send_uc = bootstrapper.resolve(UseCase)  # если есть factory
```

---

### Ошибка: "Observable не обновляется"

**Проблема**:
```python
# Но _on_data_changed() не вызывается
messages = Observable([])
messages.subscribe(print)
messages.set([1, 2, 3])  # print не вызывается!
```

**Решение**:
```python
# Неправильно
messages = [1, 2, 3]  # Изменяем список напрямую
messages.set(messages)  # Observable не замечает изменение!

# Правильно
messages = Observable([])
current = messages.get()
current.append(1)
messages.set(current)  # Правильно! Создаём новый объект
```

---

### Ошибка: "Use Case не выполняется"

**Проблема**:
```python
# Инициализируем соединение ПЕРЕД использованием сессий
async with DIBootstrapper() as bootstrapper:
    create_uc = bootstrapper.resolve(CreateSessionUseCase)
    # Но соединение не инициализировано!
    await create_uc.execute(...)  # Ошибка!
```

**Решение**:
```python
# Инициализируем соединение ПЕРЕД использованием сессий
async with DIBootstrapper() as bootstrapper:
    # 1. Инициализировать соединение
    initialize_uc = bootstrapper.resolve(InitializeUseCase)
    await initialize_uc.execute(InitializeRequest())
    
    # 2. Теперь можно использовать другие Use Cases
    create_uc = bootstrapper.resolve(CreateSessionUseCase)
    await create_uc.execute(CreateSessionRequest("my-session"))
```

---

### Ошибка: "Тесты падают после миграции"

**Проблема**:
```python
# Было (старый тест)
@pytest.mark.asyncio
async def test_create_session():
    client = ACPClient("localhost", 8000)
    # Ошибка: не подключено!
    session = await client.create_session("test")
```

**Решение**:
```python
# Стало (новый тест с моками)
@pytest.mark.asyncio
async def test_create_session():
    # Mock зависимости
    mock_transport = AsyncMock(spec=TransportService)
    mock_repo = AsyncMock(spec=SessionRepository)
    
    # Создать Use Case с моками
    use_case = CreateSessionUseCase(mock_transport, mock_repo)
    
    # Настроить моки
    mock_repo.save.return_value = None
    mock_transport.send_message.return_value = {"id": "session-1"}
    
    # Выполнить
    response = await use_case.execute(CreateSessionRequest("test"))
    
    # Проверить
    assert response.session_id == "session-1"
    mock_repo.save.assert_called_once()
```

---

### Ошибка: "EventBus не публикует события"

**Проблема**:
```python
# Неправильно
event_bus = EventBus()
event_bus.publish(MyEvent())  # Не дождался async!
```

**Решение**:
```python
# Правильно
event_bus = EventBus()
await event_bus.publish(MyEvent())  # Используй await!
```

---

### Ошибка: "DI контейнер не освобождает ресурсы"

**Проблема**:
```python
# ❌ Контейнер не очищает ресурсы (WebSocket остается открытым)
bootstrapper = DIBootstrapper()
uc = bootstrapper.resolve(SomeUseCase)
# WebSocket остается открытым!
```

**Решение**:
```python
# Используйте context manager
async with DIBootstrapper() as bootstrapper:
    uc = bootstrapper.resolve(SomeUseCase)
    await uc.execute(...)
# Контейнер автоматически очищает ресурсы

# Или явный cleanup
bootstrapper = DIBootstrapper()
try:
    uc = bootstrapper.resolve(SomeUseCase)
    await uc.execute(...)
finally:
    await bootstrapper.dispose()
```

---

### Ошибка: "Импорты из старых модулей"

**Проблема**:
```python
# Было
from acp_client.client import ACPClient
from acp_client.handlers import FileHandler
```

**Решение**:
```python
# Стало
from acp_client.application.use_cases import CreateSessionUseCase
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
```

---

### Ошибка: "Type checking ошибки"

**Проблема**:
```python
# Неправильно (старый стиль)
def send_prompt(text) -> None:
    pass

response = send_prompt("hello")  # type checker не знает что это str или None?
```

**Решение**:
```python
# Правильно (новый стиль)
async def send_prompt(text: str) -> SendPromptResponse:
    pass

response = await send_prompt("hello")  # type checker знает что это SendPromptResponse
```

---

## Ресурсы

### Документация проекта

- [ARCHITECTURE.md](../developer-guide/ARCHITECTURE.md) — Полная архитектура (все 5 слоёв)
- [DEVELOPING.md](../developer-guide/DEVELOPING.md) — Как разработать функцию
- [TESTING.md](../developer-guide/TESTING.md) — Как писать тесты

### Исходный код

- `acp-client/src/acp_client/domain/` — Domain сущности и интерфейсы
- `acp-client/src/acp_client/application/` — Use Cases и DTOs
- `acp-client/src/acp_client/infrastructure/` — DI, Transport, Repositories
- `acp-client/src/acp_client/presentation/` — ViewModels и Observable
- `acp-client/src/acp_client/tui/` — UI компоненты

### Отчеты о рефакторинге

- `DI_ANALYSIS_REPORT.md` — Анализ Dependency Injection
- `DI_IMPROVEMENTS.md` — Рекомендуемые улучшения DI

### Протокол ACP

- `doc/ACP/protocol/` — Полная спецификация ACP протокола

### Команды для проверки

```bash
# Запуск всех проверок (из acp-client)
make check

# Или локальная проверка (из acp-client)
uv run ruff check .
uv run pyright .
uv run python -m pytest

# Запуск TUI (для ручного тестирования)
python -m acp_client.tui
```

---

## Заключение

Миграция с Legacy API на Clean Architecture требует переосмысления как вы организуете код. Главные изменения:

1. **Use Cases** вместо методов на клиенте
2. **ViewModels** вместо сложной логики в UI
3. **DI контейнер** вместо глобальных объектов
4. **Observable** вместо ручного обновления UI
5. **Event Bus** вместо callbacks

Если вы будете следовать этому руководству и примерам, миграция должна пройти гладко. Удачи! 🚀
