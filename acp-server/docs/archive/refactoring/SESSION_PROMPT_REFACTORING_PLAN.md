# Архитектурный план рефакторинга session_prompt

**Статус:** 📋 Проектирование  
**Дата создания:** 2026-04-11  
**Критичность:** 🔴 Критическая (2151 строк монолитного кода)  
**Целевой результат:** Разложение на специализированные обработчики с четкой ответственностью

---

## 📊 Резюме текущего состояния

### Проблема
- **Функция:** [`session_prompt`](acp-server/src/acp_server/protocol/handlers/prompt.py:243)
- **Размер:** 2151 строк в одном файле
- **Сложность:** Более 20 вложенных if-блоков
- **Ответственность:** Более 7 функциональных областей в одной функции
- **Тестируемость:** Крайне низкая (требует моков всей сессии)
- **Дублирование:** Повторяющиеся паттерны build/finalize notifications

### Области ответственности (текущие)
1. ✅ Валидация входных параметров (17 строк, lines 269-302)
2. ✅ Обработка через LLM-агента (6 строк, lines 304-312)
3. ✅ Управление life-cycle активного turn (8 строк, lines 314-323)
4. ✅ Извлечение prompt directives (15 строк, lines 325-339)
5. ✅ Построение update сообщений (190 строк, lines 341-531)
6. ✅ Управление history и метаданными (30 строк, lines 533-559)
7. ✅ Финализация turn-а (68 строк, lines 577-595)

Вспомогательные функции в том же файле (1380+ строк):
- Directives extraction и resolution (180 строк)
- Tool call management (150 строк)
- Client RPC preparation (300 строк)
- Permission handling (140 строк)
- Plan building (100 строк)
- State finalization functions (200+ строк)

---

## 🏗️ Целевая архитектура

### Принципы

```
┌─────────────────────────────────────────────────────────────────┐
│                      PromptOrchestrator                         │
│  (Главный оркестратор, координирует обработку prompt-turn)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│ PromptValidator│ │  AgentHandler  │ │ LegacyHandler  │
│  (Валидация)   │ │ (LLM агент)    │ │ (Legacy path)  │
└────────────────┘ └────────────────┘ └────────────────┘
        │                  │                  │
        │                  │         ┌────────┴─────────┐
        │                  │         │                  │
        ▼                  ▼         ▼                  ▼
    [Session]         [Session]  ┌─────────────────────────────┐
                                 │  DirectiveProcessor Layer   │
                                 └──────────────┬──────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼                           ▼                           ▼
            ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
            │ DirectiveResolver │     │  UpdateBuilder   │     │  StateManager    │
            │ (Парсинг slash)  │      │ (Notifications)  │     │ (History, meta)  │
            └──────────────────┘      └──────────────────┘      └──────────────────┘
                    │                           │                           │
                    ▼                           ▼                           ▼
            ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
            │ ToolCallHandler  │      │  PermissionMgr   │     │ TurnLifecycle    │
            │ (Tool call flow) │      │ (Permission req)  │     │  (Active turn)   │
            └──────────────────┘      └──────────────────┘      └──────────────────┘
                    │                           │
                    ▼                           ▼
            ┌──────────────────┐      ┌──────────────────┐
            │ ClientRPCHandler │      │  PlanBuilder     │
            │ (FS, Terminal)   │      │ (Plan entries)   │
            └──────────────────┘      └──────────────────┘
```

### Новые компоненты

#### 1. **PromptValidator** (Валидация и подготовка)
**Файл:** `acp-server/src/acp_server/protocol/handlers/prompt_validator.py`

**Ответственность:**
- Валидация sessionId, prompt array, content blocks
- Проверка состояния сессии (active_turn)
- Валидация prompt content (text, resource_link)

**Интерфейс:**
```python
class PromptValidator:
    def validate_input(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome | SessionState:
        """Валидирует входные параметры.
        
        Returns:
            SessionState - если валидно
            ProtocolOutcome - если ошибка
        """
    
    def validate_content(
        self,
        request_id: JsonRpcId | None,
        prompt: list[Any],
    ) -> ACPMessage | None:
        """Валидирует содержимое prompt."""
```

#### 2. **DirectiveResolver** (Извлечение директив)
**Файл:** `acp-server/src/acp_server/protocol/handlers/directive_resolver.py`

