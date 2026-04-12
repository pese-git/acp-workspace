# Этап 3 (HIGH): Оркестраторы prompt-turn — Детальный план

**Статус:** 🔄 Планирование  
**Дата:** 2026-04-12  
**Приоритет:** 🔴 HIGH  

---

## 📋 Обзор

Этап 3 реализует четыре критичных компонента, отвечающих за оркестрацию и управление жизненным циклом prompt-turn:

1. **StateManager** — управление состоянием сессии и историей промптов
2. **PlanBuilder** — парсинг и построение планов из ответов LLM
3. **TurnLifecycleManager** — управление фазами и жизненным циклом turn
4. **PromptOrchestrator** — главный оркестратор, координирует все компоненты

Эти компоненты разлагают логику из [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py) (~2156 строк) и интегрируют компоненты Этапа 2 (ToolCallHandler, PermissionManager, ClientRPCHandler).

---

## 🔍 Анализ исходного кода

### Функции в prompt.py для рефакторинга

**Session State Management:**
```python
# session.py, prompt.py - управление состоянием и историей
def update_session_history(...) -> None:
    # Добавление записей в history (user, assistant)
    # ~15 строк

def finalize_active_turn(session: SessionState, *, stop_reason: str) -> ACPMessage | None:
    # Завершение active_turn и генерация final notification
    # ~25 строк
```

**Plan Management:**
```python
def normalize_plan_entries(raw_entries: Any) -> list[dict[str, str]] | None:
    # Валидация и нормализация плана из directives
    # ~20 строк

def build_plan_entries(
    directives: PromptDirectives,
    session: SessionState,
    session_id: str,
) -> list[ACPMessage]:
    # Построение план-entries и notifications для session/update
    # ~40 строк
```

**Stop Reason & Turn Control:**
```python
def resolve_prompt_stop_reason(directives: PromptDirectives) -> str:
    # Определение stop reason на основе directives
    # ~10 строк

def normalize_stop_reason(stop_reason: str, supported_stop_reasons: set[str] | None = None) -> str:
    # Нормализация stop reason к ACP spec
    # ~15 строк

def normalize_tool_kind(candidate: str, supported_tool_kinds: set[str] | None = None) -> str | None:
    # Нормализация tool kind
    # ~20 строк
```

**Client Request Handling:**
```python
def find_session_by_pending_client_request_id(...) -> SessionState | None:
    # Поиск сессии с pending client RPC request
    # ~15 строк

def resolve_pending_client_rpc_response_impl(...) -> ProtocolOutcome:
    # Обработка response на pending client RPC
    # ~80 строк
```

---

## 🏗️ Целевая архитектура

### 1. StateManager

**Файл:** `acp-server/src/acp_server/protocol/handlers/state_manager.py`

**Ответственность:**
- Управление состоянием SessionState
- Обновление истории (history)
- Управление заголовком сессии (title)
- Синхронизация временных меток (updated_at)

**Интерфейс:**

```python
class StateManager:
    """Управляет состоянием сессии и историей промптов."""
    
    def update_session_title(
        self,
        session: SessionState,
        text_preview: str,
    ) -> None:
        """Устанавливает title сессии из первого пользовательского запроса.
        
        Args:
            session: Состояние сессии
            text_preview: Текст для заголовка (будет обрезан до 80 символов)
        """
    
    def add_user_message(
        self,
        session: SessionState,
        prompt: list[dict[str, Any]],
    ) -> None:
        """Добавляет пользовательское сообщение в историю.
        
        Args:
            session: Состояние сессии
            prompt: Массив content blocks из request
        """
    
    def add_assistant_message(
        self,
        session: SessionState,
        content: str | dict[str, Any],
    ) -> None:
        """Добавляет ответ ассистента в историю.
        
        Args:
            session: Состояние сессии
            content: Текст или структурированный контент ответа
        """
    
    def update_session_timestamp(self, session: SessionState) -> None:
        """Обновляет updated_at на текущее время в UTC ISO 8601."""
    
    def get_session_summary(self, session: SessionState) -> dict[str, Any]:
        """Возвращает сводку состояния сессии для notifications.
        
        Returns:
            {"title": ..., "updated_at": ..., "history_length": ...}
        """
```

