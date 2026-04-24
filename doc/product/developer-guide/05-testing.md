# Тестирование

> Руководство по тестированию CodeLab.

## Обзор

CodeLab использует pytest для тестирования. Проект содержит ~1800 тестов, покрывающих клиент и сервер.

```
codelab/tests/
├── client/           # Тесты клиента (~1100)
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── presentation/
│   └── tui/
├── server/           # Тесты сервера (~700)
│   ├── protocol/
│   ├── agent/
│   ├── tools/
│   ├── storage/
│   └── e2e/
└── conftest.py       # Общие fixtures
```

## Запуск тестов

### Все тесты

```bash
# Через Makefile
make check

# Или напрямую
cd codelab
uv run python -m pytest
```

### Отдельные модули

```bash
# Тесты клиента
uv run python -m pytest tests/client/

# Тесты сервера
uv run python -m pytest tests/server/

# Конкретный файл
uv run python -m pytest tests/server/test_protocol.py

# Конкретный тест
uv run python -m pytest tests/server/test_protocol.py::TestACPProtocol::test_handle_initialize
```

### Опции pytest

```bash
# Подробный вывод
uv run python -m pytest -v

# Остановка на первой ошибке
uv run python -m pytest -x

# Параллельное выполнение
uv run python -m pytest -n auto

# С покрытием
uv run python -m pytest --cov=codelab --cov-report=html

# Только помеченные тесты
uv run python -m pytest -m "not slow"
```

## Структура тестов

### Naming conventions

```python
# Файлы: test_<module>.py
# Классы: Test<Class>
# Методы: test_<behavior>

# Пример
class TestChatViewModel:
    def test_send_message_updates_loading_state(self): ...
    def test_send_message_calls_use_case(self): ...
    def test_error_is_set_on_failure(self): ...
```

### AAA паттерн

```python
def test_create_session(self):
    # Arrange (подготовка)
    storage = AsyncMock(spec=SessionStorage)
    handler = SessionHandler(storage)
    message = ACPMessage(method="session/new", params={"title": "Test"})
    
    # Act (действие)
    outcome = await handler.handle(message)
    
    # Assert (проверка)
    assert outcome.error is None
    assert "session_id" in outcome.response
    storage.save.assert_called_once()
```

## Unit тесты

### Тестирование ViewModels

```python
import pytest
from unittest.mock import AsyncMock, Mock

from codelab.client.presentation.chat_view_model import ChatViewModel


class TestChatViewModel:
    """Unit тесты ChatViewModel."""
    
    @pytest.fixture
    def event_bus(self) -> Mock:
        """Mock EventBus."""
        return Mock()
    
    @pytest.fixture
    def send_prompt_use_case(self) -> AsyncMock:
        """Mock SendPromptUseCase."""
        return AsyncMock()
    
    @pytest.fixture
    def view_model(self, event_bus, send_prompt_use_case) -> ChatViewModel:
        """Создание тестируемого ViewModel."""
        return ChatViewModel(
            event_bus=event_bus,
            send_prompt_use_case=send_prompt_use_case,
        )
    
    async def test_initial_state(self, view_model):
        """Проверка начального состояния."""
        assert view_model.messages.get() == []
        assert view_model.is_loading.get() is False
        assert view_model.error.get() is None
    
    async def test_send_message_sets_loading(self, view_model):
        """Проверка что send_message устанавливает is_loading."""
        # Act
        task = asyncio.create_task(view_model.send_message("Hello"))
        await asyncio.sleep(0)  # Позволяем таске начаться
        
        # Assert
        assert view_model.is_loading.get() is True
        
        await task
        assert view_model.is_loading.get() is False
    
    async def test_send_message_calls_use_case(self, view_model, send_prompt_use_case):
        """Проверка вызова use case."""
        await view_model.send_message("Hello World")
        
        send_prompt_use_case.execute.assert_called_once_with("Hello World")
    
    async def test_send_message_handles_error(self, view_model, send_prompt_use_case):
        """Проверка обработки ошибок."""
        send_prompt_use_case.execute.side_effect = Exception("Network error")
        
        await view_model.send_message("Hello")
        
        assert view_model.error.get() == "Network error"
        assert view_model.is_loading.get() is False
```

### Тестирование Handlers

