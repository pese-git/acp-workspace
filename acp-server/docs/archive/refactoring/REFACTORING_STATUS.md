# Статус рефакторинга ACP Server

**Дата обновления:** 11 апреля 2026  
**Статус:** 🟢 Фаза 1 завершена (241/241 тестов ✓)

---

## 📋 Обзор рефакторинга

### Цели

Критический рефакторинг нацелен на разрешение архитектурных проблем в кодовой базе acp-server:

1. **Устранение монолитной архитектуры** — разложение гигантской функции `session_prompt` (2151 строк) на специализированные компоненты с четкой ответственностью
2. **Улучшение типизации** — замена `dict[str, Any]` на строго типизированные Pydantic модели
3. **Centralized Exception Handling** — создание иерархии специализированных исключений вместо generic Exception
4. **Eliminating Code Duplication** — выделение common patterns (SessionFactory для создания сессий)
5. **Enhanced Testability** — упрощение unit тестирования за счет разложения функций

### Влияние

После завершения Фазы 1:
- ✅ Код стал более модульным и переиспользуемым
- ✅ Улучшена типизация и IDE support
- ✅ Упрощена отладка через специализированные исключения
- ✅ Заложена база для дальнейшего разложения prompt-handler
- ✅ Все тесты пройдены без регрессий (241/241)

---

## 🟢 Фаза 1: Исходный рефакторинг (ЗАВЕРШЕНА)

### Выполненные работы

#### 1. ✅ Иерархия исключений

**Файл:** [`src/acp_server/exceptions.py`](src/acp_server/exceptions.py)

Создана специализированная иерархия исключений для различных типов ошибок:

```
ACPError (базовое исключение для всех ошибок ACP)
├── ValidationError — ошибки валидации входных данных
├── AuthenticationError — ошибки аутентификации
├── AuthorizationError — ошибки авторизации
│   └── PermissionDeniedError — отказ в разрешении на операцию
├── StorageError — ошибки работы с хранилищем сессий
│   ├── SessionNotFoundError — сессия не найдена
│   └── SessionAlreadyExistsError — сессия уже существует
├── AgentProcessingError — ошибки обработки агентом/LLM
│   └── ToolExecutionError — ошибки выполнения tool call
└── ProtocolError — ошибки протокола ACP
    └── InvalidStateError — операция невозможна в текущем состоянии
```

**Преимущества:**
- Явная типизация ошибок для обработки в handlers
- Лучшее логирование через специализированные исключения
- Возможность обработки разных ошибок по-разному на уровне транспорта

**Использование:**
```python
from acp_server.exceptions import ValidationError, SessionNotFoundError

try:
    session = await storage.load_session(session_id)
except SessionNotFoundError as e:
    logger.error(f"Session not found: {session_id}")
    return ProtocolOutcome.error("session_not_found", str(e))
except StorageError as e:
    logger.error(f"Storage error: {e}")
    return ProtocolOutcome.error("storage_error", str(e))
```

#### 2. ✅ Pydantic модели типизации

**Файл:** [`src/acp_server/models.py`](src/acp_server/models.py)

Введены строго типизированные Pydantic модели вместо `dict[str, Any]`:

**Модели сообщений:**
- `MessageContent` — содержимое сообщения (type, text, data)
- `HistoryMessage` — сообщение в истории (role, content, timestamp)

**Модели команд:**
- `CommandParameter` — параметр команды (name, type, description)
- `AvailableCommand` — доступная команда (name, description, parameters)

**Модели планов:**
- `PlanStep` — шаг плана (step_number, description, status, result)
- `AgentPlan` — план выполнения задачи (goal, steps, created_at, updated_at)

**Модели tool calls:**
- `ToolCallParameter` — параметр вызова (name, value)
- `ToolCall` — вызов инструмента (id, name, parameters, status, result, error)

**Модели разрешений:**
- `Permission` — разрешение на операцию (id, type, status, decision)

**Преимущества:**
- Валидация данных при создании (Pydantic автоматически проверяет типы)
- IDE автодополнение и type checking (PyRight)
- Self-documenting код (модель указывает на структуру данных)
- Экспорт в JSON и другие форматы
- Вспомогательные методы для работы с данными

**Использование:**
```python
from acp_server.models import HistoryMessage, ToolCall

# Валидированное создание
msg = HistoryMessage(
    role="assistant",
    content=[{"type": "text", "text": "Hello"}],
    timestamp="2026-04-11T12:00:00Z"
)

# Type-safe работа с данными
for content in msg.content:
    if content.type == "text":
        print(content.text)

# Экспорт в JSON
json_str = msg.model_dump_json()
```