**Внутренние утилиты:**
```python
def _sanitize_history_entry(entry: Any) -> HistoryMessage | dict[str, Any] | None:
    """Валидация записи истории перед добавлением."""

def _extract_text_from_content_blocks(blocks: list[dict[str, Any]]) -> str:
    """Извлечение текстового предпросмотра из content blocks."""
```

**Unit-тесты:** `acp-server/tests/test_state_manager.py`
- ✅ Установка заголовка из первого сообщения
- ✅ Добавление user и assistant сообщений в историю
- ✅ Обновление timestamp
- ✅ Получение summary для notifications
- ✅ ~80 строк тестов

---

### 2. PlanBuilder

**Файл:** `acp-server/src/acp_server/protocol/handlers/plan_builder.py`

**Ответственность:**
- Парсинг plan entries из directives
- Валидация структуры плана
- Построение plan-related notifications
- Нормализация plan entries

**Интерфейс:**

```python
class PlanBuilder:
    """Управляет построением и валидацией планов выполнения."""
    
    def should_publish_plan(self, directives: PromptDirectives) -> bool:
        """Нужно ли публиковать план в текущем turn.
        
        Returns:
            True если directives.publish_plan=True и есть plan_entries
        """
    
    def validate_plan_entries(
        self,
        raw_entries: Any,
    ) -> list[dict[str, str]] | None:
        """Валидирует и нормализует структуру plan entries.
        
        Args:
            raw_entries: Сырые entries из directives или LLM response
        
        Returns:
            Нормализованный список {title, description} или None
        """
    
    def build_plan_notification(
        self,
        session_id: str,
        plan_entries: list[dict[str, str]],
    ) -> ACPMessage:
        """Строит session/update notification с планом.
        
        Args:
            session_id: ID сессии
            plan_entries: Нормализованные entries с title и description
        
        Returns:
            ACPMessage с типом session/update и planUpdate
        """
    
    def extract_plan_from_directives(
        self,
        directives: PromptDirectives,
    ) -> list[dict[str, str]] | None:
        """Извлекает план из PromptDirectives.
        
        Returns:
            Нормализованный план или None
        """
    
    def update_session_plan(
        self,
        session: SessionState,
        plan_entries: list[dict[str, str]],
    ) -> None:
        """Обновляет latest_plan в сессии."""
    
    def build_plan_updates(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> list[ACPMessage]:
        """Строит все plan-related notifications.
        
        Returns:
            Список notifications если нужно публиковать план, иначе []
        """
```

**Внутренние утилиты:**
```python
def _validate_entry_structure(entry: Any) -> bool:
    """Проверяет валидность одного entry (требует title, description)."""

def _normalize_entry_fields(entry: dict[str, Any]) -> dict[str, str]:
    """Нормализует поля entry (обрезает длинные значения)."""

def _get_allowed_plan_keys() -> set[str]:
    """Спецификация разрешенных ключей в entry."""
```

**Unit-тесты:** `acp-server/tests/test_plan_builder.py`
- ✅ should_publish_plan для разных directives
- ✅ validate_plan_entries для валидных/невалидных входов
- ✅ build_plan_notification структура и содержимое
- ✅ extract_plan_from_directives
- ✅ update_session_plan
- ✅ build_plan_updates агрегирование notifications
- ✅ ~100 строк тестов

---

### 3. TurnLifecycleManager

**Файл:** `acp-server/src/acp_server/protocol/handlers/turn_lifecycle_manager.py`

**Ответственность:**
- Управление фазами turn (running → completed)
- Обработка cancel requests (set cancel_requested flag)
- Finalization с корректным stop reason
- Эмиссия финальных notifications

**Интерфейс:**

