# Этап 2 (HIGH): Обработчики бизнес-логики — Детальный план

**Статус:** 🔄 Планирование  
**Дата:** 2026-04-12  
**Приоритет:** 🔴 HIGH  

---

## 📋 Обзор

Этап 2 разлагает три критичных компонента, отвечающих за основную бизнес-логику обработки prompt-turn:

1. **ToolCallHandler** — управление lifecycle tool calls
2. **PermissionManager** — обработка разрешений и policy
3. **ClientRPCHandler** — подготовка RPC запросов к клиенту

Эти компоненты уже имеют разбросанный код в [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py) и [`permissions.py`](acp-server/src/acp_server/protocol/handlers/permissions.py), который требует консолидации и переоформатирования в структурированные классы.

---

## 🔍 Анализ исходного кода

### Функции в prompt.py, требующие рефакторинга

**Tool Call Management:**
```python
def create_tool_call(session: SessionState, *, title: str, kind: str) -> str:
    # Создает новый tool call с локальным монотонным ID
    # ~15 строк

def update_tool_call_status(
    session: SessionState,
    tool_call_id: str,
    status: str,
    *,
    content: list[dict[str, Any]] | None = None,
) -> None:
    # Обновляет статус с проверкой допустимых переходов
    # ~20 строк

def cancel_active_tool_calls(session: SessionState, session_id: str) -> list[ACPMessage]:
    # Отменяет все незавершенные tool calls
    # ~25 строк

def build_executor_tool_execution_updates(...) -> list[ACPMessage]:
    # Executor mode: in_progress -> completed
    # ~60 строк

def build_policy_tool_execution_updates(...) -> list[ACPMessage]:
    # Policy mode: после решения по разрешению
    # ~75 строк
```

**Client RPC Support:**
```python
def can_run_tool_runtime(session: SessionState) -> bool:
    # Проверяет доступность tool-runtime
    # ~10 строк

def can_use_fs_client_rpc(session: SessionState, kind: str) -> bool:
    # Проверяет fs/* RPC
    # ~15 строк

def can_use_terminal_client_rpc(session: SessionState) -> bool:
    # Проверяет terminal/* RPC
    # ~10 строк

def build_fs_client_request(...) -> PreparedFsClientRequest | None:
    # Подготовка fs/read или fs/write
    # ~150 строк

def build_terminal_client_request(...) -> PreparedFsClientRequest | None:
    # Подготовка terminal/create
    # ~60 строк

def normalize_session_path(cwd: str, candidate: str) -> str | None:
    # Нормализация пути в рамках cwd
    # ~10 строк
```

### Функции в permissions.py, требующие консолидации

```python
def find_session_by_permission_request_id(...) -> SessionState | None:
    # ~15 строк

def extract_permission_outcome(result: Any) -> str | None:
    # ~20 строк

def extract_permission_option_id(result: Any) -> str | None:
    # ~20 строк

def resolve_permission_option_kind(...) -> str | None:
    # ~15 строк

def resolve_remembered_permission_decision(...) -> str:
    # ~10 строк

def build_permission_options() -> list[dict[str, Any]]:
    # ~20 строк
```

### Вспомогательные функции (нужны для поддержки)

```python
def resolve_prompt_stop_reason(directives: PromptDirectives) -> str:
    # Определение stop reason
    # ~10 строк

def normalize_stop_reason(stop_reason: str, ...) -> str:
    # ~15 строк

def resolve_tool_title(kind: str) -> str:
    # ~20 строк

def normalize_tool_kind(candidate: str, ...) -> str | None:
    # ~20 строк

def finalize_active_turn(session: SessionState, *, stop_reason: str) -> ACPMessage | None:
    # ~15 строк

def find_session_by_pending_client_request_id(...) -> SessionState | None:
    # ~15 строк
```

---

## 🏗️ Целевая архитектура

### 1. ToolCallHandler

**Файл:** `acp-server/src/acp_server/protocol/handlers/tool_call_handler.py`

**Ответственность:**
- Создание tool call записей
- Управление lifecycle (pending → in_progress → completed/cancelled/failed)
- Построение tool_call update notifications
- Executor vs. permission-based execution flows

**Интерфейс:**