**Ответственность:**
- Парсинг slash-команд из текста (/tool, /plan, /fs-read, /term-run)
- Разрешение directive overrides из _meta
- Нормализация tool kinds и stop reasons
- Извлечение параметров из directives

**Интерфейс:**
```python
class DirectiveResolver:
    def resolve_directives(
        self,
        *,
        params: dict[str, Any],
        text_preview: str,
        supported_tool_kinds: set[str] | None = None,
    ) -> PromptDirectives:
        """Формирует finalized prompt directives."""
    
    def extract_slash_commands(
        self,
        text_preview: str,
        supported_tool_kinds: set[str],
    ) -> PromptDirectives:
        """Парсит slash-команды из текста."""
    
    def apply_meta_overrides(
        self,
        directives: PromptDirectives,
        raw_meta: dict[str, Any] | None,
    ) -> PromptDirectives:
        """Применяет structured overrides из _meta."""
```

#### 3. **ToolCallHandler** (Управление tool calls)
**Файл:** `acp-server/src/acp_server/protocol/handlers/tool_call_handler.py`

**Ответственность:**
- Проверка доступности tool runtime
- Создание tool call записей
- Построение tool call update notifications
- Управление статусом tool call (pending -> in_progress -> completed)

**Интерфейс:**
```python
class ToolCallHandler:
    def can_run_tools(self, session: SessionState) -> bool:
        """Проверяет доступность tool-runtime."""
    
    def create_tool_call(
        self,
        session: SessionState,
        title: str,
        kind: str,
    ) -> str:
        """Создает новый tool call, возвращает ID."""
    
    def build_tool_notifications(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> list[ACPMessage]:
        """Строит notifications для tool flow."""
    
    def update_tool_status(
        self,
        session: SessionState,
        tool_call_id: str,
        status: str,
        content: list[dict[str, Any]] | None = None,
    ) -> None:
        """Обновляет статус tool call с валидацией."""
    
    def cancel_active_tools(
        self,
        session: SessionState,
        session_id: str,
    ) -> list[ACPMessage]:
        """Отменяет все активные tool calls."""
```

#### 4. **PermissionManager** (Управление разрешениями)
**Файл:** `acp-server/src/acp_server/protocol/handlers/permission_manager.py`

**Ответственность:**
- Проверка mode (ask vs executor)
- Поиск remembered permissions
- Построение permission requests
- Построение policy-based execution updates

**Интерфейс:**
```python
class PermissionManager:
    def should_request_permission(
        self,
        session: SessionState,
        tool_kind: str,
    ) -> bool:
        """Проверяет, нужен ли permission request."""
    
    def get_remembered_permission(
        self,
        session: SessionState,
        tool_kind: str,
    ) -> str | None:
        """Возвращает 'allow', 'reject' или None."""
    
    def build_permission_request(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        tool_title: str,
        tool_kind: str,
    ) -> ACPMessage:
        """Строит permission request message."""
    
    def build_permission_updates(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        allowed: bool,
    ) -> list[ACPMessage]:
        """Строит updates после permission решения."""
```

#### 5. **ClientRPCHandler** (Обработка RPC запросов)
**Файл:** `acp-server/src/acp_server/protocol/handlers/client_rpc_handler.py`

**Ответственность:**
- Проверка доступности FS и Terminal capabilities
- Построение fs/read, fs/write, terminal/create requests
- Создание связанных tool calls и pending state

**Интерфейс:**
```python
class ClientRPCHandler:
    def can_use_fs_rpc(self, session: SessionState, kind: str) -> bool:
        """Проверяет доступность fs/* RPC."""
    
    def can_use_terminal_rpc(self, session: SessionState) -> bool:
        """Проверяет доступность terminal/* RPC."""
    
    def prepare_fs_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит fs/* request и tool call."""
    
    def prepare_terminal_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит terminal/* request и tool call."""
```

#### 6. **PlanBuilder** (Построение плана)
**Файл:** `acp-server/src/acp_server/protocol/handlers/plan_builder.py`

**Ответственность:**
- Нормализация plan entries из directives
- Построение plan notifications
- Отправка plan updates

**Интерфейс:**
```python
class PlanBuilder:
    def normalize_plan_entries(
        self,
        raw_entries: Any,
    ) -> list[dict[str, str]] | None:
        """Нормализует plan entries."""
    
    def build_plan_entries(
        self,
        directives: PromptDirectives,
        text_preview: str,
    ) -> list[dict[str, str]]:
        """Строит plan entries."""
    
    def build_plan_notification(
        self,
        session_id: str,
        plan_entries: list[dict[str, str]],
    ) -> ACPMessage:
        """Строит plan notification."""
```