```python
class TurnLifecycleManager:
    """Управляет фазами и жизненным циклом prompt-turn."""
    
    def create_active_turn(
        self,
        session_id: str,
        prompt_request_id: JsonRpcId | None,
    ) -> ActiveTurnState:
        """Создает новое состояние active turn.
        
        Args:
            session_id: ID сессии
            prompt_request_id: ID входящего prompt request
        
        Returns:
            Инициализированный ActiveTurnState
        """
    
    def mark_cancel_requested(self, session: SessionState) -> None:
        """Устанавливает флаг cancel_requested в active turn.
        
        Used when session/cancel arrives while turn is active.
        """
    
    def is_cancel_requested(self, session: SessionState) -> bool:
        """Проверяет, был ли запрошен cancel для активного turn."""
    
    def set_turn_phase(
        self,
        session: SessionState,
        phase: str,
    ) -> None:
        """Переходит turn в новую фазу.
        
        Args:
            phase: 'running', 'awaiting_permission', 'awaiting_client_rpc', 'completing'
        """
    
    def get_turn_phase(self, session: SessionState) -> str:
        """Возвращает текущую фазу turn."""
    
    def resolve_stop_reason(
        self,
        directives: PromptDirectives,
        supported_reasons: set[str] | None = None,
    ) -> str:
        """Определяет stop reason для текущего turn.
        
        Args:
            directives: Исходящие директивы
            supported_reasons: Поддерживаемые значения (default: ACP spec)
        
        Returns:
            Нормализованный stop reason
        """
    
    def finalize_turn(
        self,
        session: SessionState,
        stop_reason: str,
    ) -> ACPMessage | None:
        """Финализирует active turn и строит финальное notification.
        
        Args:
            session: Состояние сессии
            stop_reason: Причина завершения turn
        
        Returns:
            ACPMessage с session_turn_complete или None
        """
    
    def clear_active_turn(self, session: SessionState) -> None:
        """Очищает active turn (устанавливает в None)."""
    
    def should_handle_cancel(self, session: SessionState) -> bool:
        """Проверяет, нужно ли обрабатывать cancel.
        
        True если есть active_turn и cancel_requested=True.
        """
```

**Внутренние утилиты:**
```python
def _get_allowed_phases() -> set[str]:
    """Матрица допустимых фаз жизненного цикла."""

def _get_supported_stop_reasons() -> set[str]:
    """Спецификация поддерживаемых stop reasons из ACP."""

def _normalize_stop_reason(candidate: str, supported: set[str]) -> str:
    """Нормализует stop reason к поддерживаемому значению."""

def _validate_phase_transition(from_phase: str, to_phase: str) -> bool:
    """Проверяет валидность перехода между фазами."""
```

**Unit-тесты:** `acp-server/tests/test_turn_lifecycle_manager.py`
- ✅ create_active_turn инициализирует состояние
- ✅ mark_cancel_requested и is_cancel_requested
- ✅ set_turn_phase и get_turn_phase
- ✅ resolve_stop_reason для разных directives
- ✅ finalize_turn и clear_active_turn
- ✅ should_handle_cancel
- ✅ Валидация фаз
- ✅ ~120 строк тестов

---

### 4. PromptOrchestrator

**Файл:** `acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py`

**Ответственность:**
- Оркестрация prompt-turn обработки
- Интеграция компонентов Этап 2 (ToolCallHandler, PermissionManager, ClientRPCHandler)
- Интеграция компонентов Этап 3 (StateManager, PlanBuilder, TurnLifecycleManager)
- Управление потоком выполнения turn-а

**Интерфейс:**

```python
class PromptOrchestrator:
    """Главный оркестратор обработки prompt-turn."""
    
    def __init__(
        self,
        tool_call_handler: ToolCallHandler,
        permission_manager: PermissionManager,
        client_rpc_handler: ClientRPCHandler,
        state_manager: StateManager,
        plan_builder: PlanBuilder,
        turn_lifecycle_manager: TurnLifecycleManager,
    ):
        """Инициализирует оркестратор со всеми компонентами."""
    
    async def handle_prompt(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AgentOrchestrator,
    ) -> ProtocolOutcome:
        """Обрабатывает session/prompt request.
        
        Оркестрирует:
        1. Инициализацию active turn
        2. Обработку промпта через LLM-агента
        3. Управление tool calls (ToolCallHandler)
        4. Permission requests (PermissionManager)
        5. Client RPC requests (ClientRPCHandler)
        6. Plan publication (PlanBuilder)
        7. Turn finalization (TurnLifecycleManager)
        
        Args:
            request_id: ID входящего request
            params: Параметры (должны содержать prompt array)
            session: Состояние сессии
            sessions: Словарь всех сессий
            agent_orchestrator: LLM-агент для обработки
        
        Returns:
            ProtocolOutcome с notifications и response
        """
    
    async def handle_cancel(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome:
        """Обрабатывает session/cancel request.
        
        Логика:
        1. Установить cancel_requested флаг
        2. Отменить активные tool calls (ToolCallHandler.cancel_active_tools)
        3. Отменить permission requests (mark as cancelled_permission_requests)
        4. Отменить client RPC requests (mark as cancelled_client_rpc_requests)
        5. Завершить turn с stop_reason='cancel'
        
        Args:
            request_id: ID cancel request
            params: Параметры (sessionId)
            session: Состояние сессии
            sessions: Словарь всех сессий
        
        Returns:
            ProtocolOutcome с notifications об отмене
        """
    
    def handle_pending_client_rpc_response(
        self,
        session: SessionState,
        session_id: str,
        kind: str,
        result: Any,
        error: dict[str, Any] | None,
    ) -> ProtocolOutcome:
        """Обрабатывает response на pending client RPC request.
        
        Args:
            session: Состояние сессии
            session_id: ID сессии
            kind: Тип RPC ('fs_read', 'fs_write', 'terminal_create')
            result: Результат выполнения
            error: Ошибка (если есть)
        
        Returns:
            ProtocolOutcome с updates и possible turn finalization
        """
    
    def handle_permission_response(
        self,
        session: SessionState,
        session_id: str,
        permission_request_id: JsonRpcId,
        result: Any,
    ) -> ProtocolOutcome:
        """Обрабатывает response на permission request.
        
        Args:
            session: Состояние сессии
            session_id: ID сессии
            permission_request_id: ID permission request
            result: Ответ пользователя
        
        Returns:
            ProtocolOutcome с decision updates или final turn completion
        """
```