```python
class ToolCallHandler:
    """Управляет жизненным циклом tool calls в prompt-turn."""
    
    def can_run_tools(self, session: SessionState) -> bool:
        """Проверяет, доступен ли tool-runtime для текущей сессии.
        
        Returns:
            True если есть хотя бы одна capability (terminal, fs_read, fs_write)
        """
    
    def create_tool_call(
        self,
        session: SessionState,
        *,
        title: str,
        kind: str,
    ) -> str:
        """Создает новый tool call, возвращает ID.
        
        Args:
            session: Состояние сессии
            title: Название для UI (e.g., "Tool execution")
            kind: Категория (read, edit, delete, move, search, execute, think, fetch, switch_mode, other)
        
        Returns:
            ID вида "call_NNN"
        """
    
    def update_tool_call_status(
        self,
        session: SessionState,
        tool_call_id: str,
        status: str,
        *,
        content: list[dict[str, Any]] | None = None,
    ) -> None:
        """Обновляет статус tool call с проверкой допустимых переходов.
        
        Допустимые переходы:
        - pending → in_progress, cancelled, failed
        - in_progress → completed, cancelled, failed
        - completed, cancelled, failed → (терминальные)
        """
    
    def build_tool_call_notification(
        self,
        session_id: str,
        tool_call_id: str,
        title: str,
        kind: str,
        locations: list[dict[str, str]] | None = None,
    ) -> ACPMessage:
        """Строит tool_call notification для отправки клиенту."""
    
    def build_tool_update_notification(
        self,
        session_id: str,
        tool_call_id: str,
        status: str,
        content: list[dict[str, Any]] | None = None,
    ) -> ACPMessage:
        """Строит tool_call_update notification."""
    
    def build_executor_execution_updates(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        leave_running: bool = False,
    ) -> list[ACPMessage]:
        """Executor mode: in_progress → completed (или оставить running).
        
        Используется когда режим 'executor' и разрешение уже получено.
        """
    
    def build_policy_execution_updates(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        allowed: bool,
    ) -> list[ACPMessage]:
        """Policy mode: после решения по разрешению (allow/reject).
        
        - allowed=True: in_progress → completed
        - allowed=False: cancelled
        """
    
    def cancel_active_tools(
        self,
        session: SessionState,
        session_id: str,
    ) -> list[ACPMessage]:
        """Отменяет все активные (pending, in_progress) tool calls."""
```

**Внутренние утилиты:**
```python
def _get_allowed_transitions() -> dict[str, set[str]]:
    """Матрица допустимых переходов состояний."""

def _validate_tool_kind(kind: str) -> bool:
    """Проверяет, является ли kind валидным."""

def _resolve_tool_title(kind: str) -> str:
    """Возвращает человекочитаемый title для kind."""
```

**Unit-тесты:** `acp-server/tests/test_tool_call_handler.py`
- ✅ Создание tool call с монотонным ID
- ✅ Валидация переходов (pending → in_progress → completed)
- ✅ Отказ от невалидного перехода (completed → in_progress)
- ✅ Executor mode: in_progress → completed
- ✅ Policy mode: allowed=True → completed
- ✅ Policy mode: allowed=False → cancelled
- ✅ Отмена всех активных tool calls
- ✅ Построение notifications с правильной структурой
- ✅ 180+ строк тестов

---

### 2. PermissionManager

**Файл:** `acp-server/src/acp_server/protocol/handlers/permission_manager.py`

**Ответственность:**
- Определение, нужен ли permission request
- Поиск remembered permissions
- Построение permission request messages
- Обработка permission response

**Интерфейс:**