#### 7. **StateManager** (Управление состоянием сессии)
**Файл:** `acp-server/src/acp_server/protocol/handlers/state_manager.py`

**Ответственность:**
- Управление history
- Обновление metadata (title, updated_at)
- Построение session_info notifications
- Управление available_commands updates

**Интерфейс:**
```python
class StateManager:
    def update_history(
        self,
        session: SessionState,
        prompt: list[Any],
        agent_text: str,
    ) -> None:
        """Обновляет историю сессии."""
    
    def update_title_if_needed(
        self,
        session: SessionState,
        text_preview: str,
    ) -> bool:
        """Обновляет title, возвращает True если изменен."""
    
    def update_metadata(self, session: SessionState) -> None:
        """Обновляет updated_at и другие metadata."""
    
    def build_session_info_notification(
        self,
        session_id: str,
        title: str | None,
        updated_at: str | None,
    ) -> ACPMessage:
        """Строит session_info notification."""
    
    def build_commands_notification(
        self,
        session_id: str,
        available_commands: list[Any],
    ) -> ACPMessage:
        """Строит available_commands notification."""
```

#### 8. **TurnLifecycleManager** (Управление life-cycle turn-а)
**Файл:** `acp-server/src/acp_server/protocol/handlers/turn_lifecycle_manager.py`

**Ответственность:**
- Инициализация активного turn
- Определение фаз turn (running, waiting_tool_completion, waiting_permission, waiting_client_rpc)
- Финализация turn-а
- Проверка need to defer completion

**Интерфейс:**
```python
class TurnLifecycleManager:
    def initialize_turn(
        self,
        session: SessionState,
        request_id: JsonRpcId | None,
    ) -> ActiveTurnState:
        """Инициализирует новый active turn."""
    
    def should_defer_completion(
        self,
        session: SessionState,
        directives: PromptDirectives,
    ) -> bool:
        """Проверяет, нужно ли отложить завершение."""
    
    def finalize_turn(
        self,
        session: SessionState,
        stop_reason: str,
    ) -> ACPMessage | None:
        """Финализирует turn и возвращает response."""
    
    def update_turn_phase(
        self,
        session: SessionState,
        phase: str,
    ) -> None:
        """Обновляет текущую фазу turn-а."""
```

#### 9. **PromptOrchestrator** (Главный оркестратор)
**Файл:** `acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py`

**Ответственность:**
- Координация всех обработчиков
- Управление flow-ом обработки prompt
- Построение финального ProtocolOutcome
- Обработка error cases

**Интерфейс:**
```python
class PromptOrchestrator:
    def __init__(
        self,
        validator: PromptValidator,
        directive_resolver: DirectiveResolver,
        tool_handler: ToolCallHandler,
        permission_manager: PermissionManager,
        rpc_handler: ClientRPCHandler,
        plan_builder: PlanBuilder,
        state_manager: StateManager,
        lifecycle_manager: TurnLifecycleManager,
    ):
        """Инициализирует оркестратор с обработчиками."""
    
    async def handle_prompt(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        sessions: dict[str, SessionState],
        agent_orchestrator: AgentOrchestrator | None = None,
    ) -> ProtocolOutcome:
        """Главная точка входа для обработки prompt."""
    
    async def handle_with_agent(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        agent_orchestrator: AgentOrchestrator,
    ) -> ProtocolOutcome:
        """Обрабатывает prompt через LLM-агента."""
    
    async def handle_legacy(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome:
        """Обрабатывает prompt legacy path (без агента)."""
```

#### 10. **PromptCancellationHandler** (Отмена prompt-turn)
**Файл:** `acp-server/src/acp_server/protocol/handlers/prompt_cancellation_handler.py`

**Ответственность:**
- Обработка session/cancel
- Очистка pending requests
- Завершение активного turn
- Отмена tool calls

**Интерфейс:**
```python
class PromptCancellationHandler:
    def handle_cancellation(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome:
        """Обрабатывает session/cancel."""
    
    def cancel_pending_requests(
        self,
        session: SessionState,
        session_id: str,
    ) -> list[ACPMessage]:
        """Отменяет pending client requests."""
```

---

## 🔄 Поток данных

### Сценарий 1: Простой prompt (без tool, без RPC)