**Внутренние утилиты:**
```python
def _extract_text_from_prompt_blocks(prompt: list[dict[str, Any]]) -> tuple[str, str]:
    """Извлекает полный текст и preview из prompt blocks.
    
    Returns:
        (full_text, preview_text)
    """

def _build_prompt_updates(
    session_id: str,
    text_preview: str,
) -> list[ACPMessage]:
    """Строит initial notifications для prompt processing."""

async def _process_agent_response(
    session: SessionState,
    sessions: dict[str, SessionState],
    agent_result: Any,
) -> list[ACPMessage]:
    """Обрабатывает результат от LLM-агента."""

def _build_turn_finalization_updates(
    orchestrator: PromptOrchestrator,
    session: SessionState,
    session_id: str,
    stop_reason: str,
) -> list[ACPMessage]:
    """Собирает все финальные notifications при завершении turn."""
```

**Unit-тесты:** `acp-server/tests/test_prompt_orchestrator.py`
- ✅ handle_prompt end-to-end flow
- ✅ handle_cancel отмена active turn
- ✅ handle_pending_client_rpc_response обработка fs/read
- ✅ handle_pending_client_rpc_response обработка fs/write
- ✅ handle_pending_client_rpc_response обработка terminal
- ✅ handle_permission_response для allow/reject
- ✅ Интеграция с ToolCallHandler
- ✅ Интеграция с PermissionManager
- ✅ Интеграция с ClientRPCHandler
- ✅ Интеграция с StateManager
- ✅ Интеграция с PlanBuilder
- ✅ Интеграция с TurnLifecycleManager
- ✅ ~250 строк тестов

---

## 🔗 Зависимости между компонентами

```
PromptOrchestrator (главный оркестратор)
├── StateManager
│   ├── SessionState.history
│   ├── SessionState.title
│   └── SessionState.updated_at
├── PlanBuilder
│   ├── SessionState.latest_plan
│   ├── PromptDirectives.plan_entries
│   └── ACPMessage (plan notifications)
├── TurnLifecycleManager
│   ├── SessionState.active_turn
│   ├── ActiveTurnState.phase
│   └── ActiveTurnState.cancel_requested
├── ToolCallHandler (Этап 2)
│   ├── SessionState.tool_calls
│   ├── SessionState.tool_call_counter
│   └── ACPMessage (notifications)
├── PermissionManager (Этап 2)
│   ├── SessionState.permission_policy
│   ├── SessionState.active_turn
│   └── ACPMessage (requests)
└── ClientRPCHandler (Этап 2)
    ├── SessionState.runtime_capabilities
    ├── SessionState.active_turn
    └── ACPMessage (requests)

Порядок инициализации:
1. StateManager (самостоятельный)
2. PlanBuilder (самостоятельный)
3. TurnLifecycleManager (самостоятельный)
4. ToolCallHandler (Этап 2)
5. PermissionManager (Этап 2)
6. ClientRPCHandler (Этап 2, зависит от ToolCallHandler)
7. PromptOrchestrator (зависит от всех выше)
```

---

