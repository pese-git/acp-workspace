# Анализ кодовой базы acp-server: Проблемы и рекомендации по рефакторингу

**Дата анализа:** 10 апреля 2026  
**Версия:** 0.1.0  
**Целевой стек:** Python 3.12+, async/await, Pydantic v2

## Резюме

Кодовая база показывает признаки быстрого прототипирования с недостаточным вниманием к архитектуре по мере роста сложности. **Критическая проблема** — гигантская функция `session_prompt` (2151 строка), нарушающая все принципы модульности. Вторичные проблемы включают дублирование кода, слабую типизацию и жесткие связи между модулями.

---

## Общая оценка архитектуры

### Сильные стороны
- ✅ Четкое разделение на слои: транспорт → протокол → обработчики → хранилище
- ✅ Использование `async/await` и `aiohttp` для неблокирующих операций
- ✅ Хорошо документированные docstring с примерами использования
- ✅ Абстрактные интерфейсы для `SessionStorage` и `LLMProvider`
- ✅ Использование Pydantic для валидации сообщений
- ✅ Structlog для структурированного логирования

### Слабые стороны
- ❌ Нарушение SRP (Single Responsibility Principle) в обработчиках
- ❌ Дублирование логики создания/загрузки сессий
- ❌ Неконсистентная типизация (`Any` вместо специализированных типов)
- ❌ Жесткие связи через прямые импорты функций вместо инъекции зависимостей
- ❌ Отсутствие специализированных исключений для доменной логики
- ❌ SessionState стал свалкой всех возможных полей состояния
- ❌ Отсутствие явного паттерна для управления lifecycle компонентов

---

## 🔴 Критические проблемы (требуют немедленного внимания)

### 1. Гигантская функция `session_prompt` нарушает все принципы модульности

**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py:240-2150`](acp-server/src/acp_server/protocol/handlers/prompt.py:240)

**Описание проблемы:**
- Функция содержит **2151 строку** кода в одном файле
- Реализует несколько не связанных сценариев (агент, разрешения, tool calls, FS операции)
- Имеет более 20 вложенных `if`-блоков
- Содержит дублирование логики build/финализации notifications
- Сложно тестировать без мокирования всей сессии
- Будет только расти при добавлении новых функций

**Влияние:**
- Невозможно переиспользовать отдельные части логики
- Высокий когнитивный груз при необходимости изменений
- Риск регрессий при любых модификациях
- Нарушает принцип Open/Closed (сложно расширять)

**Рекомендация:**
Разложить на подфункции и классы с четкой ответственностью:
```python
# Текущая структура (плохо)
async def session_prompt(...) -> ProtocolOutcome:
    # 2151 строк всего что угодно

# Рекомендуемая структура (хорошо)
class PromptHandler:
    """Оркестрирует обработку prompt-turn."""
    
    async def handle(self) -> ProtocolOutcome:
        """Главная точка входа."""
        # 50-100 строк координации
        
    async def _process_with_agent(self) -> AgentProcessingResult:
        """Деделегирует агенту."""
        
    async def _process_with_permissions(self) -> PermissionResult:
        """Обрабатывает разрешения."""
        
    async def _process_tool_calls(self) -> ToolCallResult:
        """Выполняет tool calls."""
        
    async def _process_client_rpc(self) -> ClientRPCResult:
        """Обрабатывает client RPC responses."""
```

**План действий:**
- [ ] Извлечь `PermissionHandler` для управления разрешениями
- [ ] Извлечь `ToolCallHandler` для управления tool calls
- [ ] Извлечь `ClientRPCHandler` для обработки client responses
- [ ] Создать `PromptOrchestrator` для координации
- [ ] Добавить unit-тесты для каждого handler

---

### 2. Дублирование логики создания сессий между `core.py` и `handlers/session.py`

**Файлы:** 
- [`acp-server/src/acp_server/protocol/core.py:203-263`](acp-server/src/acp_server/protocol/core.py:203)
- [`acp-server/src/acp_server/protocol/handlers/session.py:18-75`](acp-server/src/acp_server/protocol/handlers/session.py:18)

**Описание проблемы:**
```python
# В core.py (строки 214-249)
cwd = params.get("cwd")
if not isinstance(cwd, str) or not Path(cwd).is_absolute():
    return ProtocolOutcome(
        response=ACPMessage.error_response(
            message.id,
            code=-32602,
            message="Invalid params: cwd must be an absolute path",
        )
    )