```python
class PermissionManager:
    """Управляет разрешениями и permission flow."""
    
    def should_request_permission(
        self,
        session: SessionState,
        tool_kind: str,
    ) -> bool:
        """Нужен ли permission request для данного tool kind.
        
        Returns:
            True если policy для tool_kind == 'ask' или не установлена
            False если policy == 'allow_always' или 'reject_always'
        """
    
    def get_remembered_permission(
        self,
        session: SessionState,
        tool_kind: str,
    ) -> str:
        """Возвращает применяемое решение из permission_policy.
        
        Returns:
            'allow' (для 'allow_always')
            'reject' (для 'reject_always')
            'ask' (если нет policy или по умолчанию)
        """
    
    def build_permission_request(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        tool_title: str,
        tool_kind: str,
    ) -> ACPMessage:
        """Строит session/request_permission message.
        
        Включает:
        - Allow once
        - Allow always (with policy save)
        - Reject once
        - Reject always (with policy save)
        """
    
    def build_permission_options(self) -> list[dict[str, Any]]:
        """Возвращает варианты решения для permission request."""
    
    def extract_permission_outcome(self, result: Any) -> str | None:
        """Извлекает outcome из response (поддерживает ACP и legacy format).
        
        Returns:
            'selected' или другой outcome, или None
        """
    
    def extract_permission_option_id(self, result: Any) -> str | None:
        """Извлекает optionId из response.
        
        Returns:
            'allow_once', 'allow_always', 'reject_once', 'reject_always' или None
        """
    
    def resolve_permission_option_kind(
        self,
        option_id: str | None,
        permission_options: list[dict[str, Any]],
    ) -> str | None:
        """Возвращает kind опции по optionId."""
    
    def build_permission_acceptance_updates(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        option_id: str,
    ) -> list[ACPMessage]:
        """Строит updates после выбора опции разрешения.
        
        Если опция имеет 'always', сохраняет policy в session.permission_policy.
        """
    
    def find_session_by_permission_request_id(
        self,
        permission_request_id: JsonRpcId,
        sessions: dict[str, SessionState],
    ) -> SessionState | None:
        """Ищет сессию с активным turn, ожидающим ответ на permission request."""
```

**Внутренние утилиты:**
```python
def _build_permission_options_spec() -> list[dict[str, str]]:
    """Спецификация всех permission опций."""

def _extract_policy_decision(option_id: str) -> tuple[str, bool]:
    """Из option_id извлекает (decision, should_save_policy).
    
    Возвращает:
        ('allow', True) для 'allow_always'
        ('allow', False) для 'allow_once'
        ('reject', True) для 'reject_always'
        ('reject', False) для 'reject_once'
    """
```

**Unit-тесты:** `acp-server/tests/test_permission_manager.py`
- ✅ should_request_permission для разных policy values
- ✅ get_remembered_permission для allow_always/reject_always/default
- ✅ build_permission_request структура и содержимое
- ✅ extract_permission_outcome для ACP и legacy format
- ✅ extract_permission_option_id для ACP и legacy format
- ✅ resolve_permission_option_kind поиск по optionId
- ✅ build_permission_acceptance_updates с сохранением policy
- ✅ find_session_by_permission_request_id
- ✅ Permission caching (remembered permissions)
- ✅ 150+ строк тестов

---

### 3. ClientRPCHandler

**Файл:** `acp-server/src/acp_server/protocol/handlers/client_rpc_handler.py`

**Ответственность:**
- Проверка доступности FS и Terminal capabilities
- Подготовка fs/read, fs/write, terminal/create requests
- Создание связанных tool calls и pending state
- Нормализация путей

**Интерфейс:**

```python
class ClientRPCHandler:
    """Управляет agent→client RPC запросами (fs/*, terminal/*)."""
    
    def can_use_fs_rpc(
        self,
        session: SessionState,
        kind: str,
    ) -> bool:
        """Проверяет доступность fs/* RPC.
        
        Args:
            kind: 'fs_read' или 'fs_write'
        
        Returns:
            True если runtime_capabilities имеет соответствующую capability
        """
    
    def can_use_terminal_rpc(self, session: SessionState) -> bool:
        """Проверяет доступность terminal/* RPC."""
    
    def can_run_tools(self, session: SessionState) -> bool:
        """Проверяет общую доступность tool-runtime.
        
        Returns:
            True если есть хотя бы одна capability
        """
    
    def normalize_path(self, cwd: str, candidate: str) -> str | None:
        """Преобразует путь в абсолютный в рамках cwd.
        
        - Если absolute, оставляет как есть
        - Если relative, присоединяет к cwd
        - Если пусто/невалидно, возвращает None
        """
    
    def prepare_fs_read_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит fs/read_text_file request.
        
        Returns:
            PreparedFsClientRequest с tool_call, request и pending state
            None если fs_read_path не установлен или путь невалиден
        """
    
    def prepare_fs_write_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит fs/write_text_file request.
        
        Returns:
            PreparedFsClientRequest для fs/write
            None если fs_write_path не установлен
        """
    
    def prepare_terminal_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Готовит terminal/create request.
        
        Returns:
            PreparedFsClientRequest для terminal/create
            None если terminal_command не установлен
        """
    
    def prepare_fs_request(
        self,
        session: SessionState,
        session_id: str,
        directives: PromptDirectives,
    ) -> PreparedFsClientRequest | None:
        """Помощник: выбирает между read и write на основе directives."""
    
    def handle_pending_response(
        self,
        session: SessionState,
        session_id: str,
        kind: str,
        result: Any,
        error: dict[str, Any] | None,
    ) -> list[ACPMessage]:
        """Обрабатывает response на ожидаемый RPC request.
        
        Args:
            kind: 'fs_read', 'fs_write', 'terminal_create'
            result: Результат от клиента (если success)
            error: Ошибка от клиента (если error)
        
        Returns:
            Списокupdate notifications для tool_call
        """
```

