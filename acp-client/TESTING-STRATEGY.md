# Стратегия тестирования acp-client

Документация по подходам, инструментам и практикам тестирования в проекте acp-client.

## Содержание

1. [Введение](#введение)
2. [Инструменты и фреймворки](#инструменты-и-фреймворки)
3. [Структура тестов](#структура-тестов)
4. [Unit тесты](#unit-тесты)
5. [MVVM тесты](#mvvm-тесты)
6. [Integration тесты](#integration-тесты)
7. [Fixtures и моки](#fixtures-и-моки)
8. [Асинхронное тестирование](#асинхронное-тестирование)
9. [Coverage и метрики](#coverage-и-метрики)
10. [Best Practices](#best-practices)
11. [Запуск тестов](#запуск-тестов)
12. [Отладка тестов](#отладка-тестов)
13. [CI/CD интеграция](#cicd-интеграция)
14. [Типичные проблемы и решения](#типичные-проблемы-и-решения)

---

## Введение

### Философия тестирования

acp-client следует принципам чистой архитектуры и многоуровневого тестирования:

- **Unit тесты** - тестируют отдельные компоненты в изоляции
- **Integration тесты** - тестируют взаимодействие между компонентами
- **MVVM тесты** - тестируют связку UI компонента с ViewModel
- **E2E тесты** (интеграция с реальным сервером) - полный workflow

### Test Pyramid

```
         /\
        /  \  E2E (интеграция с сервером)
       /----\
      /      \  Integration
     /--------\
    /          \  Unit
   /____________\
```

### Цели тестирования

1. **Гарантия корректности** - код работает как ожидается
2. **Регрессионная защита** - новые изменения не ломают старый функционал
3. **Документирование** - тесты документируют поведение кода
4. **Упрощение рефакторинга** - быстрое обнаружение проблем при изменениях
5. **Изоляция слоев** - валидация архитектуры (domain ≠ infrastructure)

---

## Инструменты и фреймворки

### Основные зависимости

Все зависимости для тестирования указаны в `pyproject.toml`:

```toml
[dependency-groups]
dev = [
  "pytest>=8.3.5",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.11.4",
  "ty>=0.0.1a11",
]
```

### pytest

Основной фреймворк для запуска тестов.

**Особенности:**
- Автоматическое обнаружение тестов по паттерну `test_*.py`
- Встроенная система fixtures
- Подробные отчёты о сбоях
- Параллельное выполнение тестов

### pytest-asyncio

Расширение для тестирования асинхронного кода.

**Использование:**
```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected_value
```

### unittest.mock

Встроенный модуль Python для создания моков и патчей.

```python
from unittest.mock import Mock, MagicMock, patch

# Создание простого мока
mock_obj = Mock()
mock_obj.some_method.return_value = "value"

# Проверка вызовов
assert mock_obj.some_method.called
assert mock_obj.some_method.call_count == 1
```

### pytest-cov (coverage)

Инструмент для измерения покрытия кода тестами.

```bash
# Запуск с отчётом о покрытии
pytest --cov=acp_client --cov-report=html
```

---

## Структура тестов

### Организация файлов

Тесты расположены в директории `acp-client/tests/`:

```
tests/
├── conftest.py                          # Общие fixtures
├── test_domain_*.py                     # Тесты Domain Layer
├── test_application_*.py                # Тесты Application Layer
├── test_infrastructure_*.py             # Тесты Infrastructure Layer
├── test_presentation_*.py               # Тесты Presentation Layer
├── test_tui_*.py                        # Тесты TUI компонентов
├── test_tui_*_mvvm.py                   # MVVM тесты (View + ViewModel)
├── test_navigation_*.py                 # Тесты NavigationManager
├── test_integration_*.py                # Integration тесты
└── test_cli.py                          # Тесты CLI
```

### Naming Conventions

| Тип | Паттерн | Пример |
|-----|---------|--------|
| Test файл | `test_<module>.py` | `test_domain_entities.py` |
| Test класс | `Test<Component>` | `TestSession` |
| Test метод | `test_<scenario>` | `test_session_create` |
| Fixture | `<name>_fixture` или просто `<name>` | `mock_transport` |

### Категории тестов

#### 1. Unit тесты Domain Layer
- **Файлы:** `test_domain_*.py`
- **Тестируют:** entities, events, domain logic
- **Характеристика:** быстрые, изолированные, no mocks

#### 2. Unit тесты Application Layer
- **Файлы:** `test_application_*.py`
- **Тестируют:** use cases, state machine, application services
- **Характеристика:** тестируют бизнес-логику с моками инфраструктуры

#### 3. Unit тесты Infrastructure Layer
- **Файлы:** `test_infrastructure_*.py`
- **Тестируют:** DI container, event bus, transport, repositories
- **Характеристика:** могут использовать real компоненты или моки

#### 4. Unit тесты Presentation Layer
- **Файлы:** `test_presentation_*.py`
- **Тестируют:** ViewModels, Observable pattern
- **Характеристика:** тестируют reactive логику, подписки на события

#### 5. MVVM тесты
- **Файлы:** `test_tui_*_mvvm.py`
- **Тестируют:** компонент View + его ViewModel
- **Характеристика:** интеграционные тесты UI слоя

#### 6. Integration тесты
- **Файлы:** `test_integration_*.py`
- **Тестируют:** полный workflow с реальным/mock сервером
- **Характеристика:** медленные, но проверяют реальные сценарии

---

## Unit тесты

### Что тестируем

#### Domain Layer

```python
# tests/test_domain_entities.py
"""Тесты для Domain entities."""

from datetime import datetime
from acp_client.domain import Message, Session, ToolCall

class TestSession:
    """Тесты для Session entity."""
    
    def test_session_create(self) -> None:
        """Тест создания новой сессии."""
        session = Session.create(
            server_host="127.0.0.1",
            server_port=8765,
            client_capabilities={"fs": {"readTextFile": True}},
            server_capabilities={"tools": ["read", "write"]},
        )
        
        assert session.server_host == "127.0.0.1"
        assert session.server_port == 8765
        assert session.client_capabilities == {"fs": {"readTextFile": True}}
        assert session.server_capabilities == {"tools": ["read", "write"]}
        assert session.is_authenticated is False
    
    def test_session_has_timestamp(self) -> None:
        """Тест что у сессии есть timestamp создания."""
        session = Session.create(
            server_host="127.0.0.1",
            server_port=8765,
            client_capabilities={},
            server_capabilities={},
        )
        
        assert isinstance(session.created_at, datetime)
```

**Принципы:**
- Тестируем бизнес-правила, не реализацию
- Используем только реальные объекты (no mocks)
- Проверяем граничные случаи

#### Application Layer

```python
# tests/test_application_state_machine.py
"""Тесты для State Machine."""

import pytest
from acp_client.application import (
    UIState,
    UIStateMachine,
    StateTransitionError,
)

class TestUIStateMachine:
    """Тесты для UIStateMachine."""
    
    def test_initial_state(self) -> None:
        """Тест начального состояния."""
        sm = UIStateMachine()
        assert sm.current_state == UIState.INITIALIZING
    
    def test_valid_transition(self) -> None:
        """Тест валидного перехода."""
        sm = UIStateMachine(initial_state=UIState.READY)
        assert sm.can_transition(UIState.PROCESSING_PROMPT)
        
        state_change = sm.transition(UIState.PROCESSING_PROMPT)
        assert sm.current_state == UIState.PROCESSING_PROMPT
        assert state_change.from_state == UIState.READY
    
    def test_invalid_transition_raises_error(self) -> None:
        """Тест что невалидный переход выбрасывает исключение."""
        sm = UIStateMachine(initial_state=UIState.INITIALIZING)
        
        with pytest.raises(StateTransitionError):
            sm.transition(UIState.PROCESSING_PROMPT)
    
    def test_transition_with_metadata(self) -> None:
        """Тест переход с метаданными."""
        sm = UIStateMachine(initial_state=UIState.READY)
        metadata = {"session_id": "123"}
        
        state_change = sm.transition(
            UIState.PROCESSING_PROMPT,
            metadata=metadata,
        )
        assert state_change.metadata == metadata
```

**Принципы:**
- Тестируем каждый use case отдельно
- Проверяем state transitions
- Используем моки для external dependencies

#### Infrastructure Layer

```python
# tests/test_infrastructure_transport.py
"""Тесты для Transport."""

import pytest
from acp_client.infrastructure.transport import WebSocketTransport

class TestWebSocketTransport:
    """Тесты WebSocketTransport."""
    
    def test_default_parameters(self) -> None:
        """Проверяет инициализацию с параметрами по умолчанию."""
        transport = WebSocketTransport()
        assert transport.host == "127.0.0.1"
        assert transport.port == 8765
        assert transport.path == "/acp/ws"
        assert not transport.is_connected()
    
    def test_custom_parameters(self) -> None:
        """Проверяет инициализацию с кастомными параметрами."""
        transport = WebSocketTransport(
            host="localhost",
            port=9000,
            path="/custom/ws",
        )
        assert transport.host == "localhost"
        assert transport.port == 9000
        assert transport.path == "/custom/ws"
    
    @pytest.mark.asyncio
    async def test_send_raises_when_not_connected(self) -> None:
        """Проверяет что send_str выбрасывает ошибку без соединения."""
        transport = WebSocketTransport()
        with pytest.raises(RuntimeError, match="not open"):
            await transport.send_str("test")
```

**Принципы:**
- Тестируем инициализацию и конфигурацию
- Проверяем error handling
- Используем реальные объекты если возможно

#### Presentation Layer

```python
# tests/test_presentation_observable.py
"""Тесты для Observable Pattern."""

from acp_client.presentation.observable import Observable

class TestObservable:
    """Тесты для Observable класса."""

    def test_observable_initialization(self) -> None:
        """Проверить инициализацию Observable."""
        obs = Observable(42)
        assert obs.value == 42

    def test_observable_value_change(self) -> None:
        """Проверить изменение значения."""
        obs = Observable(1)
        obs.value = 2
        assert obs.value == 2

    def test_observable_notify_on_change(self) -> None:
        """Проверить что observers уведомляются об изменении."""
        obs = Observable(1)
        changes = []
        
        obs.subscribe(lambda x: changes.append(x))
        
        obs.value = 2
        obs.value = 3
        
        assert changes == [2, 3]

    def test_observable_unsubscribe(self) -> None:
        """Проверить отписку от Observable."""
        obs = Observable(0)
        changes = []
        
        unsubscribe = obs.subscribe(lambda x: changes.append(x))
        
        obs.value = 1
        unsubscribe()  # Отписаться
        obs.value = 2
        
        assert changes == [1]  # 2 не должно быть в списке

    def test_observable_multiple_observers(self) -> None:
        """Проверить работу с множеством observers."""
        obs = Observable(0)
        results1 = []
        results2 = []
        
        obs.subscribe(lambda x: results1.append(x))
        obs.subscribe(lambda x: results2.append(x))
        
        obs.value = 1
        obs.value = 2
        
        assert results1 == [1, 2]
        assert results2 == [1, 2]
```

**Принципы:**
- Тестируем Observable паттерн и подписки
- Проверяем notification логику
- Проверяем cleanup (unsubscribe)

### AAA Pattern (Arrange-Act-Assert)

Все unit тесты следуют AAA паттерну:

```python
def test_some_functionality() -> None:
    # ARRANGE - подготовка
    obj = SomeClass()
    expected = "result"
    
    # ACT - выполнение
    actual = obj.do_something()
    
    # ASSERT - проверка
    assert actual == expected
```

---

## MVVM тесты

### Что такое MVVM тесты

MVVM тесты тестируют взаимодействие между:
- **View** - UI компонент (Textual Widget)
- **ViewModel** - логика презентации с Observable свойствами

```python
# tests/test_tui_chat_view_mvvm.py
"""Тесты для компонента ChatView с MVVM интеграцией."""

from acp_client.infrastructure.events.bus import EventBus
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.tui.components.chat_view import ChatView

@pytest.fixture
def event_bus() -> EventBus:
    """Создать EventBus для тестов."""
    return EventBus()

@pytest.fixture
def chat_view_model(event_bus: EventBus) -> ChatViewModel:
    """Создать ChatViewModel для тестов."""
    return ChatViewModel(
        coordinator=None,
        event_bus=event_bus,
        logger=None,
    )

@pytest.fixture
def chat_view(chat_view_model: ChatViewModel) -> ChatView:
    """Создать ChatView с ChatViewModel."""
    view = ChatView(chat_view_model)
    view._mounted = True  # Имитируем монтирование
    return view

def test_chat_view_initializes_with_view_model(
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ChatView инициализируется с ChatViewModel."""
    chat_view = ChatView(chat_view_model)
    
    assert chat_view.chat_vm is chat_view_model
    assert chat_view.id == "chat_view"
    assert chat_view._mounted is False
```

### Тестирование Observable уведомлений

```python
def test_chat_view_updates_on_messages_changed(
    chat_view: ChatView,
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ChatView обновляется при добавлении сообщений."""
    messages = [
        {"type": "user", "content": "Hello"},
        {"type": "assistant", "content": "Hi there!"},
    ]
    
    chat_view_model.messages.value = messages
    
    # После обновления сообщений, компонент должен отобразить их
    assert chat_view_model.messages.value == messages

def test_chat_view_updates_on_streaming_text_changed(
    chat_view: ChatView,
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ChatView обновляется при streaming текста."""
    chat_view_model.is_streaming.value = True
    chat_view_model.streaming_text.value = "Loading response..."
    
    # Проверить что streaming флаг активен
    assert chat_view_model.is_streaming.value is True
    assert chat_view_model.streaming_text.value == "Loading response..."
```

### Тестирование user interactions

```python
def test_chat_view_updates_on_tool_calls_changed(
    chat_view: ChatView,
    chat_view_model: ChatViewModel,
) -> None:
    """Проверить что ChatView обновляется при добавлении tool calls."""
    tool_calls = [
        {
            "id": "tool_1",
            "name": "read_file",
            "arguments": {"path": "/tmp/file.txt"},
        },
    ]
    
    chat_view_model.tool_calls.value = tool_calls
    
    # Проверить что tool calls были добавлены
    assert chat_view_model.tool_calls.value == tool_calls
```

---

## Integration тесты

### Что тестируем

Integration тесты проверяют:
- Взаимодействие нескольких компонентов
- Полные workflow сценарии
- Интеграцию с mock/real сервером

### Пример: DI Container Integration

```python
# tests/test_di_bootstrapper.py
"""Тесты полной инициализации DI контейнера."""

@pytest.mark.asyncio
async def test_di_bootstrapper_initializes_all_components() -> None:
    """Проверить что DI bootstrapper инициализирует все компоненты."""
    container = await DIBootstrapper.bootstrap()
    
    # Проверить наличие всех необходимых сервисов
    assert container.resolve(TransportService) is not None
    assert container.resolve(SessionCoordinator) is not None
    assert container.resolve(EventBus) is not None
    assert container.resolve(HandlerRegistry) is not None
```

### Пример: Full Workflow с Mock сервером

```python
# tests/test_integration_with_server.py
"""Integration тесты с mock WebSocket сервером."""

import json
import socket
import pytest
from aiohttp import web
from acp_client import ACPClient

def _get_free_port() -> int:
    """Получить свободный порт для mock сервера."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])

@pytest.mark.asyncio
async def test_full_session_workflow() -> None:
    """Тест полного workflow: создание, загрузка, отправка промпта."""
    
    async def handle_ws_request(request: web.Request) -> web.WebSocketResponse:
        """Mock WebSocket обработчик."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        async for message in ws:
            payload = json.loads(message.data)
            
            # Ответить на initialize
            if payload.get("method") == "initialize":
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": 1,
                        "agentCapabilities": {},
                        "agentInfo": {"name": "test-agent", "version": "1.0.0"},
                        "authMethods": [],
                    },
                })
            
            # Ответить на session/load
            elif payload.get("method") == "session/load":
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "configOptions": [],
                        "modes": {
                            "availableModes": [],
                            "currentModeId": "ask",
                        },
                    },
                })
            
            break
        return ws
    
    # Запустить mock сервер
    port = _get_free_port()
    app = web.Application()
    app.router.add_get("/acp/ws", handle_ws_request)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    
    try:
        # Создать клиент и выполнить workflow
        client = ACPClient(host="127.0.0.1", port=port)
        await client.initialize()
        session = await client.load_session("test-session")
        
        assert session is not None
        assert session.id == "test-session"
    finally:
        await runner.cleanup()
```

---

## Fixtures и моки

### Fixtures в conftest.py

```python
# tests/conftest.py
"""Общие pytest fixtures для всех тестов acp-client."""

from unittest.mock import Mock
import pytest

@pytest.fixture
def mock_session_view_model() -> Mock:
    """Создать mock SessionViewModel для тестов компонентов."""
    mock_vm = Mock()
    # Инициализируем Observable свойства
    mock_vm.sessions = Mock()
    mock_vm.sessions.subscribe = Mock()
    mock_vm.selected_session_id = Mock()
    mock_vm.selected_session_id.subscribe = Mock()
    mock_vm.is_loading_sessions = Mock()
    mock_vm.is_loading_sessions.subscribe = Mock()
    return mock_vm

@pytest.fixture
def mock_chat_view_model() -> Mock:
    """Создать mock ChatViewModel для тестов компонентов."""
    mock_vm = Mock()
    mock_vm.messages = Mock()
    mock_vm.messages.subscribe = Mock()
    mock_vm.tool_calls = Mock()
    mock_vm.tool_calls.subscribe = Mock()
    mock_vm.is_streaming = Mock()
    mock_vm.is_streaming.subscribe = Mock()
    mock_vm.streaming_text = Mock()
    mock_vm.streaming_text.subscribe = Mock()
    return mock_vm

@pytest.fixture
def mock_terminal_view_model() -> Mock:
    """Создать mock TerminalViewModel для тестов компонентов."""
    mock_vm = Mock()
    mock_vm.output = Mock()
    mock_vm.output.subscribe = Mock()
    mock_vm.output.value = ""
    mock_vm.has_output = Mock()
    mock_vm.has_output.subscribe = Mock()
    mock_vm.has_output.value = False
    mock_vm.is_running = Mock()
    mock_vm.is_running.subscribe = Mock()
    mock_vm.is_running.value = False
    return mock_vm
```

### Как создавать моки

#### Simple Mock

```python
from unittest.mock import Mock

# Создать простой мок
mock_obj = Mock()
mock_obj.some_method.return_value = "value"

# Использовать
result = mock_obj.some_method()
assert result == "value"
```

#### Mock with Spec

```python
from unittest.mock import Mock
from acp_client.infrastructure.transport import TransportService

# Мок с контрактом реального класса
mock_transport = Mock(spec=TransportService)
mock_transport.send_str.return_value = None
```

#### Mock with Side Effects

```python
from unittest.mock import Mock

# Мок с побочным эффектом (исключение)
mock_obj = Mock()
mock_obj.some_method.side_effect = ValueError("test error")

try:
    mock_obj.some_method()
except ValueError:
    pass  # Ожидается
```

#### Verify Mock Calls

```python
from unittest.mock import Mock

mock_obj = Mock()
mock_obj.method(arg1="value1")

# Проверить что метод был вызван
assert mock_obj.method.called
assert mock_obj.method.call_count == 1
assert mock_obj.method.call_args[1]["arg1"] == "value1"
```

### Best Practices для Fixtures

1. **Изолированные fixtures** - каждый тест получает свой экземпляр
   ```python
   @pytest.fixture
   def fresh_container() -> DIContainer:
       """Создать новый DI контейнер для каждого теста."""
       return DIContainer()
   ```

2. **Fixtures с cleanup** - использовать yield
   ```python
   @pytest.fixture
   async def database() -> AsyncGenerator[DB, None]:
       db = await DB.connect()
       yield db
       await db.disconnect()  # cleanup
   ```

3. **Scope fixtures** - переиспользовать в пределах scope
   ```python
   @pytest.fixture(scope="session")
   def mock_server():
       """Запустить mock сервер один раз на всю сессию тестов."""
       return MockServer()
   ```

4. **Parametrized fixtures** - один fixture для разных случаев
   ```python
   @pytest.fixture(params=["127.0.0.1", "localhost"])
   def host(request):
       return request.param
   
   def test_connect_to_different_hosts(host):
       # Тест запустится для каждого host
       assert can_connect(host)
   ```

---

## Асинхронное тестирование

### pytest-asyncio

Для тестирования асинхронного кода используется декоратор `@pytest.mark.asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation() -> None:
    """Тест асинхронной операции."""
    result = await some_async_function()
    assert result == expected_value
```

### Примеры async тестов

#### Тест асинхронного метода

```python
@pytest.mark.asyncio
async def test_send_message_async(mock_transport: Mock) -> None:
    """Тест отправки сообщения асинхронно."""
    mock_transport.send_str = Mock(return_value=None)
    
    await mock_transport.send_str("test message")
    
    assert mock_transport.send_str.called
```

#### Тест с asyncio.wait_for (timeout)

```python
import asyncio

@pytest.mark.asyncio
async def test_operation_completes_within_timeout() -> None:
    """Тест что операция завершается в пределах timeout."""
    async def slow_operation() -> str:
        await asyncio.sleep(0.1)
        return "done"
    
    result = await asyncio.wait_for(slow_operation(), timeout=1.0)
    assert result == "done"
```

#### Тест с asyncio.gather (параллельные операции)

```python
@pytest.mark.asyncio
async def test_concurrent_operations() -> None:
    """Тест параллельных операций."""
    async def operation(n: int) -> int:
        await asyncio.sleep(0.1)
        return n * 2
    
    results = await asyncio.gather(
        operation(1),
        operation(2),
        operation(3),
    )
    
    assert results == [2, 4, 6]
```

#### Тест Observable со asyncio

```python
@pytest.mark.asyncio
async def test_observable_with_async_handlers() -> None:
    """Тест Observable с асинхронными обработчиками."""
    obs = Observable(0)
    results = []
    
    async def async_handler(value: int) -> None:
        await asyncio.sleep(0.01)
        results.append(value)
    
    obs.subscribe(lambda v: asyncio.create_task(async_handler(v)))
    
    obs.value = 1
    obs.value = 2
    
    # Дождаться выполнения async tasks
    await asyncio.sleep(0.1)
    assert results == [1, 2]
```

---

## Coverage и метрики

### Запуск с coverage

```bash
# Базовый отчёт
pytest --cov=acp_client

# HTML отчёт
pytest --cov=acp_client --cov-report=html
# Открыть: htmlcov/index.html

# Терминальный отчёт с подробностями
pytest --cov=acp_client --cov-report=term-missing
```

### Целевые метрики

| Компонент | Целевое покрытие | Обоснование |
|-----------|-----------------|-------------|
| Domain | 95%+ | Критичная бизнес-логика |
| Application | 90%+ | Важные use cases |
| Infrastructure | 85%+ | Может использовать real компоненты |
| Presentation | 85%+ | Observable паттерны сложнее тестировать |
| TUI компоненты | 70%+ | Визуальное тестирование сложно |

### Как улучшить покрытие

1. **Найти untested код**
   ```bash
   pytest --cov=acp_client --cov-report=term-missing | grep "?" 
   ```

2. **Написать тесты для граничных случаев**
   ```python
   def test_empty_input() -> None:
       result = process("")
       assert result == []
   
   def test_none_input() -> None:
       with pytest.raises(ValueError):
           process(None)
   ```

3. **Использовать parametrized тесты**
   ```python
   @pytest.mark.parametrize("input,expected", [
       ("hello", "HELLO"),
       ("", ""),
       ("123", "123"),
   ])
   def test_process_various_inputs(input, expected):
       assert process(input) == expected
   ```

---

## Best Practices

### 1. Arrange-Act-Assert (AAA)

Все тесты должны следовать этому паттерну:

```python
def test_something() -> None:
    # ARRANGE - подготовка данных и объектов
    obj = SomeClass()
    input_data = {"key": "value"}
    
    # ACT - выполнение проверяемого кода
    result = obj.process(input_data)
    
    # ASSERT - проверка результата
    assert result["status"] == "success"
    assert result["data"] is not None
```

### 2. Один тест = одна проверка

❌ **Плохо:**
```python
def test_user_operations() -> None:
    user = User.create("John")
    assert user.name == "John"  # Проверка 1
    user.set_email("john@example.com")
    assert user.email == "john@example.com"  # Проверка 2
    user.mark_active()
    assert user.is_active is True  # Проверка 3
```

✅ **Хорошо:**
```python
def test_user_creation() -> None:
    user = User.create("John")
    assert user.name == "John"

def test_user_email_setting() -> None:
    user = User.create("John")
    user.set_email("john@example.com")
    assert user.email == "john@example.com"

def test_user_activation() -> None:
    user = User.create("John")
    user.mark_active()
    assert user.is_active is True
```

### 3. Изоляция тестов

Каждый тест должен быть независимым и не зависеть от порядка выполнения:

```python
# ✅ Хорошо - каждый тест создаёт свой объект
class TestSession:
    def test_session_1(self) -> None:
        session = Session.create(...)
        # использовать session
    
    def test_session_2(self) -> None:
        session = Session.create(...)  # Новый объект
        # использовать session

# ❌ Плохо - зависимость между тестами
class TestSession:
    session = None
    
    def test_session_creation(self) -> None:
        TestSession.session = Session.create(...)
    
    def test_session_usage(self) -> None:
        # Зависит от предыдущего теста!
        assert TestSession.session is not None
```

### 4. Моки vs Реальные объекты

| Случай | Использовать |
|--------|--------------|
| External dependencies (HTTP, DB) | Моки или fixtures |
| Pure logic | Реальные объекты |
| Async операции | Моки с side_effect |
| Тяжёлые операции | Моки |

```python
# ❌ Неправильно - мокируем domain logic
def test_calculation(self):
    calculator = Mock(spec=Calculator)
    calculator.add.return_value = 5  # Тестируем конфигурацию мока!
    assert calculator.add(2, 3) == 5

# ✅ Правильно - реальная логика
def test_calculation(self):
    calculator = Calculator()
    assert calculator.add(2, 3) == 5

# ✅ Правильно - мокируем external dependency
def test_save_with_mock_storage(self):
    mock_storage = Mock(spec=StorageService)
    repo = Repository(mock_storage)
    
    repo.save({"id": 1, "name": "test"})
    
    assert mock_storage.store.called
```

### 5. Naming Conventions

❌ **Плохо:**
```python
def test_1() -> None:
    ...

def test_something() -> None:
    ...

class TestSuite:
    pass
```

✅ **Хорошо:**
```python
def test_session_creation_with_valid_parameters() -> None:
    ...

def test_session_creation_with_invalid_host_raises_error() -> None:
    ...

class TestSessionEntity:
    def test_session_creation(self) -> None:
        ...
    
    def test_session_validation(self) -> None:
        ...
```

### 6. Документирование тестов

Каждый тест должен иметь docstring:

```python
def test_observable_notifies_on_value_change() -> None:
    """Проверить что Observable уведомляет подписчиков при изменении значения.
    
    Сценарий:
    1. Создать Observable с начальным значением
    2. Подписать обработчик
    3. Изменить значение
    4. Проверить что обработчик был вызван с новым значением
    """
    obs = Observable(1)
    changes = []
    
    obs.subscribe(lambda x: changes.append(x))
    obs.value = 2
    
    assert changes == [2]
```

---

## Запуск тестов

### Все тесты

```bash
# Из корня репозитория
uv run --directory acp-client python -m pytest

# Или с полным путём
uv run --directory acp-client python -m pytest tests/
```

### Конкретный файл

```bash
uv run --directory acp-client python -m pytest tests/test_domain_entities.py
uv run --directory acp-client python -m pytest tests/test_tui_chat_view_mvvm.py
```

### Конкретный тест

```bash
uv run --directory acp-client python -m pytest \
  tests/test_domain_entities.py::TestSession::test_session_create
```

### Фильтрация по имени

```bash
# Запустить тесты содержащие "session" в имени
uv run --directory acp-client python -m pytest -k "session"

# Запустить тесты НЕ содержащие "slow"
uv run --directory acp-client python -m pytest -k "not slow"
```

### С coverage

```bash
# Терминальный отчёт
uv run --directory acp-client python -m pytest --cov=acp_client

# HTML отчёт
uv run --directory acp-client python -m pytest \
  --cov=acp_client \
  --cov-report=html
# Открыть acp-client/htmlcov/index.html
```

### Verbose режим

```bash
# Вывод на уровне каждого теста
uv run --directory acp-client python -m pytest -v

# С выводом print statements
uv run --directory acp-client python -m pytest -v -s
```

### Параллельное выполнение

```bash
# Требует pytest-xdist
# uv run --directory acp-client pip install pytest-xdist
# затем:
uv run --directory acp-client python -m pytest -n auto
```

### Категории тестов

```bash
# Только unit тесты domain
uv run --directory acp-client python -m pytest tests/test_domain_*.py

# Только unit тесты application
uv run --directory acp-client python -m pytest tests/test_application_*.py

# Только MVVM тесты
uv run --directory acp-client python -m pytest tests/test_tui_*_mvvm.py

# Только integration тесты
uv run --directory acp-client python -m pytest tests/test_integration_*.py

# Исключить медленные integration тесты
uv run --directory acp-client python -m pytest -k "not integration"
```

### Проверка с coverage drop

```bash
# Провалить тесты если покрытие упало ниже 80%
uv run --directory acp-client python -m pytest \
  --cov=acp_client \
  --cov-fail-under=80
```

---

## Отладка тестов

### pytest -v -s (вывод print)

```bash
uv run --directory acp-client python -m pytest -v -s tests/test_something.py
```

В тесте:
```python
def test_something() -> None:
    value = calculate()
    print(f"Calculated value: {value}")  # Будет выведено с -s
    assert value == expected
```

### pytest --pdb (интерактивный debugger)

```bash
# Остановиться в debugger при ошибке теста
uv run --directory acp-client python -m pytest --pdb tests/test_something.py
```

В тесте:
```python
def test_something() -> None:
    value = calculate()
    breakpoint()  # Остановиться здесь
    assert value == expected
```

Команды в pdb:
- `n` (next) - следующая строка
- `s` (step) - войти в функцию
- `c` (continue) - продолжить выполнение
- `p variable` - напечатать переменную
- `l` (list) - показать текущий код
- `pp variable` - красиво напечатать переменную

### pytest -x (остановиться на первой ошибке)

```bash
# Остановиться после первого failing теста
uv run --directory acp-client python -m pytest -x tests/

# Остановиться после 3 ошибок
uv run --directory acp-client python -m pytest --maxfail=3 tests/
```

### pytest --tb=short (краткий traceback)

```bash
# Полный traceback (default)
uv run --directory acp-client python -m pytest --tb=long

# Краткий traceback
uv run --directory acp-client python -m pytest --tb=short

# Очень краткий
uv run --directory acp-client python -m pytest --tb=line

# Без traceback
uv run --directory acp-client python -m pytest --tb=no
```

### Логирование в тестах

```python
import logging
import pytest

@pytest.fixture
def caplog(caplog):
    """Capture logs в тестах."""
    caplog.set_level(logging.DEBUG)
    return caplog

@pytest.mark.asyncio
async def test_with_logging(caplog) -> None:
    """Тест с логированием."""
    logger = logging.getLogger("test")
    
    logger.info("Test started")
    result = await some_operation()
    logger.debug(f"Result: {result}")
    
    # Проверить что логи содержат ожидаемые сообщения
    assert "Test started" in caplog.text
    assert "Result:" in caplog.text
```

---

## CI/CD интеграция

### Запуск в GitHub Actions

Пример workflow файла (`.github/workflows/test.yml`):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install uv
        run: pip install uv
      
      - name: Run tests
        run: uv run --directory acp-client python -m pytest
      
      - name: Generate coverage report
        run: |
          uv run --directory acp-client python -m pytest \
            --cov=acp_client \
            --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./acp-client/coverage.xml
```

### Проверка в Makefile

```bash
# Из acp-client/ директории:
make test              # Запустить тесты
make test-coverage     # Тесты с coverage
make test-verbose      # Verbose вывод
```

---

## Типичные проблемы и решения

### Проблема 1: Async тесты не работают

❌ **Ошибка:**
```
RuntimeError: no running event loop
```

✅ **Решение:** Использовать декоратор `@pytest.mark.asyncio`

```python
@pytest.mark.asyncio
async def test_async_operation() -> None:
    result = await some_async_function()
    assert result == expected
```

### Проблема 2: Моки не работают как ожидается

❌ **Проблема:**
```python
mock_obj = Mock()
mock_obj.method()  # Вернёт новый Mock, не None!
assert mock_obj.method() is None  # Провалится
```

✅ **Решение:** Явно установить return_value

```python
mock_obj = Mock()
mock_obj.method.return_value = None
assert mock_obj.method() is None  # ✓
```

### Проблема 3: Тесты зависят друг от друга

❌ **Проблема:**
```python
class TestUser:
    user = None
    
    def test_create(self):
        TestUser.user = User.create("John")
    
    def test_email(self):
        # Зависит от test_create!
        assert TestUser.user.email == "john@example.com"
```

✅ **Решение:** Использовать fixtures для изоляции

```python
class TestUser:
    @pytest.fixture
    def user(self):
        return User.create("John")
    
    def test_create(self, user):
        assert user.name == "John"
    
    def test_email(self, user):
        user.set_email("john@example.com")
        assert user.email == "john@example.com"
```

### Проблема 4: Observable tests не уведомляют

❌ **Проблема:**
```python
obs = Observable([1, 2, 3])
changes = []
obs.subscribe(lambda x: changes.append(x))

obs.value = [1, 2, 3]  # Одинаковое значение
assert len(changes) == 1  # Провалится, будет 0
```

✅ **Решение:** Observable не уведомляет если значение не изменилось

```python
obs = Observable([1, 2, 3])
changes = []
obs.subscribe(lambda x: changes.append(x))

obs.value = [1, 2, 3, 4]  # Другое значение
assert len(changes) == 1  # ✓
```

### Проблема 5: Медленные тесты

❌ **Проблема:** Использование real компонентов или sleep

```python
def test_timeout() -> None:
    import time
    time.sleep(5)  # Очень медленно!
    assert True
```

✅ **Решение:** Использовать моки или asyncio.sleep с timeout

```python
@pytest.mark.asyncio
async def test_timeout() -> None:
    import asyncio
    
    # Быстро и правильно
    async def operation() -> bool:
        await asyncio.sleep(0.01)  # Микросекунды
        return True
    
    result = await asyncio.wait_for(operation(), timeout=1.0)
    assert result
```

### Проблема 6: Невозможно импортировать модули из src

❌ **Ошибка:**
```
ModuleNotFoundError: No module named 'acp_client'
```

✅ **Решение:** pyproject.toml должен содержать

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "../acp-server/src"]
```

---

## Заключение

Тестирование в acp-client следует многоуровневому подходу:

1. **Unit тесты** - быстрые, изолированные, по слоям
2. **MVVM тесты** - тестирование связки UI + логики
3. **Integration тесты** - проверка workflows с реальным сервером

Все тесты:
- Следуют AAA паттерну (Arrange-Act-Assert)
- Имеют понятные имена и docstrings
- Используют fixtures для изоляции
- Проверяют одно логическое действие

Для запуска и разработки используйте:

```bash
# Все тесты
uv run --directory acp-client python -m pytest

# С coverage
uv run --directory acp-client python -m pytest --cov=acp_client -v

# С отладкой
uv run --directory acp-client python -m pytest -v -s --tb=short
```