```
User Request
    ↓
PromptValidator.validate_input() ✓
    ↓
TurnLifecycleManager.initialize_turn()
    ↓
DirectiveResolver.resolve_directives()
    ↓
StateManager.update_history()
StateManager.update_title_if_needed()
StateManager.update_metadata()
    ↓
TurnLifecycleManager.should_defer_completion() → false
    ↓
StateManager.build_session_info_notification()
StateManager.build_commands_notification()
    ↓
TurnLifecycleManager.finalize_turn() → response
    ↓
ProtocolOutcome { response, notifications }
```

### Сценарий 2: Prompt с tool call (ask mode)

```
User Request
    ↓
PromptValidator.validate_input() ✓
    ↓
TurnLifecycleManager.initialize_turn()
    ↓
DirectiveResolver.resolve_directives()
    ↓
ToolCallHandler.can_run_tools() → true
ToolCallHandler.create_tool_call()
    ↓
PermissionManager.should_request_permission() → true
PermissionManager.get_remembered_permission() → null
PermissionManager.build_permission_request()
    ↓
TurnLifecycleManager.update_turn_phase("waiting_permission")
    ↓
TurnLifecycleManager.should_defer_completion() → true
    ↓
ProtocolOutcome { response: null, notifications }
   (response будет отправлена позже через complete_active_turn)
```

### Сценарий 3: Prompt с FS RPC

```
User Request → /fs-read /path/to/file
    ↓
PromptValidator.validate_input() ✓
    ↓
DirectiveResolver.resolve_directives()
    ↓
ClientRPCHandler.can_use_fs_rpc("fs_read") → true
ClientRPCHandler.prepare_fs_request()
    ↓
TurnLifecycleManager.update_turn_phase("waiting_client_rpc")
    ↓
ProtocolOutcome { response: null, notifications }
```

---

## 📋 План реализации по этапам

### Этап 1: Подготовка инфраструктуры (Priority: HIGH)
**Файлы для создания:**
- [ ] `acp-server/src/acp_server/protocol/handlers/prompt_validator.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/directive_resolver.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/base.py` (базовый класс для обработчиков)

**Задачи:**
1. Создать базовый интерфейс для всех обработчиков
2. Реализовать PromptValidator с перемещением логики валидации
3. Реализовать DirectiveResolver с логикой парсинга directives
4. Написать unit-тесты для обоих компонентов

**Эстимат по файлам:**
- PromptValidator: ~120 строк кода + ~150 строк тестов
- DirectiveResolver: ~180 строк кода + ~200 строк тестов

### Этап 2: Обработчики бизнес-логики (Priority: HIGH)
**Файлы для создания:**
- [ ] `acp-server/src/acp_server/protocol/handlers/tool_call_handler.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/permission_manager.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/client_rpc_handler.py`

**Задачи:**
1. Перемещение логики tool call management из prompt.py
2. Перемещение логики permission handling из permissions.py
3. Перемещение логики RPC preparation
4. Написание тестов для каждого обработчика

**Эстимат:**
- ToolCallHandler: ~140 строк + ~150 тестов
- PermissionManager: ~100 строк + ~120 тестов
- ClientRPCHandler: ~150 строк + ~180 тестов

### Этап 3: Построение notifications (Priority: MEDIUM)
**Файлы для создания:**
- [ ] `acp-server/src/acp_server/protocol/handlers/state_manager.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/plan_builder.py`

**Задачи:**
1. Конструирование StateManager для history/metadata
2. Построение PlanBuilder для plan entries
3. Утилиты для build_*_updates функций

**Эстимат:**
- StateManager: ~120 строк + ~140 тестов
- PlanBuilder: ~80 строк + ~100 тестов

### Этап 4: Управление жизненным циклом (Priority: HIGH)
**Файлы для создания:**
- [ ] `acp-server/src/acp_server/protocol/handlers/turn_lifecycle_manager.py`

**Задачи:**
1. Управление фазами turn (running, waiting_*, etc.)
2. Логика defer completion
3. Finalization и cleanup

**Эстимат:**
- TurnLifecycleManager: ~100 строк + ~130 тестов

### Этап 5: Оркестрация (Priority: CRITICAL)
**Файлы для создания:**
- [ ] `acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py`
- [ ] `acp-server/src/acp_server/protocol/handlers/prompt_cancellation_handler.py`