**Внутренние утилиты:**
```python
def _validate_fs_kind(kind: str) -> bool:
    """Проверяет валидность fs kind."""

def _extract_fs_response_content(result: Any, kind: str) -> str | None:
    """Извлекает контент из fs RPC response."""

def _build_terminal_response_content(result: Any) -> str:
    """Построение контента для terminal RPC response."""

def _handle_fs_read_response(...) -> list[ACPMessage]:
    """Обработка fs/read_text_file response."""

def _handle_fs_write_response(...) -> list[ACPMessage]:
    """Обработка fs/write_text_file response."""

def _handle_terminal_response(...) -> list[ACPMessage]:
    """Обработка terminal/create response."""
```

**Unit-тесты:** `acp-server/tests/test_client_rpc_handler.py`
- ✅ can_use_fs_rpc для read и write
- ✅ can_use_terminal_rpc
- ✅ can_run_tools общая проверка
- ✅ normalize_path для absolute/relative путей
- ✅ prepare_fs_read_request структура и валидация
- ✅ prepare_fs_write_request
- ✅ prepare_terminal_request
- ✅ handle_pending_response для fs_read success
- ✅ handle_pending_response для fs_write success
- ✅ handle_pending_response для terminal success
- ✅ handle_pending_response для error cases
- ✅ 200+ строк тестов

---

## 🔗 Зависимости между компонентами

```
ToolCallHandler
├── SessionState.tool_calls
├── SessionState.tool_call_counter
└── ACPMessage (notifications)

PermissionManager
├── SessionState.permission_policy
├── SessionState.active_turn
└── ACPMessage (request, notifications)

ClientRPCHandler
├── SessionState.runtime_capabilities
├── SessionState.active_turn
├── SessionState.tool_calls (through ToolCallHandler)
├── PreparedFsClientRequest
└── ACPMessage (request, notifications)
```

**Порядок инициализации в PromptOrchestrator (Этап 5):**
1. ToolCallHandler (базовый)
2. PermissionManager (базовый)
3. ClientRPCHandler (использует ToolCallHandler)

---

## 📊 Метрики кода

| Компонент | Строк кода | Строк тестов | Интеграционные точки |
|-----------|-----------|--------------|------------------|
| **ToolCallHandler** | ~140 | ~150 | prompt.py, core.py |
| **PermissionManager** | ~100 | ~120 | prompt.py, core.py |
| **ClientRPCHandler** | ~150 | ~180 | prompt.py, core.py |
| **Итого** | ~390 | ~450 | - |

---

## 📝 План исполнения

### Этап 2.1: ToolCallHandler (~2 часа работы)

**Шаги:**
1. Создать файл [`tool_call_handler.py`](acp-server/src/acp_server/protocol/handlers/tool_call_handler.py)
2. Переместить функции из [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py):
   - `create_tool_call()`
   - `update_tool_call_status()`
   - `cancel_active_tool_calls()`
   - `build_executor_tool_execution_updates()`
   - `build_policy_tool_execution_updates()`
   - `resolve_tool_title()` (helper)
3. Инкапсулировать в класс `ToolCallHandler`
4. Добавить методы для построения notifications
5. Написать unit-тесты (150 строк)
6. Обновить импорты в [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)

**Контрольные точки:**
- ✅ Класс создан и скомпилируется
- ✅ Все функции переместены без изменения логики
- ✅ Старые тесты все еще проходят
- ✅ Новые unit-тесты на 90%+ покрытие

### Этап 2.2: PermissionManager (~2 часа работы)

**Шаги:**
1. Создать файл [`permission_manager.py`](acp-server/src/acp_server/protocol/handlers/permission_manager.py)
2. Переместить функции из [`permissions.py`](acp-server/src/acp_server/protocol/handlers/permissions.py):
   - `extract_permission_outcome()`
   - `extract_permission_option_id()`
   - `resolve_permission_option_kind()`
   - `resolve_remembered_permission_decision()`
   - `build_permission_options()`
   - `find_session_by_permission_request_id()`