## 📊 Метрики кода

| Компонент | Строк кода | Строк тестов | Интеграционные точки |
|-----------|-----------|--------------|------------------|
| **StateManager** | ~90 | ~80 | prompt.py, session.py |
| **PlanBuilder** | ~120 | ~100 | prompt.py |
| **TurnLifecycleManager** | ~140 | ~120 | prompt.py |
| **PromptOrchestrator** | ~200 | ~250 | prompt.py, core.py |
| **Итого** | ~550 | ~550 | - |

---

## 📝 План исполнения

### Этап 3.1: StateManager (~1.5 часа работы)

**Шаги:**
1. Создать файл [`state_manager.py`](acp-server/src/acp_server/protocol/handlers/state_manager.py)
2. Реализовать методы управления историей и состоянием
3. Написать unit-тесты (80 строк)
4. Проверить интеграцию с SessionState

**Контрольные точки:**
- ✅ Класс создан и компилируется
- ✅ Все методы реализованы
- ✅ Unit-тесты на 90%+ покрытие

### Этап 3.2: PlanBuilder (~1.5 часа работы)

**Шаги:**
1. Создать файл [`plan_builder.py`](acp-server/src/acp_server/protocol/handlers/plan_builder.py)
2. Реализовать валидацию и парсинг планов
3. Написать unit-тесты (100 строк)
4. Проверить построение notifications

**Контрольные точки:**
- ✅ Класс создан и функционален
- ✅ Валидация plan entries работает
- ✅ Notifications корректно строятся

### Этап 3.3: TurnLifecycleManager (~2 часа работы)

**Шаги:**
1. Создать файл [`turn_lifecycle_manager.py`](acp-server/src/acp_server/protocol/handlers/turn_lifecycle_manager.py)
2. Реализовать управление фазами и жизненным циклом
3. Написать unit-тесты (120 строк)
4. Проверить обработку cancel

**Контрольные точки:**
- ✅ Класс создан и функционален
- ✅ Фазы правильно управляются
- ✅ Cancel handling работает

### Этап 3.4: PromptOrchestrator (~3 часа работы)

**Шаги:**
1. Создать файл [`prompt_orchestrator.py`](acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py)
2. Реализовать оркестрацию всех компонентов
3. Интегрировать компоненты Этапа 2
4. Написать unit-тесты (250 строк)
5. Проверить end-to-end flow

**Контрольные точки:**
- ✅ Класс создан и функционален
- ✅ Все компоненты интегрированы
- ✅ End-to-end тесты проходят

### Этап 3.5: Интеграция и тестирование (~2 часа работы)

**Шаги:**
1. Обновить [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py):
   - Импортировать новые компоненты
   - Удалить переместившуюся логику
2. Проверить, что все существующие тесты проходят
3. Запустить `make check`:
   - pytest: должно пройти 429+ тестов
   - ruff check
   - type check
4. Обновить [`acp-server/README.md`](acp-server/README.md)
5. Обновить [`REFACTORING_STATUS.md`](acp-server/REFACTORING_STATUS.md)

**Контрольные точки:**
- ✅ make check проходит полностью
- ✅ Все 429+ тестов проходят
- ✅ Type checking в strict mode
- ✅ Нет регрессий

---

## 🧪 Стратегия тестирования

### Unit-тесты StateManager (80 строк)

```python
# test_state_manager.py

class TestStateManagerHistory:
    def test_update_session_title_from_preview(self):
    def test_add_user_message_to_history(self):
    def test_add_assistant_message_to_history(self):

class TestStateManagerTimestamp:
    def test_update_session_timestamp(self):

class TestStateManagerSummary:
    def test_get_session_summary(self):
```

### Unit-тесты PlanBuilder (100 строк)

```python
# test_plan_builder.py

class TestPlanBuilderValidation:
    def test_validate_plan_entries_valid_input(self):
    def test_validate_plan_entries_invalid_structure(self):

class TestPlanBuilderNotifications:
    def test_build_plan_notification_structure(self):

class TestPlanBuilderExtraction:
    def test_extract_plan_from_directives(self):

class TestPlanBuilderUpdates:
    def test_build_plan_updates(self):
```

### Unit-тесты TurnLifecycleManager (120 строк)