#### 3. ✅ SessionFactory

**Файл:** [`src/acp_server/protocol/session_factory.py`](src/acp_server/protocol/session_factory.py)

Фабрика для централизованного создания новых сессий, устраняющая дублирование кода:

```python
class SessionFactory:
    @staticmethod
    def create_session(
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        config_values: dict[str, str] | None = None,
        available_commands: list[Any] | None = None,
        runtime_capabilities: ClientRuntimeCapabilities | None = None,
        session_id: str | None = None,
    ) -> SessionState:
        """Создает новую сессию с валидацией и подготовкой параметров."""
        ...
    
    @staticmethod
    def validate_session_params(params: dict) -> None:
        """Валидирует параметры создания сессии."""
        ...
```

**Функциональность:**
- Валидация обязательных параметров (cwd)
- Проверка типов опциональных параметров
- Автогенерация ID сессии если не указан (`sess_{uuid4_hex}`)
- Подготовка значений по умолчанию
- Фильтрация MCP-серверов

**Преимущества:**
- Единственный способ создания сессий
- Гарантирует консистентность инициализации
- Легче тестировать и модифицировать логику создания
- Определяет контракт для всех создателей сессий

**Использование:**
```python
from acp_server.protocol.session_factory import SessionFactory

# Создание новой сессии
session = SessionFactory.create_session(
    cwd="/home/user/project",
    mcp_servers=[{"name": "filesystem"}],
    config_values={"model": "gpt-4"},
    available_commands=[{"name": "/plan"}]
)

# SessionFactory автоматически сгенерирует ID и подготовит параметры
assert session.session_id.startswith("sess_")
assert session.cwd == "/home/user/project"
```

#### 4. ✅ Начало разложения session_prompt (Этап 1/7)

**Директория:** [`src/acp_server/protocol/prompt_handlers/`](src/acp_server/protocol/prompt_handlers/)

Начато разложение монолитной функции `session_prompt` (2151 строк) в файле [`handlers/prompt.py`](src/acp_server/protocol/handlers/prompt.py:240-2150) на специализированные компоненты.

**Архитектурный план:**

```
PromptOrchestrator (Этап 2 - планирование)
├── PromptValidator (Этап 1 ✓ ЗАВЕРШЕН)
├── DirectiveResolver (Этап 1 ✓ ЗАВЕРШЕН)
├── UpdateBuilder (Этап 3 - планирование)
├── ToolCallHandler (Этап 4 - планирование)
├── StateManager (Этап 5 - планирование)
├── TurnLifecycle (Этап 6 - планирование)
└── ClientRPCHandler (Этап 7 - планирование)
```

##### ✅ PromptValidator

**Файл:** [`src/acp_server/protocol/prompt_handlers/validator.py`](src/acp_server/protocol/prompt_handlers/validator.py)

Компонент валидации и подготовки данных prompt-turn:

```python
class PromptValidator:
    """Валидирует входные данные для prompt-turn."""
    
    def validate_input(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome | SessionState:
        """Валидирует sessionId, prompt array, content blocks."""
        ...
    
    def validate_content(
        self,
        request_id: JsonRpcId | None,
        prompt: list[Any],
    ) -> ACPMessage | None:
        """Валидирует содержимое prompt array."""
        ...
```

**Ответственность:**
- Валидация `sessionId` (наличие и корректность формата)
- Валидация `prompt` array (не пусто, все элементы — объекты)
- Валидация каждого content block (`text`, `resource_link`)
- Проверка состояния сессии (нет активного turn)
- Возврат `SessionState` если всё валидно, `ProtocolOutcome` ошибка если нет

**Тесты:** [`tests/test_prompt_validator.py`](../tests/test_prompt_validator.py) — 15+ unit тестов

##### ✅ DirectiveResolver

**Файл:** [`src/acp_server/protocol/prompt_handlers/directive_resolver.py`](src/acp_server/protocol/prompt_handlers/directive_resolver.py)

Компонент парсинга slash-команд и разрешения directives:

```python
class DirectiveResolver:
    """Разрешает prompt directives из текста и _meta."""
    
    def resolve_directives(
        self,
        *,
        params: dict[str, Any],
        text_preview: str,
        supported_tool_kinds: set[str] | None = None,
    ) -> PromptDirectives:
        """Формирует finalized prompt directives."""
        ...
    
    def extract_slash_commands(
        self,
        text_preview: str,
        supported_tool_kinds: set[str],
    ) -> PromptDirectives:
        """Парсит slash-команды из текста."""
        ...
    
    def apply_meta_overrides(
        self,
        directives: PromptDirectives,
        raw_meta: dict[str, Any] | None,
    ) -> PromptDirectives:
        """Применяет overrides из _meta.promptDirectives."""
        ...
```