3. Добавить методы для permission request construction
4. Добавить методы для decision handling
5. Написать unit-тесты (120 строк)
6. Обновить импорты в [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)

**Контрольные точки:**
- ✅ Класс создан и работает
- ✅ Функции переместены и тестированы
- ✅ Permission policy logic корректно работает

### Этап 2.3: ClientRPCHandler (~3 часа работы)

**Шаги:**
1. Создать файл [`client_rpc_handler.py`](acp-server/src/acp_server/protocol/handlers/client_rpc_handler.py)
2. Переместить функции из [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py):
   - `can_run_tool_runtime()` → `can_run_tools()`
   - `can_use_fs_client_rpc()` → `can_use_fs_rpc()`
   - `can_use_terminal_client_rpc()` → `can_use_terminal_rpc()`
   - `normalize_session_path()` → `normalize_path()`
   - `build_fs_client_request()` (разложить на read/write)
   - `build_terminal_client_request()`
3. Добавить методы для response handling
4. Добавить поддержку error cases
5. Написать unit-тесты (180 строк)
6. Обновить импорты в [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)

**Контрольные точки:**
- ✅ Класс создан и функционален
- ✅ FS и Terminal RPC работают
- ✅ Обработка response/error корректна

### Этап 2.4: Интеграция и тестирование (~2 часа работы)

**Шаги:**
1. Обновить импорты в [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py):
   - Удалить переместившиеся функции
   - Импортировать классы новых обработчиков
2. Проверить, что все существующие тесты все еще проходят
3. Запустить `make check`:
   - pytest: должно пройти 241+ тест
   - ruff check
   - type check
4. Обновить [`acp-server/README.md`](acp-server/README.md) с описанием новых компонентов
5. Обновить [`REFACTORING_STATUS.md`](acp-server/REFACTORING_STATUS.md)

**Контрольные точки:**
- ✅ make check проходит полностью
- ✅ Все 241+ тест проходят
- ✅ Type checking в strict mode
- ✅ Нет regression в функциональности

---

## 🧪 Стратегия тестирования

### Unit-тесты ToolCallHandler (150 строк)

```python
# test_tool_call_handler.py

class TestToolCallHandlerCreation:
    def test_create_tool_call_incremental_id(self):
        # call_001, call_002, ...
    
    def test_create_tool_call_records_in_session(self):
        # session.tool_calls заполняется корректно

class TestToolCallHandlerStatusUpdates:
    def test_update_pending_to_in_progress(self):
    def test_update_in_progress_to_completed(self):
    def test_reject_invalid_transition(self):
        # completed -> in_progress должно быть отклонено
    def test_update_with_content(self):

class TestToolCallHandlerExecutor:
    def test_executor_mode_in_progress_then_completed(self):
    def test_executor_mode_leave_running(self):

class TestToolCallHandlerPolicy:
    def test_policy_allowed_in_progress_then_completed(self):
    def test_policy_rejected_cancelled(self):

class TestToolCallHandlerCancellation:
    def test_cancel_all_active_tools(self):
    def test_cancel_ignores_completed_tools(self):

class TestToolCallHandlerNotifications:
    def test_tool_call_notification_structure(self):
    def test_tool_update_notification_structure(self):
```

### Unit-тесты PermissionManager (120 строк)

```python
# test_permission_manager.py

class TestPermissionManagerDecision:
    def test_should_request_for_default(self):
    def test_should_not_request_for_allow_always(self):
    def test_should_not_request_for_reject_always(self):

class TestPermissionManagerRemembered:
    def test_get_remembered_allow(self):
    def test_get_remembered_reject(self):
    def test_get_remembered_default_ask(self):

class TestPermissionManagerRequest:
    def test_build_permission_request_message(self):
    def test_permission_options_structure(self):

class TestPermissionManagerExtraction:
    def test_extract_outcome_acp_format(self):
    def test_extract_outcome_legacy_format(self):
    def test_extract_option_id_acp_format(self):
    def test_extract_option_id_legacy_format(self):

class TestPermissionManagerAcceptance:
    def test_acceptance_allow_once_no_policy_save(self):
    def test_acceptance_allow_always_saves_policy(self):
    def test_acceptance_reject_always_saves_policy(self):

class TestPermissionManagerSessionFinding:
    def test_find_session_by_permission_request_id(self):
    def test_find_session_missing(self):
```