```python
# test_turn_lifecycle_manager.py

class TestTurnLifecycleCreation:
    def test_create_active_turn(self):

class TestTurnLifecyclePhases:
    def test_set_turn_phase(self):
    def test_get_turn_phase(self):

class TestTurnLifecycleCancel:
    def test_mark_cancel_requested(self):
    def test_is_cancel_requested(self):

class TestTurnLifecycleStopReason:
    def test_resolve_stop_reason(self):

class TestTurnLifecycleFinalization:
    def test_finalize_turn(self):
    def test_clear_active_turn(self):
```

### Unit-тесты PromptOrchestrator (250 строк)

```python
# test_prompt_orchestrator.py

class TestPromptOrchestratorHandlePrompt:
    def test_handle_prompt_end_to_end(self):
    def test_handle_prompt_with_agent(self):

class TestPromptOrchestratorHandleCancel:
    def test_handle_cancel_with_active_turn(self):
    def test_handle_cancel_no_active_turn(self):

class TestPromptOrchestratorClientRpc:
    def test_handle_pending_client_rpc_response_fs_read(self):
    def test_handle_pending_client_rpc_response_fs_write(self):
    def test_handle_pending_client_rpc_response_terminal(self):

class TestPromptOrchestratorPermission:
    def test_handle_permission_response_allow(self):
    def test_handle_permission_response_reject(self):

class TestPromptOrchestratorIntegration:
    def test_all_components_integrated(self):
    def test_component_initialization_order(self):
```

---

## 🔄 Миграция из prompt.py

### Функции для переместить в StateManager:
```python
# Из prompt.py, session.py - implicit functions
- update_session_history() (новая)
- update_session_title() (выделить из _handle_with_agent)
- add_user_message() (новая)
- add_assistant_message() (новая)
- update_session_timestamp() (новая)
```

### Функции для переместить в PlanBuilder:
```python
# Из prompt.py (строки ~1027-1240)
- normalize_plan_entries()
- build_plan_entries()
```

### Функции для переместить в TurnLifecycleManager:
```python
# Из prompt.py (строки ~945-1020)
- resolve_prompt_stop_reason()
- normalize_stop_reason()
- finalize_active_turn()
```

### Функции для переместить в PromptOrchestrator:
```python
# Из prompt.py (строки ~40-230, 1305-1430)
- _handle_with_agent() → handle_prompt()
- session/cancel обработка → handle_cancel()
- resolve_pending_client_rpc_response_impl() → handle_pending_client_rpc_response()
```

### Функции для оставить в prompt.py (поддержка):
```python
# Будут использоваться orchestrator и другими компонентами
- normalize_tool_kind()
- find_session_by_pending_client_request_id()
- Helpers для LLM интеграции
```

---

## ✅ Критерии успеха

1. **Функциональность:** Все компоненты работают корректно и интегрированы
2. **Тесты:** 550+ новых unit-тестов на 90%+ покрытие кода компонентов
3. **Качество:** `make check` проходит полностью без регрессий
4. **Совместимость:** ACP протокол полностью соблюдается
5. **Документация:** README обновлена с описанием новых компонентов

---

## ⚠️ Потенциальные риски

| Риск | Вероятность | Импакт | Стратегия |
|------|-----------|------|----|
| **Сложная оркестрация** | Средняя | Высокий | Detailed unit + integration tests |
| **Регрессия в prompt handling** | Средняя | Критический | Comprehensive conformance tests |
| **Circular imports** | Средняя | Высокий | Осторожность с импортами |
| **Async handling** | Средняя | Средний | Тесты async flows |
| **Type safety в интеграциях** | Низкая | Средний | Strict mypy mode |

---

## 📚 Ссылки на исходный код

- [`prompt.py:40-230`](acp-server/src/acp_server/protocol/handlers/prompt.py:40) — _handle_with_agent
- [`prompt.py:945-1020`](acp-server/src/acp_server/protocol/handlers/prompt.py:945) — Stop reason functions
- [`prompt.py:1027-1240`](acp-server/src/acp_server/protocol/handlers/prompt.py:1027) — Plan functions
- [`prompt.py:1569-1610`](acp-server/src/acp_server/protocol/handlers/prompt.py:1569) — finalize_active_turn
- [`state.py`](acp-server/src/acp_server/protocol/state.py) — Data structures
- [`models.py`](acp-server/src/acp_server/models.py) — Pydantic models

---

**Документ создан:** 2026-04-12  
**Версия:** 1.0  
**Статус:** 📋 Ready for implementation