**Ответственность:**
- Парсинг slash-команд: `/tool`, `/plan`, `/fs-read`, `/term-run` и т.д.
- Извлечение параметров из команд (`/tool:kind=shell`)
- Разрешение overrides из `_meta.promptDirectives` (приоритет над текстовыми командами)
- Нормализация tool kinds
- Нормализация stop reasons
- Определение stop reason на основе directives

**Тесты:** [`tests/test_directive_resolver.py`](../tests/test_directive_resolver.py) — 20+ unit тестов

---

## 📊 Метрики улучшений

### Тестирование

- **Общее количество тестов:** 241/241 ✓
- **Новые тесты (Фаза 1):** 35+ unit тестов для новых компонентов
- **Регрессии:** 0 (все существующие тесты проходят)
- **Покрытие:** Увеличено за счет unit тестов отдельных компонентов

### Качество кода

| Метрика | До рефакторинга | После Фазы 1 |
|---------|----------------|-------------|
| Функция session_prompt | 2151 строк | ~1900 строк (прогресс) |
| Типизация (Any вместо типов) | Высокая | ↓ Снижена (модели) |
| Дублирование кода создания сессий | Да (3+ места) | Нет (SessionFactory) |
| Специализированные исключения | Нет | Да (10+ типов) |
| Unit-тестируемые компоненты | Низко (много зависимостей) | Высоко (PromptValidator, DirectiveResolver) |

### Архитектурные улучшения

**Что улучшилось:**
- ✅ Появилась иерархия исключений (более явная обработка ошибок)
- ✅ Типизация данных Pydantic моделями (IDE support, валидация)
- ✅ Централизованное создание сессий (SessionFactory)
- ✅ Первые компоненты разложения монолитной функции (PromptValidator, DirectiveResolver)
- ✅ Основа для дальнейшего разложения (архитектурный план на 7 этапов)

**Что осталось:**
- ⏳ Полное разложение session_prompt (6 этапов из 7)
- ⏳ Миграция остального кода на новые исключения
- ⏳ Полная типизация всех структур данных

---

## 📈 План дальнейших работ

### Фаза 2: PromptOrchestrator (планирование)

Создание главного оркестратора для координации обработки prompt-turn:

```python
class PromptOrchestrator:
    """Координирует обработку prompt-turn через специализированные компоненты."""
    
    def __init__(self, validator: PromptValidator, resolver: DirectiveResolver, ...):
        self.validator = validator
        self.resolver = resolver
        # Остальные компоненты будут добавлены в Фазе 3-7
    
    async def handle_prompt(self, params: dict[str, Any]) -> ProtocolOutcome:
        """Главный метод обработки prompt."""
        # 1. Валидация входных данных (PromptValidator)
        # 2. Разрешение directives (DirectiveResolver)
        # 3. Построение updates (UpdateBuilder - Фаза 3)
        # 4. Обработка tool calls (ToolCallHandler - Фаза 4)
        # 5. Управление состоянием (StateManager - Фаза 5)
        # 6. Управление lifecycle (TurnLifecycle - Фаза 6)
        # 7. Обработка client RPC (ClientRPCHandler - Фаза 7)
```

### Фаза 3: UpdateBuilder

Компонент для построения `session/update` сообщений с notifications.

### Фаза 4: ToolCallHandler

Компонент для управления жизненным циклом tool calls (approval, denial, execution).

### Фаза 5: StateManager

Компонент для управления историей сообщений и метаданными сессии.

### Фаза 6: TurnLifecycle

Компонент для управления активным turn и его финализацией.

### Фаза 7: ClientRPCHandler

Компонент для обработки client RPC responses (fs, terminal, permissions).

---

## 🔗 Связанные документы

- **[REFACTORING_ANALYSIS.md](REFACTORING_ANALYSIS.md)** — детальный анализ проблем кодовой базы и рекомендации
- **[SESSION_PROMPT_REFACTORING_PLAN.md](SESSION_PROMPT_REFACTORING_PLAN.md)** — подробный архитектурный план разложения session_prompt
- **[README.md](README.md)** — обзор и использование новых компонентов в разделе "Архитектура"
- **[CHANGELOG.md](../CHANGELOG.md)** — запись о выполненном рефакторинге

## 🚀 Запуск проверок

```bash
# Полная проверка из корня репозитория
make check

# Или локально в acp-server
uv run ruff check .
uv run ty check
uv run python -m pytest
```

Все 241 тест успешно проходят после завершения Фазы 1 ✓