### Unit-тесты ClientRPCHandler (180 строк)

```python
# test_client_rpc_handler.py

class TestClientRPCHandlerCapabilities:
    def test_can_use_fs_read_true(self):
    def test_can_use_fs_read_false(self):
    def test_can_use_fs_write_true(self):
    def test_can_use_terminal_true(self):
    def test_can_run_tools_any_capability(self):

class TestClientRPCHandlerPathNormalization:
    def test_normalize_absolute_path(self):
    def test_normalize_relative_path(self):
    def test_normalize_invalid_path(self):

class TestClientRPCHandlerFsRead:
    def test_prepare_fs_read_request_structure(self):
    def test_prepare_fs_read_creates_tool_call(self):
    def test_prepare_fs_read_invalid_path(self):
    def test_prepare_fs_read_capability_check(self):

class TestClientRPCHandlerFsWrite:
    def test_prepare_fs_write_request_structure(self):
    def test_prepare_fs_write_creates_tool_call(self):

class TestClientRPCHandlerTerminal:
    def test_prepare_terminal_request_structure(self):
    def test_prepare_terminal_creates_tool_call(self):

class TestClientRPCHandlerResponseHandling:
    def test_handle_fs_read_success_response(self):
    def test_handle_fs_write_success_response(self):
    def test_handle_terminal_success_response(self):
    def test_handle_response_error_case(self):
```

---

## 🔄 Миграция из prompt.py

### Функции для переместить в ToolCallHandler:
```python
# Из prompt.py (строки ~1487-1566)
- create_tool_call()
- update_tool_call_status()
- cancel_active_tool_calls()
- build_executor_tool_execution_updates()
- build_policy_tool_execution_updates()

# Helpers
- resolve_tool_title()
```

### Функции для консолидировать в PermissionManager:
```python
# Из permissions.py
- extract_permission_outcome()
- extract_permission_option_id()
- resolve_permission_option_kind()
- resolve_remembered_permission_decision()
- build_permission_options()
- find_session_by_permission_request_id()
```

### Функции для переместить в ClientRPCHandler:
```python
# Из prompt.py (строки ~1426-1423)
- can_run_tool_runtime()
- can_use_fs_client_rpc()
- can_use_terminal_client_rpc()
- normalize_session_path()
- build_fs_client_request()
- build_terminal_client_request()
```

### Функции для оставить в prompt.py (поддержка):
```python
# Будут использоваться новыми обработчиками
- normalize_stop_reason()
- resolve_prompt_stop_reason()
- normalize_tool_kind()
- normalize_plan_entries()
- build_plan_entries()
- finalize_active_turn()
- find_session_by_pending_client_request_id()
- resolve_pending_client_rpc_response_impl()
```

---

## ✅ Критерии успеха

1. **Функциональность:** Все переместившиеся функции работают идентично исходному коду
2. **Тесты:** 450+ новых unit-тестов на 90%+ покрытие кода обработчиков
3. **Качество:** `make check` проходит полностью без регрессий
4. **Совместимость:** ACP протокол полностью соблюдается
5. **Документация:** README обновлена с описанием новых компонентов

---

## ⚠️ Потенциальные риски

| Риск | Вероятность | Импакт | Стратегия |
|------|-----------|------|----|
| **Регрессия функциональности** | Средняя | Высокий | Comprehensive unit + regression tests |
| **Нарушение ACP протокола** | Низкая | Критический | Валидация protocol tests |
| **Performance деградация** | Низкая | Средний | Benchmark tests |
| **Type safety** | Низкая | Средний | Strict mypy mode |
| **Circular imports** | Средняя | Высокий | Осторожность с импортами |

---

## 📚 Ссылки на исходный код

- [`prompt.py:1487-1566`](acp-server/src/acp_server/protocol/handlers/prompt.py:1487) — Tool call functions
- [`prompt.py:1426-1485`](acp-server/src/acp_server/protocol/handlers/prompt.py:1426) — Client RPC functions
- [`permissions.py:14-211`](acp-server/src/acp_server/protocol/handlers/permissions.py:14) — Permission functions
- [`state.py`](acp-server/src/acp_server/protocol/state.py) — Data structures
- [`models.py`](acp-server/src/acp_server/models.py) — Pydantic models

---

**Документ создан:** 2026-04-12  
**Версия:** 1.0  
**Статус:** 📋 Ready for implementation