```python
class TestSessionHandler:
    """Unit тесты SessionHandler."""
    
    @pytest.fixture
    def storage(self) -> AsyncMock:
        return AsyncMock(spec=SessionStorage)
    
    @pytest.fixture
    def handler(self, storage) -> SessionHandler:
        return SessionHandler(storage)
    
    async def test_new_session_creates_session(self, handler, storage):
        """Тест создания сессии."""
        message = ACPMessage(
            method="session/new",
            params={"title": "Test Session"},
        )
        
        outcome = await handler.handle(message)
        
        assert outcome.error is None
        assert "session_id" in outcome.response
        assert outcome.response["title"] == "Test Session"
        storage.save.assert_called_once()
    
    async def test_load_session_returns_session(self, handler, storage):
        """Тест загрузки существующей сессии."""
        # Arrange
        session = SessionState(id="test-id", title="Existing")
        storage.load.return_value = session
        
        message = ACPMessage(
            method="session/load",
            params={"session_id": "test-id"},
        )
        
        # Act
        outcome = await handler.handle(message)
        
        # Assert
        assert outcome.error is None
        assert outcome.response["session_id"] == "test-id"
    
    async def test_load_session_not_found(self, handler, storage):
        """Тест загрузки несуществующей сессии."""
        storage.load.return_value = None
        
        message = ACPMessage(
            method="session/load",
            params={"session_id": "unknown"},
        )
        
        outcome = await handler.handle(message)
        
        assert outcome.error is not None
        assert "not found" in str(outcome.error.message).lower()
```

## Интеграционные тесты

### Тестирование с реальным Storage

```python
class TestStorageIntegration:
    """Интеграционные тесты хранилища."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path) -> Path:
        """Временная директория для тестов."""
        return tmp_path / "sessions"
    
    @pytest.fixture
    def storage(self, temp_dir) -> JsonFileStorage:
        """Реальное хранилище."""
        return JsonFileStorage(temp_dir)
    
    async def test_save_and_load(self, storage):
        """Тест сохранения и загрузки."""
        session = SessionState(
            id="test-1",
            title="Test",
            messages=[Message(role="user", content="Hello")],
        )
        
        # Save
        await storage.save(session)
        
        # Load
        loaded = await storage.load("test-1")
        
        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.title == session.title
        assert len(loaded.messages) == 1
    
    async def test_list_all(self, storage):
        """Тест получения списка сессий."""
        # Create sessions
        for i in range(3):
            await storage.save(SessionState(id=f"session-{i}"))
        
        # List
        sessions = await storage.list_all()
        
        assert len(sessions) == 3
```

### Тестирование Protocol

```python
class TestProtocolIntegration:
    """Интеграционные тесты протокола."""
    
    @pytest.fixture
    async def protocol(self) -> ACPProtocol:
        """Создание протокола с реальными компонентами."""
        storage = InMemoryStorage()
        config = AppConfig()
        
        notifications = []
        
        async def send_callback(msg):
            notifications.append(msg)
        
        return ACPProtocol(
            storage=storage,
            config=config,
            send_callback=send_callback,
        )
    
    async def test_full_session_lifecycle(self, protocol):
        """Тест полного жизненного цикла сессии."""
        # Initialize
        outcome = await protocol.handle(ACPMessage(
            method="initialize",
            params={"client_info": {"name": "test"}},
        ))
        assert outcome.error is None
        
        # Create session
        outcome = await protocol.handle(ACPMessage(
            method="session/new",
            params={"title": "Test"},
        ))
        assert outcome.error is None
        session_id = outcome.response["session_id"]
        
        # Load session
        outcome = await protocol.handle(ACPMessage(
            method="session/load",
            params={"session_id": session_id},
        ))
        assert outcome.error is None
        assert outcome.response["session_id"] == session_id
```

## E2E тесты

### Тестирование WebSocket