**Задачи:**
1. Создание PromptOrchestrator
2. Реализация handle_prompt() с координацией всех обработчиков
3. Реализация handle_with_agent()
4. Реализация handle_legacy()
5. Реализация PromptCancellationHandler
6. Миграция поддерживающих функций (session_cancel, complete_active_turn, etc.)

**Эстимат:**
- PromptOrchestrator: ~200 строк + ~250 тестов
- PromptCancellationHandler: ~120 строк + ~140 тестов

### Этап 6: Интеграция и миграция (Priority: HIGH)
**Задачи:**
1. Обновить core.py для использования PromptOrchestrator
2. Обновить HTTP транспорт для работы с новой архитектурой
3. Миграция из старого handler.session_prompt на новый
4. Удаление старого кода после миграции

**Файлы к изменению:**
- `acp-server/src/acp_server/protocol/core.py`
- `acp-server/src/acp_server/http_server.py`
- `acp-server/src/acp_server/protocol/handlers/prompt.py` (очистка)

### Этап 7: Тестирование и валидация (Priority: CRITICAL)
**Задачи:**
1. Integration тесты для всех scenarios
2. Regression тесты для существующей функциональности
3. Performance тесты
4. Валидация совместимости с ACP протоколом

**Файлы:**
- `acp-server/tests/test_prompt_orchestrator.py` (~500 строк)
- `acp-server/tests/test_prompt_handlers_integration.py` (~400 строк)

---

## 🔗 Зависимости и совместимость

### Использование существующих компонентов

**Exceptions** (уже созданы в `acp-server/src/acp_server/exceptions.py`):
- `ValidationError` — для invalid params
- `InvalidStateError` — для invalid state transitions
- `PermissionDeniedError` — для permission denied
- `ProtocolError` — для protocol-level errors

**Models** (уже созданы в `acp-server/src/acp_server/models.py`):
- `MessageContent`, `HistoryMessage` — для истории
- `ToolCall`, `ToolCallParameter` — для tool calls
- `Permission` — для разрешений
- `AgentPlan`, `PlanStep` — для плана

**State** (уже созданы в `acp-server/src/acp_server/protocol/state.py`):
- `SessionState` — главное состояние
- `ActiveTurnState` — состояние текущего turn
- `ToolCallState` — состояние tool call
- `PromptDirectives` — флаги поведения
- `PendingClientRequestState` — состояние ожидающего RPC

**SessionFactory** (уже создана):
- `SessionFactory.create_session()` — создание сессий
- Используется в миграции

### Совместимость

✅ **Обратная совместимость:**
- Публичный интерфейс `session_prompt()` остается неизменным
- Все notifications и responses остаются идентичными
- Параметры функции не меняются

✅ **Протокол ACP:**
- Все stop reasons остаются поддерживаемыми
- Все update types остаются валидными
- Все notifications format остаются корректными

⚠️ **Миграция:**
- Требует обновления импортов в core.py
- HTTP транспорт может требовать минорных адаптаций

---

## 🧪 Стратегия тестирования

### Unit тесты (приоритет: высокий)
```
tests/
├── protocol/
│   └── handlers/
│       ├── test_prompt_validator.py (150 строк)
│       ├── test_directive_resolver.py (200 строк)
│       ├── test_tool_call_handler.py (180 строк)
│       ├── test_permission_manager.py (150 строк)
│       ├── test_client_rpc_handler.py (200 строк)
│       ├── test_state_manager.py (150 строк)
│       ├── test_plan_builder.py (120 строк)
│       ├── test_turn_lifecycle_manager.py (160 строк)
│       ├── test_prompt_orchestrator.py (300 строк)
│       └── test_prompt_cancellation_handler.py (150 строк)
```

### Integration тесты (приоритет: критический)
```
tests/
├── protocol/
│   └── handlers/
│       ├── test_prompt_integration_simple.py (150 строк)
│       ├── test_prompt_integration_with_tool.py (200 строк)
│       ├── test_prompt_integration_with_rpc.py (180 строк)
│       ├── test_prompt_integration_with_permission.py (160 строк)
│       ├── test_prompt_integration_with_agent.py (200 строк)
│       └── test_prompt_integration_full_flow.py (250 строк)
```

### Сценарии тестирования

