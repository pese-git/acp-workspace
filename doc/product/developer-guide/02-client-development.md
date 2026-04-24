# Разработка клиента

> Руководство по разработке TUI клиента CodeLab.

## Обзор

Клиент CodeLab построен на [Textual](https://textual.textualize.io/) с использованием Clean Architecture и MVVM паттерна.

## Структура клиента

```
client/
├── domain/              # Domain Layer
│   ├── entities.py      # Сущности
│   └── repositories.py  # Интерфейсы репозиториев
├── application/         # Application Layer
│   ├── use_cases/       # Use Cases
│   ├── dtos/            # Data Transfer Objects
│   └── state_machine.py # State Machine
├── infrastructure/      # Infrastructure Layer
│   ├── di_bootstrapper.py
│   ├── transport.py
│   ├── event_bus.py
│   └── handlers/
│       ├── fs/
│       └── terminal/
├── presentation/        # Presentation Layer
│   ├── base_view_model.py
│   ├── chat_view_model.py
│   ├── observable.py
│   └── ...
└── tui/                 # TUI Layer
    ├── app.py
    ├── components/
    └── styles/
```

## MVVM Pattern

### Observable State

```python
from codelab.client.presentation.observable import Observable

class Observable(Generic[T]):
    """Наблюдаемое значение с подпиской на изменения."""
    
    def __init__(self, initial: T) -> None:
        self._value = initial
        self._subscribers: list[Callable[[T], None]] = []
    
    def get(self) -> T:
        return self._value
    
    def set(self, value: T) -> None:
        self._value = value
        for subscriber in self._subscribers:
            subscriber(value)
    
    def subscribe(self, callback: Callable[[T], None]) -> None:
        self._subscribers.append(callback)
```

### BaseViewModel

```python
from codelab.client.presentation.base_view_model import BaseViewModel

class BaseViewModel:
    """Базовый класс ViewModel."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._subscriptions: list[Subscription] = []
    
    def dispose(self) -> None:
        """Очистка подписок при уничтожении."""
        for sub in self._subscriptions:
            sub.unsubscribe()
```

### Создание ViewModel

```python
from codelab.client.presentation.chat_view_model import ChatViewModel

class ChatViewModel(BaseViewModel):
    """ViewModel для Chat View."""
    
    def __init__(
        self,
        event_bus: EventBus,
        send_prompt_use_case: SendPromptUseCase,
    ) -> None:
        super().__init__(event_bus)
        
        # Наблюдаемое состояние
        self.messages: Observable[list[Message]] = Observable([])
        self.is_loading: Observable[bool] = Observable(False)
        self.error: Observable[str | None] = Observable(None)
        
        self._send_prompt_use_case = send_prompt_use_case
    
    async def send_message(self, text: str) -> None:
        """Отправка сообщения агенту."""
        self.is_loading.set(True)
        self.error.set(None)
        
        try:
            await self._send_prompt_use_case.execute(text)
        except Exception as e:
            self.error.set(str(e))
        finally:
            self.is_loading.set(False)
    
    def on_message_received(self, message: Message) -> None:
        """Обработка входящего сообщения."""
        messages = self.messages.get()
        self.messages.set([*messages, message])
```

## TUI Компоненты

### Структура компонентов

```
tui/components/
├── __init__.py
├── chat_view.py           # Чат с агентом
├── file_tree.py           # Файловое дерево
├── file_viewer.py         # Просмотр файлов
├── footer.py              # Footer bar
├── header.py              # Header bar
├── help_modal.py          # Модальное окно справки
├── permission_modal.py    # Модальное окно разрешений
├── inline_permission_widget.py  # Inline разрешения
├── plan_panel.py          # Панель плана
├── prompt_input.py        # Поле ввода
├── sidebar.py             # Боковая панель
├── terminal_log_modal.py  # Лог терминала
├── terminal_output.py     # Вывод терминала
└── tool_panel.py          # Панель инструментов
```

### Создание компонента

```python
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, Input
from textual.reactive import reactive

class PromptInput(Vertical):
    """Компонент ввода промпта."""
    
    # Reactive атрибуты
    is_disabled: reactive[bool] = reactive(False)
    placeholder: reactive[str] = reactive("Введите сообщение...")
    
    def __init__(
        self,
        view_model: PromptInputViewModel,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._view_model = view_model
    
    def compose(self) -> ComposeResult:
        """Создание дочерних виджетов."""
        yield Static("💬", id="prompt-icon")
        yield Input(
            placeholder=self.placeholder,
            disabled=self.is_disabled,
            id="prompt-input",
        )
    
    def on_mount(self) -> None:
        """Инициализация при монтировании."""
        # Подписка на изменения ViewModel
        self._view_model.is_loading.subscribe(self._on_loading_change)
    
    def _on_loading_change(self, is_loading: bool) -> None:
        """Обработка изменения состояния загрузки."""
        self.is_disabled = is_loading
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Обработка отправки ввода."""
        text = event.value.strip()
        if text:
            event.input.value = ""
            await self._view_model.send_message(text)
```

### Стилизация (TCSS)

```css
/* styles/app.tcss */

PromptInput {
    height: auto;
    padding: 1;
    background: $surface;
}

PromptInput Input {
    width: 100%;
    border: solid $primary;
}

PromptInput Input:focus {
    border: solid $accent;
}

PromptInput.-disabled Input {
    opacity: 0.5;
}
```

## Use Cases

### Структура Use Case

```python
from codelab.client.application.use_cases.base import UseCase

class SendPromptUseCase(UseCase):
    """Use case отправки промпта."""
    
    def __init__(
        self,
        transport: Transport,
        session_repository: SessionRepository,
        event_bus: EventBus,
    ) -> None:
        self._transport = transport
        self._session_repository = session_repository
        self._event_bus = event_bus
    
    async def execute(self, session_id: str, text: str) -> None:
        """Выполнение use case."""
        # Валидация
        if not text.strip():
            raise ValueError("Prompt cannot be empty")
        
        # Получение сессии
        session = await self._session_repository.get(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        
        # Отправка
        await self._transport.send({
            "jsonrpc": "2.0",
            "method": "session/prompt",
            "params": {
                "session_id": session_id,
                "prompt": {"text": text}
            }
        })
        
        # Публикация события
        self._event_bus.publish(PromptSentEvent(session_id, text))
```

## Infrastructure Layer

### DI Bootstrapper

```python
class DIBootstrapper:
    """Инициализация контейнера зависимостей."""
    
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
    
    def bootstrap(self) -> Container:
        container = Container()
        
        # Event Bus
        event_bus = EventBus()
        container.register_instance(EventBus, event_bus)
        
        # Transport
        transport = WebSocketTransport(self._host, self._port)
        container.register_instance(Transport, transport)
        
        # Repositories
        container.register(SessionRepository, InMemorySessionRepository)
        
        # Use Cases
        container.register(SendPromptUseCase)
        container.register(CreateSessionUseCase)
        
        # ViewModels
        container.register(ChatViewModel)
        container.register(SessionViewModel)
        
        # Handlers
        self._register_handlers(container)
        
        return container
    
    def _register_handlers(self, container: Container) -> None:
        """Регистрация RPC handlers."""
        handler_registry = HandlerRegistry()
        
        # File System handlers
        handler_registry.register("fs/read_text_file", FileReadHandler)
        handler_registry.register("fs/write_text_file", FileWriteHandler)
        
        # Terminal handlers
        handler_registry.register("terminal/create", TerminalCreateHandler)
        
        container.register_instance(HandlerRegistry, handler_registry)
```

### Event Bus

```python
class EventBus:
    """Шина событий для слабо связанной коммуникации."""
    
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable]] = {}
    
    def subscribe(
        self,
        event_type: type[T],
        handler: Callable[[T], None],
    ) -> Subscription:
        """Подписка на событие."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        return Subscription(lambda: self._unsubscribe(event_type, handler))
    
    def publish(self, event: Any) -> None:
        """Публикация события."""
        event_type = type(event)
        for handler in self._subscribers.get(event_type, []):
            handler(event)
```

### Handlers (fs/*, terminal/*)

```python
class FileReadHandler:
    """Обработчик fs/read_text_file запросов от сервера."""
    
    async def handle(self, params: dict) -> dict:
        """Чтение файла и возврат содержимого."""
        path = Path(params["path"])
        
        # Проверка безопасности
        if not self._is_safe_path(path):
            raise SecurityError("Path traversal detected")
        
        # Чтение файла
        content = path.read_text(encoding="utf-8")
        
        return {
            "content": content,
            "total_lines": content.count("\n") + 1,
        }
```

## Тестирование

### Unit тесты ViewModel

```python
import pytest
from unittest.mock import AsyncMock, Mock

class TestChatViewModel:
    @pytest.fixture
    def view_model(self) -> ChatViewModel:
        event_bus = Mock(spec=EventBus)
        use_case = AsyncMock(spec=SendPromptUseCase)
        return ChatViewModel(event_bus, use_case)
    
    async def test_send_message_sets_loading(self, view_model):
        """Проверка что send_message устанавливает is_loading."""
        assert view_model.is_loading.get() is False
        
        # Запуск без await для проверки промежуточного состояния
        task = asyncio.create_task(view_model.send_message("test"))
        await asyncio.sleep(0)
        
        assert view_model.is_loading.get() is True
        
        await task
        assert view_model.is_loading.get() is False
    
    async def test_send_message_calls_use_case(self, view_model):
        """Проверка вызова use case."""
        await view_model.send_message("Hello")
        
        view_model._send_prompt_use_case.execute.assert_called_once_with("Hello")
```

### Интеграционные тесты

```python
class TestChatIntegration:
    @pytest.fixture
    async def app(self):
        """Создание тестового приложения."""
        app = ACPClientApp(host="localhost", port=8765)
        async with app.run_test() as pilot:
            yield pilot
    
    async def test_send_message(self, app):
        """Интеграционный тест отправки сообщения."""
        # Ввод текста
        await app.press("H", "e", "l", "l", "o")
        await app.press("enter")
        
        # Проверка отправки
        chat_view = app.query_one(ChatView)
        assert len(chat_view.messages) == 1
```

## Рекомендации

### Структура кода

1. **Один компонент — один файл**
2. **ViewModel для каждого сложного компонента**
3. **Use Case для каждой бизнес-операции**
4. **Events для коммуникации между слоями**

### Именование

- ViewModels: `*ViewModel` (ChatViewModel)
- Use Cases: `*UseCase` (SendPromptUseCase)
- Components: описательные имена (PromptInput)
- Events: `*Event` (MessageReceivedEvent)

### Тестирование

- Unit тесты для ViewModels
- Интеграционные тесты для компонентов
- E2E тесты для критических путей

## См. также

- [Архитектура](01-architecture.md) — общая архитектура
- [Тестирование](05-testing.md) — руководство по тестированию
- [Textual документация](https://textual.textualize.io/)