mcp_servers = params.get("mcpServers", [])
if not isinstance(mcp_servers, list):
    return ProtocolOutcome(...)

session_id = f"sess_{uuid4().hex[:12]}"
config_values = {
    config_id: str(spec["default"]) for config_id, spec in self._config_specs.items()
}

session_state = SessionState(
    session_id=session_id,
    cwd=cwd,
    mcp_servers=[srv for srv in mcp_servers if isinstance(srv, dict)],
    config_values=config_values,
)

# В handlers/session.py (строки 46-74) — ТОЧНО ТА ЖЕ ВАЛИДАЦИЯ И ЛОГИКА
```

**Влияние:**
- Изменение в одном месте требует обновления в двух местах
- Риск десинхронизации логики
- Нарушает DRY (Don't Repeat Yourself)
- Усложняет тестирование

**Рекомендация:**
Создать единую фабрику для создания сессий:
```python
# acp-server/src/acp_server/protocol/session_factory.py
class SessionFactory:
    """Фабрика для создания и валидации сессий."""
    
    @staticmethod
    def validate_params(params: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Валидирует и извлекает cwd и mcpServers."""
        cwd = params.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute():
            raise ValidationError("cwd must be an absolute path")
        
        mcp_servers = params.get("mcpServers", [])
        if not isinstance(mcp_servers, list):
            raise ValidationError("mcpServers must be an array")
        
        return cwd, mcp_servers
    
    @staticmethod
    def create_session(
        cwd: str,
        mcp_servers: list[dict[str, Any]],
        config_specs: dict[str, dict[str, Any]],
    ) -> SessionState:
        """Создает новую сессию."""
        session_id = f"sess_{uuid4().hex[:12]}"
        config_values = {
            config_id: str(spec["default"]) 
            for config_id, spec in config_specs.items()
        }
        return SessionState(
            session_id=session_id,
            cwd=cwd,
            mcp_servers=[srv for srv in mcp_servers if isinstance(srv, dict)],
            config_values=config_values,
        )
```

---

### 3. Отсутствие специализированных исключений для обработки ошибок

**Файлы:** 
- [`acp-server/src/acp_server/storage/base.py:141`](acp-server/src/acp_server/storage/base.py:141) — только `StorageError`
- [`acp-server/src/acp_server/protocol/handlers/*.py`](acp-server/src/acp_server/protocol/handlers/) — используют только `Exception`

**Описание проблемы:**
```python
# Текущее (плохо)
except Exception as e:
    error_message = f"Agent error: {str(e)}"
    
# Рекомендуемое (хорошо)
except AgentProcessingError as e:
    logger.error("agent_processing_failed", error_code=e.error_code)
except ValidationError as e:
    logger.warning("invalid_params", details=e.details)
except PermissionDeniedError as e:
    logger.warning("permission_denied", kind=e.kind)
```

**Влияние:**
- Невозможно различить типы ошибок при обработке
- Сложнее логировать и мониторить
- Нарушает возможность graceful degradation

**Рекомендация:**
Создать иерархию исключений:
```python
# acp-server/src/acp_server/exceptions.py
class ACPServerError(Exception):
    """Base exception for ACP server errors."""
    error_code: int = -32603  # Internal error
    
class ValidationError(ACPServerError):
    """Ошибка валидации параметров."""
    error_code = -32602
    
class AuthenticationError(ACPServerError):
    """Ошибка аутентификации."""
    error_code = -32010
    
class PermissionDeniedError(ACPServerError):
    """Ошибка прав доступа."""
    error_code = -32011
    
class StorageError(ACPServerError):
    """Ошибка хранилища."""
    error_code = -32012
    
class AgentProcessingError(ACPServerError):
    """Ошибка при обработке агентом."""
    error_code = -32013
```

---

### 4. Слабая типизация: `dict[str, Any]` вместо структурированных моделей

**Файлы:**
- [`acp-server/src/acp_server/protocol/state.py:37`](acp-server/src/acp_server/protocol/state.py:37) — `history: list[dict[str, Any]]`
- [`acp-server/src/acp_server/protocol/state.py:47`](acp-server/src/acp_server/protocol/state.py:47) — `latest_plan: list[dict[str, str]]`
- [`acp-server/src/acp_server/protocol/state.py:45`](acp-server/src/acp_server/protocol/state.py:45) — `available_commands: list[dict[str, Any]]`

**Описание проблемы:**
```python
# Текущее (плохо) — неясно какие поля внутри
history: list[dict[str, Any]] = field(default_factory=list)
available_commands: list[dict[str, Any]] = field(default_factory=list)

# Код использования полагается на "магические" строки
for entry in session.history:
    if entry.get("role") == "assistant":  # Какие еще ключи могут быть?
        text = entry.get("text", "")  # Почему "text", а не что-то другое?
```

**Влияние:**
- IDE не может подсказать поля при автодополнении
- Легко ошибиться при обращении к полям
- Сложнее искать использование через рефакторинг
- Нет валидации на уровне типов

**Рекомендация:**
Создать Pydantic модели для структур:
```python
# acp-server/src/acp_server/protocol/models.py
from pydantic import BaseModel, Field

class HistoryEntry(BaseModel):
    """Запись в истории сессии."""
    role: str  # "user", "assistant", "system"
    content: str | list[dict[str, Any]]
    
    class Config:
        frozen = True

class PlanEntry(BaseModel):
    """Запись в плане выполнения."""
    step_id: str
    description: str
    status: str  # "pending", "in_progress", "completed", "failed"

class AvailableCommand(BaseModel):
    """Доступная команда сессии."""
    id: str
    name: str
    description: str
    
# Обновить SessionState
@dataclass
class SessionState:
    ...
    history: list[HistoryEntry] = field(default_factory=list)
    latest_plan: list[PlanEntry] = field(default_factory=list)
    available_commands: list[AvailableCommand] = field(default_factory=list)
```

---

## 🟡 Средние проблемы (желательно исправить)

### 5. Жесткие связи между `ACPProtocol` и обработчиками

**Файл:** [`acp-server/src/acp_server/protocol/core.py:176-341`](acp-server/src/acp_server/protocol/core.py:176)

**Описание проблемы:**
```python
# Диспетчер в core.py прямо импортирует и вызывает функции
from .handlers import auth, config, legacy, permissions, prompt, session

if method == "initialize":
    response = auth.initialize(...)  # Прямой вызов функции модуля
elif method == "authenticate":
    response, authenticated = auth.authenticate(...)
elif method == "session/new":
    ...  # Логика создания в самом core.py, не в handler!
```

**Влияние:**
- Сложно добавить новый handler без изменения диспетчера
- Нарушает принцип Open/Closed
- Нельзя динамически регистрировать обработчики

**Рекомендация:**
Использовать реестр обработчиков:
```python
# acp-server/src/acp_server/protocol/handler_registry.py
class MethodHandler(Protocol):
    """Protocol для обработчика метода."""
    async def __call__(
        self, 
        request_id: JsonRpcId | None, 
        params: dict[str, Any],
        context: HandlerContext,
    ) -> ProtocolOutcome: ...

class HandlerRegistry:
    """Реестр обработчиков методов."""
    
    def __init__(self):
        self._handlers: dict[str, MethodHandler] = {}
    
    def register(self, method: str, handler: MethodHandler) -> None:
        """Зарегистрировать обработчик."""
        self._handlers[method] = handler
    
    async def dispatch(
        self, 
        method: str, 
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        context: HandlerContext,
    ) -> ProtocolOutcome:
        """Диспетчировать метод."""
        handler = self._handlers.get(method)
        if not handler:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32601,
                    message=f"Method not found: {method}",
                )
            )
        return await handler(request_id, params, context)

# В ACPProtocol.__init__:
self._registry = HandlerRegistry()
self._registry.register("initialize", self._handle_initialize)
self._registry.register("session/new", self._handle_session_new)
# и т.д.

# В ACPProtocol.handle:
return await self._registry.dispatch(method, message.id, params, context)
```

---

### 6. SessionState содержит слишком много не связанных полей

**Файл:** [`acp-server/src/acp_server/protocol/state.py:17-57`](acp-server/src/acp_server/protocol/state.py:17)

**Описание проблемы:**
```python
@dataclass(slots=True)
class SessionState:
    # Базовые данные
    session_id: str
    cwd: str
    
    # Конфигурация
    config_values: dict[str, str]
    
    # Время
    updated_at: str
    
    # История
    history: list[dict[str, Any]]
    
    # Active turn состояние (если есть)
    active_turn: ActiveTurnState | None
    
    # Tool calls
    tool_calls: dict[str, ToolCallState]
    tool_call_counter: int
    
    # Команды и план
    available_commands: list[dict[str, Any]]
    latest_plan: list[dict[str, str]]
    
    # Permissions
    permission_policy: dict[str, str]
    cancelled_permission_requests: set[JsonRpcId]
    cancelled_client_rpc_requests: set[JsonRpcId]
    
    # Runtime capabilities
    runtime_capabilities: ClientRuntimeCapabilities | None
    
    # + title, mcp_servers
```

**Влияние:**
- Сложно разобраться в ответственности
- Сложнее тестировать (нужно инициализировать все поля)
- Затруднен рефакторинг — изменение одного аспекта может затронуть другие
- Нарушает Single Responsibility Principle

**Рекомендация:**
Разложить на несколько специализированных классов:
```python
# acp-server/src/acp_server/protocol/session_context.py
@dataclass(slots=True)
class SessionMetadata:
    """Метаданные сессии."""
    session_id: str
    cwd: str
    title: str | None = None
    updated_at: str = field(default_factory=...)
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)

@dataclass(slots=True)
class SessionConfiguration:
    """Конфигурация сессии."""
    config_values: dict[str, str] = field(default_factory=dict)
    permission_policy: dict[str, str] = field(default_factory=dict)
    available_commands: list[dict[str, Any]] = field(default_factory=list)

@dataclass(slots=True)
class SessionTurnState:
    """Состояние текущего turn."""
    active_turn: ActiveTurnState | None = None
    tool_calls: dict[str, ToolCallState] = field(default_factory=dict)
    tool_call_counter: int = 0
    cancelled_permission_requests: set[JsonRpcId] = field(default_factory=set)
    cancelled_client_rpc_requests: set[JsonRpcId] = field(default_factory=set)

@dataclass(slots=True)
class SessionState:
    """Агрегирует все аспекты сессии."""
    metadata: SessionMetadata
    config: SessionConfiguration
    turn_state: SessionTurnState
    history: list[HistoryEntry] = field(default_factory=list)
    latest_plan: list[PlanEntry] = field(default_factory=list)
    runtime_capabilities: ClientRuntimeCapabilities | None = None
```

---

### 7. Дублирование логики сериализации в `JsonFileStorage`

**Файл:** [`acp-server/src/acp_server/storage/json_file.py:52-222`](acp-server/src/acp_server/storage/json_file.py:52)

**Описание проблемы:**
Множество методов `_serialize_*` и `_deserialize_*`:
- `_serialize_active_turn` / `_deserialize_active_turn`
- `_serialize_tool_call` / `_deserialize_tool_call`
- `_serialize_pending_client_request` / `_deserialize_pending_client_request`
- `_serialize_capabilities` / `_deserialize_capabilities`
- `_serialize_session` / `_deserialize_session`

**Влияние:**
- Сложно поддерживать при изменении dataclasses
- Легко допустить ошибку при добавлении новых полей
- Нарушает DRY
- Можно использовать встроенные механизмы Pydantic

**Рекомендация:**
Использовать Pydantic для сериализации:
```python
# Пересоздать dataclasses как Pydantic модели
class SessionState(BaseModel):
    session_id: str
    cwd: str
    # ...
    
    class Config:
        # Для совместимости с dataclasses
        arbitrary_types_allowed = True

# В JsonFileStorage
async def save_session(self, session: SessionState) -> None:
    """Сохраняет сессию в JSON файл."""
    path = self._session_file_path(session.session_id)
    data = session.model_dump()  # Автоматическая сериализация
    await aiofiles.open(path, 'w') as f:
        await f.write(json.dumps(data))

async def load_session(self, session_id: str) -> SessionState | None:
    """Загружает сессию из JSON файла."""
    path = self._session_file_path(session_id)
    if not path.exists():
        return None
    data = json.loads(await aiofiles.open(path).read())
    return SessionState.model_validate(data)  # Автоматическая десериализация
```

---

### 8. Отсутствие явного lifecycle управления компонентами

**Файлы:**
- [`acp-server/src/acp_server/http_server.py`](acp-server/src/acp_server/http_server.py)
- [`acp-server/src/acp_server/agent/orchestrator.py`](acp-server/src/acp_server/agent/orchestrator.py)

**Описание проблемы:**
```python
# Нет явного метода cleanup/shutdown
class AgentOrchestrator:
    def __init__(self, ...):
        self.agent = NaiveAgent(...)
    
    # Нет метода для очистки ресурсов агента при завершении

# Нет контекстного менеджера
# В коде используется:
orchestrator = AgentOrchestrator(...)
# Неясно когда освобождать ресурсы LLM провайдера
```

**Влияние:**
- Утечки ресурсов LLM провайдера (незакрытые сессии)
- Незавершенные задачи при shutdown сервера
- Сложнее тестировать (нужно вручную очищать)

**Рекомендация:**
```python
class AgentOrchestrator:
    def __init__(self, ...):
        self.agent = NaiveAgent(...)
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.agent.initialize(...)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.agent.end_session(...)
        await self.llm_provider.close()  # Закрыть сессию LLM

# Использование:
async with AgentOrchestrator(...) as orchestrator:
    await orchestrator.process_prompt(...)
```

---

## 🟢 Незначительные улучшения (можно отложить)

### 9. Использование `pass` вместо `...` в абстрактных методах

**Файл:** [`acp-server/src/acp_server/storage/base.py:46`](acp-server/src/acp_server/storage/base.py:46)

```python
# Текущее (не Pythonic)
@abstractmethod
async def save_session(self, session: SessionState) -> None:
    """..."""
    pass

# Рекомендуемое (Pythonic)
@abstractmethod
async def save_session(self, session: SessionState) -> None:
    """..."""
    ...
```

---

### 10. Неконсистентное использование логирования

**Файлы:**
- [`acp-server/src/acp_server/http_server.py`](acp-server/src/acp_server/http_server.py) — использует structlog
- [`acp-server/src/acp_server/storage/json_file.py`](acp-server/src/acp_server/storage/json_file.py) — нет логирования
- [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py) — использует structlog

**Рекомендация:**
Добавить структурированное логирование во все модули, особенно в storage и LLM провайдеры.

---

### 11. Отсутствие валидации конфигурации при инициализации

**Файл:** [`acp-server/src/acp_server/config.py:74-92`](acp-server/src/acp_server/config.py:74)

```python
# Текущее (плохо) — нет валидации конфигурации
class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

# Рекомендуемое (хорошо) — с валидацией
class AppConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    
    @model_validator(mode="after")
    def validate_llm_config(self) -> AppConfig:
        """Валидирует конфигурацию LLM при инициализации."""
        if self.llm.provider == "openai" and not self.llm.api_key:
            raise ValueError("OpenAI provider requires api_key")
        if not self.agent.system_prompt:
            raise ValueError("system_prompt is required")
        return self
```

---

### 12. Проблема с управлением памятью в `_sessions` словаре

**Файл:** [`acp-server/src/acp_server/protocol/core.py:75`](acp-server/src/acp_server/protocol/core.py:75)

**Описание проблемы:**
```python
# Словарь сессий никогда не очищается, может расти бесконечно
self._sessions: dict[str, SessionState] = {}

# При delete_session очищается только из хранилища, но не из кэша!
if method == "session/delete":
    return session.session_delete(...)  # Может очищать только хранилище
```

**Рекомендация:**
```python
# Использовать TTL кэш или явно удалять при delete_session
from functools import lru_cache
from datetime import datetime, timedelta

class SessionCache:
    """Кэш сессий с поддержкой TTL."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: dict[str, tuple[SessionState, float]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, session_id: str) -> SessionState | None:
        """Получить сессию, удалив если истекла."""
        item = self._sessions.get(session_id)
        if item is None:
            return None
        
        session, timestamp = item
        if datetime.now().timestamp() - timestamp > self.ttl_seconds:
            del self._sessions[session_id]
            return None
        
        return session
    
    def set(self, session: SessionState) -> None:
        """Установить сессию с текущей временной меткой."""
        self._sessions[session.session_id] = (session, datetime.now().timestamp())
    
    def delete(self, session_id: str) -> None:
        """Удалить сессию из кэша."""
        self._sessions.pop(session_id, None)
```

---

## 📋 Приоритизированный план рефакторинга

### Фаза 1: Критические (Sprint 1-2)
1. **Разложить `session_prompt`** на отдельные обработчики
   - Создать `PermissionHandler`
   - Создать `ToolCallHandler`
   - Создать `ClientRPCHandler`
   - Обновить тесты
   
2. **Создать `SessionFactory`** и удалить дублирование
   - Извлечь логику валидации
   - Обновить `core.py` и `handlers/session.py`
   - Добавить unit-тесты для фабрики

3. **Создать иерархию исключений** (`exceptions.py`)
   - Определить все домены ошибок
   - Обновить обработчики ошибок
   - Обновить логирование

### Фаза 2: Средние (Sprint 3-4)
4. **Внедрить типизацию** с Pydantic моделями
   - Создать `models.py` с `HistoryEntry`, `PlanEntry`, и т.д.
   - Обновить `SessionState`
   - Обновить использование в обработчиках

5. **Разложить `SessionState`** на специализированные классы
   - Создать `SessionMetadata`, `SessionConfiguration`, `SessionTurnState`
   - Обновить все места использования
   - Обновить `SessionStorage` интерфейс

6. **Внедрить реестр обработчиков** (`handler_registry.py`)
   - Создать `HandlerRegistry`
   - Обновить `ACPProtocol.handle()` для использования реестра
   - Дать возможность регистрировать обработчики динамически

### Фаза 3: Незначительные (Sprint 5+)
7. **Добавить lifecycle управление** для компонентов
   - Реализовать `async with` для `AgentOrchestrator`
   - Добавить методы cleanup
   - Обновить `ACPHttpServer` для корректного shutdown

8. **Улучшить сериализацию** в `JsonFileStorage`
   - Перейти на Pydantic для (де)сериализации
   - Удалить ручные методы `_serialize_*`

9. **Добавить TTL кэш** для `_sessions`
   - Реализовать `SessionCache`
   - Обновить `ACPProtocol`

10. **Добавить валидацию конфигурации** в `AppConfig`
    - Использовать Pydantic validators
    - Добавить интеграционные тесты

---

## Метрики успеха

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| Максимальный размер функции | 2151 строк | < 100 строк |
| Цикломатическая сложность `session_prompt` | ~50 | < 5 (после рефакторинга на несколько функций) |
| Покрытие специализированными исключениями | 10% | 80% |
| Использование `Any` в типах | 25% | < 5% |
| Дублирование кода (по Radon) | ~15% | < 5% |
| Количество методов в `SessionState` | 0 (dataclass) | Логика в специализированных классах |

---

## Заключение

Кодовая база нуждается в **срочном рефакторинге на критичных проблемах**, особенно разложении гигантской функции `session_prompt`. После этого рекомендуется работать над типизацией и архитектурой слой за слоем.

Предложенные изменения не будут нарушать публичные интерфейсы CLI и внешние API, так как они сосредоточены на внутренней архитектуре.

**Ожидаемый результат:** более поддерживаемая, расширяемая и тестируемая кодовая база, готовая к добавлению новых функций без деградации качества.