| Сценарий | Валидирует | Тест |
|----------|-----------|------|
| Простой prompt | Базовый flow без tool | `test_prompt_integration_simple.py` |
| Prompt с tool (ask mode) | Permission request | `test_prompt_integration_with_permission.py` |
| Prompt с tool (executor mode) | Auto-execution | `test_prompt_integration_with_tool.py` |
| Prompt с /fs-read | FS RPC | `test_prompt_integration_with_rpc.py` |
| Prompt с /term-run | Terminal RPC | `test_prompt_integration_with_rpc.py` |
| Prompt с /plan | Plan building | Unit тест в `test_plan_builder.py` |
| Prompt через агента | Agent delegation | `test_prompt_integration_with_agent.py` |
| Cancel в процессе | Cleanup + finalization | `test_prompt_cancellation_handler.py` |
| Nested directives | Override resolution | Unit тест в `test_directive_resolver.py` |
| Permission caching | Remembered permissions | `test_permission_manager.py` |

---

## 🚨 Риски и стратегии митигации

| Риск | Воздействие | Стратегия |
|------|-----------|----------|
| **Регрессия функциональности** | Высокое | Comprehensive integration tests перед deploy |
| **Performance деградация** | Среднее | Benchmark существующего vs нового; профилирование |
| **Несовместимость с Protocol** | Высокое | Тесты со спецификацией ACP; review от maintainers |
| **Сложность миграции** | Среднее | Gradual migration; параллельная поддержка обоих path |
| **Тестовое покрытие** | Среднее | Обязательное unit + integration покрытие |
| **Документирование** | Низкое | Docstrings, примеры, README updates |

### Стратегия rollout

1. **Фаза 1: Разработка и тестирование** (в отдельной ветке)
   - Написание всех компонентов
   - Unit и integration тесты
   - Internal validation

2. **Фаза 2: Staging validation**
   - Развертывание на staging
   - Load testing
   - Regression testing

3. **Фаза 3: Production rollout**
   - Feature flag для использования нового handler
   - Gradual traffic migration (10% → 50% → 100%)
   - Monitoring metrics

4. **Фаза 4: Cleanup**
   - Удаление старого кода
   - Документирование изменений

---

## 📈 Метрики успеха

| Метрика | Целевое значение | Как измерить |
|---------|-----------------|-------------|
| **Размер главной функции** | < 100 строк | Lines of code в orchestrator |
| **Cyclomatic complexity** | < 5 для каждого обработчика | Radon, pylint |
| **Test coverage** | > 90% | Coverage.py |
| **Response time** | ± 5% vs baseline | Benchmark тесты |
| **Type safety** | 100% | mypy в strict mode |
| **Documentation** | 100% docstrings | docstring coverage tools |

---

## 📚 Структура документов

### Документы разработчикам
- `acp-server/docs/PROMPT_HANDLER_ARCHITECTURE.md` — обзор архитектуры
- `acp-server/docs/HANDLER_INTERFACE_SPECIFICATION.md` — интерфейсы обработчиков
- `acp-server/docs/MIGRATION_GUIDE.md` — guide для миграции

### Обновления существующих документов
- `acp-server/README.md` — упоминание новой архитектуры
- `REFACTORING_ANALYSIS.md` — обновление статуса (COMPLETED)

---

## ⏭️ Следующие шаги

1. **Review архитектуры** — обсуждение с командой
2. **Утверждение плана** — approval от maintainers
3. **Начало реализации Этапа 1** — валидатор и resolver
4. **Итеративная разработка** — этап за этапом с тестами
5. **Integration и validation** — полная проверка перед merge
6. **Cleanup и документирование** — finalization и publication

---

## 🔗 Ссылки на связанные файлы

- [`acp-server/src/acp_server/protocol/handlers/prompt.py:243`](acp-server/src/acp_server/protocol/handlers/prompt.py:243) — текущая функция
- [`acp-server/src/acp_server/protocol/state.py`](acp-server/src/acp_server/protocol/state.py) — dataclasses
- [`acp-server/src/acp_server/exceptions.py`](acp-server/src/acp_server/exceptions.py) — исключения
- [`acp-server/src/acp_server/models.py`](acp-server/src/acp_server/models.py) — Pydantic модели
- [`acp-server/src/acp_server/protocol/session_factory.py`](acp-server/src/acp_server/protocol/session_factory.py) — SessionFactory
- [`acp-server/REFACTORING_ANALYSIS.md`](acp-server/REFACTORING_ANALYSIS.md) — исходный анализ

---

**Документ создан:** 2026-04-11  
**Версия:** 1.0  
**Статус:** 📋 Ready for review