```python
class TestE2EWebSocket:
    """E2E тесты через WebSocket."""
    
    @pytest.fixture
    async def server(self):
        """Запуск тестового сервера."""
        server = ACPHttpServer(host="127.0.0.1", port=0)
        task = asyncio.create_task(server.run())
        
        # Ждем запуска
        await asyncio.sleep(0.1)
        
        yield server
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.fixture
    async def ws_client(self, server):
        """WebSocket клиент."""
        async with aiohttp.ClientSession() as session:
            url = f"ws://{server.host}:{server.port}/acp/ws"
            async with session.ws_connect(url) as ws:
                yield ws
    
    async def test_initialize(self, ws_client):
        """Тест инициализации."""
        await ws_client.send_json({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"client_info": {"name": "test"}},
            "id": 1,
        })
        
        response = await ws_client.receive_json()
        
        assert "result" in response
        assert response["id"] == 1
    
    async def test_create_and_prompt_session(self, ws_client):
        """Тест создания сессии и отправки промпта."""
        # Initialize
        await ws_client.send_json({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {},
            "id": 1,
        })
        await ws_client.receive_json()
        
        # Create session
        await ws_client.send_json({
            "jsonrpc": "2.0",
            "method": "session/new",
            "params": {},
            "id": 2,
        })
        response = await ws_client.receive_json()
        session_id = response["result"]["session_id"]
        
        # Send prompt
        await ws_client.send_json({
            "jsonrpc": "2.0",
            "method": "session/prompt",
            "params": {
                "session_id": session_id,
                "prompt": {"text": "Hello"},
            },
            "id": 3,
        })
        
        # Receive updates
        updates = []
        while True:
            msg = await asyncio.wait_for(
                ws_client.receive_json(),
                timeout=5.0,
            )
            updates.append(msg)
            if "result" in msg and msg.get("id") == 3:
                break
        
        assert len(updates) > 0
```

## Fixtures

### Общие fixtures

```python
# tests/conftest.py

import pytest
from pathlib import Path


@pytest.fixture
def project_root() -> Path:
    """Корень проекта."""
    return Path(__file__).parent.parent


@pytest.fixture
def test_data_dir(project_root) -> Path:
    """Директория с тестовыми данными."""
    return project_root / "tests" / "data"


@pytest.fixture
async def mock_transport() -> AsyncMock:
    """Mock транспорта."""
    transport = AsyncMock()
    transport.send.return_value = None
    return transport


@pytest.fixture
def sample_session() -> SessionState:
    """Пример сессии для тестов."""
    return SessionState(
        id="test-session-id",
        title="Test Session",
        created_at=datetime.utcnow(),
        messages=[
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there!"),
        ],
    )
```

### Fixtures для LLM

```python
@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    """Mock LLM провайдера."""
    provider = AsyncMock(spec=LLMProvider)
    
    async def mock_stream(*args, **kwargs):
        yield LLMChunk(text="Hello, ")
        yield LLMChunk(text="how can I help?")
    
    provider.stream.return_value = mock_stream()
    return provider
```

## Маркеры

### Определение маркеров

```python
# pytest.ini или pyproject.toml

[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "e2e: marks tests as end-to-end tests",
]
```

### Использование маркеров

```python
import pytest


@pytest.mark.slow
async def test_complex_operation():
    """Медленный тест."""
    ...


@pytest.mark.integration
async def test_with_real_database():
    """Интеграционный тест."""
    ...


@pytest.mark.e2e
async def test_full_user_flow():
    """E2E тест."""
    ...


# Запуск без медленных тестов
# uv run python -m pytest -m "not slow"
```

## Проверка качества

### Линтинг

```bash
# Ruff
uv run ruff check .

# С исправлением
uv run ruff check --fix .
```

### Type checking

```bash
# Ty (или mypy)
uv run ty check
```

### Полная проверка

```bash
# Makefile
make check

# Запускает:
# 1. ruff check
# 2. ty check
# 3. pytest
```

## Best Practices

### ✅ Рекомендуется

1. **Один assert на тест** (когда возможно)
2. **Описательные имена тестов**
3. **AAA паттерн** (Arrange-Act-Assert)
4. **Изоляция тестов** — тесты не должны зависеть друг от друга
5. **Mock внешних зависимостей**

### ⚠️ Избегать

1. Тестов без assertions
2. Зависимостей между тестами
3. Реальных сетевых вызовов в unit тестах
4. Хардкода путей и портов

## Coverage

### Генерация отчета

```bash
uv run python -m pytest --cov=codelab --cov-report=html
open htmlcov/index.html
```

### Минимальное покрытие

```toml
# pyproject.toml
[tool.coverage.report]
fail_under = 80
```

## См. также

- [Архитектура](01-architecture.md) — структура проекта
- [Разработка клиента](02-client-development.md)
- [Разработка сервера](03-server-development.md)
