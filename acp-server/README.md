# ACP Server

Серверная часть Agent Client Protocol (ACP) с WebSocket транспортом:

- WebSocket (`GET /acp/ws`)

## Установка

```bash
uv sync
```

## Запуск

### Базовый запуск (in-memory хранилище)

```bash
uv run acp-server --host 127.0.0.1 --port 8080
```

### С обязательной аутентификацией

```bash
uv run acp-server --host 127.0.0.1 --port 8080 --require-auth
```

### С локальным API key backend для authenticate

```bash
uv run acp-server --host 127.0.0.1 --port 8080 --require-auth --auth-api-key dev-secret
```

## Хранилище сессий

Сервер поддерживает два backends для хранения сессий:

### In-memory (по умолчанию)

Сессии хранятся в памяти процесса и теряются при перезапуске:

```bash
uv run acp-server --host 127.0.0.1 --port 8080
# или явно:
uv run acp-server --host 127.0.0.1 --port 8080 --storage memory
```

### JSON файловое хранилище (persistence)

Сессии сохраняются в JSON файлы для persistence между перезапусками:

```bash
# Сохранять сессии в ~/.acp/sessions
uv run acp-server --host 127.0.0.1 --port 8080 --storage json:~/.acp-server/sessions

# Или с абсолютным путем
uv run acp-server --host 127.0.0.1 --port 8080 --storage json:/var/lib/acp/sessions
```

Каждая сессия сохраняется в отдельный JSON файл (`{session_id}.json`) с полным состоянием включая:
- Текущую рабочую директорию
- Историю диалога
- Состояние tool calls
- Конфигурацию сессии
- Runtime capabilities клиента

**Пример:**

```bash
# Разработка с persistence (в домашней директории)
uv run acp-server --log-level DEBUG --storage json:~/.acp/sessions

# Production с JSON логами и хранилищем
uv run acp-server \
  --host 0.0.0.0 \
  --port 8080 \
  --require-auth \
  --auth-api-key $ACP_SERVER_API_KEY \
  --log-json \
  --storage json:/var/lib/acp/sessions
```

## Логирование

Сервер использует структурированное логирование с помощью `structlog` для удобного отслеживания событий.

### Уровни логирования

Поддерживаются следующие уровни логирования (по умолчанию `INFO`):

- `DEBUG` — детальная информация для отладки
- `INFO` — общая информация о работе сервера
- `WARNING` — предупреждения о потенциальных проблемах
- `ERROR` — ошибки, требующие внимания

### Development режим (консольный формат)

Для локальной разработки используется цветной консольный формат:

```bash
# Запуск с DEBUG уровнем (по умолчанию цветной консольный формат)
uv run acp-server --log-level DEBUG

# Запуск с INFO уровнем
uv run acp-server --log-level INFO

# Запуск с WARNING уровнем
uv run acp-server --log-level WARNING
```

Пример вывода (цветной консоль):

```
2026-04-07T15:41:00Z [info     ] server started                 endpoint=/acp/ws host=127.0.0.1 port=8080
2026-04-07T15:41:05Z [info     ] ws connection established      connection_id=abc12345 remote_addr=127.0.0.1:54321
2026-04-07T15:41:05Z [info     ] request received              connection_id=abc12345 method=initialize request_id=1 session_id=None
2026-04-07T15:41:10Z [info     ] request received              connection_id=abc12345 method=session/new request_id=2 session_id=sess-123
2026-04-07T15:41:15Z [info     ] ws connection closed          connection_id=abc12345 duration=10.234
```

### Production режим (JSON формат)

Для production используется JSON формат, удобный для парсинга системами логирования:

```bash
# Запуск с JSON форматом и INFO уровнем
uv run acp-server --log-level INFO --log-json

# Запуск с JSON форматом и DEBUG уровнем
uv run acp-server --log-level DEBUG --log-json
```

Пример вывода (JSON логи):

```json
{"timestamp": "2026-04-07T15:41:00Z", "level": "info", "event": "server started", "endpoint": "/acp/ws", "host": "127.0.0.1", "port": 8080}
{"timestamp": "2026-04-07T15:41:05Z", "level": "info", "event": "ws connection established", "connection_id": "abc12345", "remote_addr": "127.0.0.1:54321"}
{"timestamp": "2026-04-07T15:41:05Z", "level": "info", "event": "request received", "connection_id": "abc12345", "method": "initialize", "request_id": "1", "session_id": null}
{"timestamp": "2026-04-07T15:41:10Z", "level": "info", "event": "request received", "connection_id": "abc12345", "method": "session/new", "request_id": "2", "session_id": "sess-123"}
{"timestamp": "2026-04-07T15:41:15Z", "level": "info", "event": "ws connection closed", "connection_id": "abc12345", "duration": 10.234}
```

### Отслеживаемые события

- **server started** — запуск сервера (host, port, endpoint)
- **server shutting down** — остановка сервера
- **ws connection established** — новое WebSocket соединение (connection_id, remote_addr)
- **ws connection closed** — закрытие WebSocket соединения (connection_id, duration)
- **request received** — входящий ACP запрос (method, request_id, session_id)
- **request parse error** — ошибка парсинга запроса (request_id, error, traceback)
- **deferred prompt completed** — завершение отложенного prompt (connection_id, session_id)

## MCP Support

Сервер поддерживает подключение [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) серверов через параметр `mcpServers` в `session/new` и `session/load`.

### Конфигурация MCP серверов

```json
{
  "method": "session/new",
  "params": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"]
      },
      "database": {
        "command": "/usr/local/bin/mcp-postgres",
        "args": ["--connection-string", "postgresql://..."],
        "env": {
          "POSTGRES_PASSWORD": "secret"
        }
      }
    }
  }
}
```

### Как это работает

1. При создании сессии ACP сервер запускает указанные MCP серверы как subprocess
2. Выполняет MCP handshake (initialize) и получает список доступных tools
3. MCP tools регистрируются в ToolRegistry с namespace `mcp:{server_name}:{tool_name}`
4. LLM может вызывать MCP tools как обычные инструменты
5. При завершении сессии MCP процессы корректно завершаются

### Архитектура MCP интеграции

```
┌─────────────────────────────────────────────────────────────────┐
│                         ACP Server                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     ToolRegistry                          │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐│  │
│  │  │  Built-in Tools │  │        MCP Tools                 ││  │
│  │  │  - fs/read      │  │  - mcp:filesystem:read_file     ││  │
│  │  │  - terminal/run │  │  - mcp:database:query           ││  │
│  │  └─────────────────┘  └─────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      MCPManager                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │  │
│  │  │  MCPClient   │  │  MCPClient   │  │  MCPClient   │   │  │
│  │  │  (filesystem)│  │  (database)  │  │  (custom)    │   │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │  │
│  └─────────┼─────────────────┼─────────────────┼────────────┘  │
└────────────┼─────────────────┼─────────────────┼────────────────┘
             │ stdio           │ stdio           │ stdio
     ┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
     │  MCP Server   │ │  MCP Server   │ │  MCP Server   │
     │  (filesystem) │ │  (postgres)   │ │  (custom)     │
     └───────────────┘ └───────────────┘ └───────────────┘
```

### Модуль MCP

Реализация находится в `src/acp_server/mcp/`:

| Файл | Описание |
|------|----------|
| `models.py` | Pydantic модели MCP протокола |
| `transport.py` | StdioTransport для stdio коммуникации |
| `client.py` | MCPClient — клиент для MCP сервера |
| `tool_adapter.py` | Адаптер MCP tools → ToolDefinition |
| `manager.py` | MCPManager — управление несколькими серверами |
- **deferred prompt cancelled** — отмена отложенного prompt (connection_id, session_id)

## Content Types

Сервер поддерживает следующие типы контента согласно ACP спецификации:

- **TextContent** - текстовые сообщения
- **ImageContent** - изображения (base64, PNG, JPEG, GIF, WebP)
- **AudioContent** - аудиоданные (base64, WAV, MP3, MPEG)
- **EmbeddedResourceContent** - встроенные ресурсы
- **ResourceLinkContent** - ссылки на ресурсы

Реализация использует Pydantic dataclasses с валидацией и discriminated union для полиморфизма.

Подробнее см. [`doc/architecture/CONTENT_TYPES_ARCHITECTURE.md`](../../doc/architecture/CONTENT_TYPES_ARCHITECTURE.md)

## Клиентские методы (Agent → Client RPC)

Агент может вызывать методы на клиенте для доступа к локальной среде пользователя.

### ClientRPCService

Сервис для инициирования RPC вызовов на клиенте:

```python
from acp_server.client_rpc import ClientRPCService

# Создать сервис
rpc_service = ClientRPCService(
    send_request_callback=transport.send,
    client_capabilities=client_caps,
    timeout=30.0
)

# Прочитать файл на клиенте
content = await rpc_service.read_text_file(
    session_id="sess_123",
    path="/path/to/file.txt"
)

# Создать терминал на клиенте
terminal_id = await rpc_service.create_terminal(
    session_id="sess_123",
    command="npm",
    args=["test"]
)

# Получить output терминала
output = await rpc_service.terminal_output(
    session_id="sess_123",
    terminal_id=terminal_id,
    max_bytes=10000
)
```

### Поддерживаемые методы

#### File System
- `read_text_file(path, start_line, end_line)` — чтение текстовых файлов с поддержкой диапазонов строк
- `write_text_file(path, content, create, overwrite)` — запись текстовых файлов с контролем создания

#### Terminal
- `create_terminal(command, args, cwd)` — создание терминала и запуск команды
- `terminal_output(terminal_id, max_bytes)` — получение output терминала
- `wait_for_exit(terminal_id)` — ожидание завершения процесса
- `kill_terminal(terminal_id)` — принудительное завершение процесса
- `release_terminal(terminal_id)` — освобождение ресурсов терминала

### Особенности

- **Проверка возможностей:** Сервис проверяет `clientCapabilities` перед вызовом каждого метода
- **Управление timeout:** Автоматическое управление ожидающими запросами с таймаутом
- **Обработка ошибок:** Специализированные исключения для различных типов ошибок
- **Безопасность:** Валидация всех параметров перед отправкой на клиент

Подробнее см. [`doc/architecture/CLIENT_METHODS_ARCHITECTURE.md`](../../doc/architecture/CLIENT_METHODS_ARCHITECTURE.md)

## ACP методы

- `authenticate`
- `initialize`
- `session/new`
- `session/load`
- `session/list`
- `session/prompt`
- `session/cancel`
- `session/set_config_option`

Профиль транспорта: только WebSocket (`GET /acp/ws`).

### Поведение `initialize`

- Сервер ожидает обязательные поля `protocolVersion` (integer) и `clientCapabilities` (object).
- Поле `clientInfo` опционально, но если передано — должно быть объектом.
- Для WebSocket сначала должен быть выполнен `initialize`, иначе `session/*` запросы отклоняются.

### Поведение `session/prompt` и `session/cancel`

- Через WebSocket сервер поддерживает отложенное завершение prompt-turn.
- В режиме `ask` сервер отправляет клиенту JSON-RPC request `session/request_permission` перед выполнением tool call.
- Для compatibility поддержаны slash-команды `/plan`, `/tool`, `/tool-pending`.
- Для WS-оркестрации также поддерживаются structured overrides через `_meta.promptDirectives`.
- Legacy marker-триггеры (`[plan]`, `[tool]`, `[tool-pending]`) больше не обрабатываются.
- Если turn отменяется методом `session/cancel`, исходный `session/prompt` завершается с `stopReason: "cancelled"`.
- При разрыве WebSocket соединения сервер автоматически отменяет все активные turn этой
  connection (auto-cancel on disconnect), чтобы не оставлять зависшие in-flight операции.

### Поведение `authenticate`

- При запуске с `--require-auth` сервер возвращает `authMethods` в `initialize`.
- До успешного `authenticate` методы `session/new` и `session/load` возвращают ошибку `auth_required`.
- При запуске с `--auth-api-key` (или `ACP_SERVER_API_KEY`) метод `authenticate` требует `params.apiKey`.

### Поведение `session/list`

- Поддерживается фильтр по `cwd` (абсолютный путь).
- Поддерживается cursor-based пагинация через поля `cursor` и `nextCursor`.

Временные legacy-методы:

- `ping`
- `echo`
- `shutdown`

## Архитектура

Сервер построен на модульной архитектуре с четкой разделением ответственности между компонентами.

### Ядро протокола

**Transport Layer** — WebSocket сервер (см. [`http_server.py`](src/acp_server/http_server.py)):
- Обработка WebSocket соединений на `/acp/ws`
- Парсинг JSON-RPC сообщений от клиентов
- Обработка deferred responses для длительных операций
- Отправка `session/update` событий для real-time обновлений

**Protocol Layer** — логика протокола ACP (см. [`protocol/core.py`](src/acp_server/protocol/core.py)):
- `ACPProtocol` — главная точка диспетчеризации методов
- `ProtocolOutcome` — унифицированный результат обработки методов
- Модульные handlers для разных категорий методов

**Storage Layer** — подключаемые backend для хранения сессий:
- `SessionStorage(ABC)` — абстрактный интерфейс
- `InMemoryStorage` — для development и тестирования
- `JsonFileStorage` — для production с persistence на диск

### Компоненты рефакторинга Фазы 1

Фаза 1 критического рефакторинга завершена (241/241 тестов ✓). Реализованы следующие компоненты:

#### 1. Иерархия исключений ([`exceptions.py`](src/acp_server/exceptions.py))

Специализированные классы исключений для различных типов ошибок:

```python
ACPError (базовое)
├── ValidationError — ошибки валидации данных
├── AuthenticationError — ошибки аутентификации
├── AuthorizationError — ошибки авторизации
│   └── PermissionDeniedError — отказ в разрешении
├── StorageError — ошибки хранилища
│   ├── SessionNotFoundError — сессия не найдена
│   └── SessionAlreadyExistsError — дублирование ID
├── AgentProcessingError — ошибки обработки агентом
│   └── ToolExecutionError — ошибки выполнения tool
└── ProtocolError — ошибки протокола
    └── InvalidStateError — некорректное состояние
```

Использование специализированных исключений улучшает обработку ошибок и логирование.

#### 2. Pydantic модели ([`models.py`](src/acp_server/models.py))

Строго типизированные модели для замены `dict[str, Any]`:

- **Сообщения:** `MessageContent`, `HistoryMessage`
- **Команды:** `CommandParameter`, `AvailableCommand`
- **Планы:** `PlanStep`, `AgentPlan`
- **Tool calls:** `ToolCallParameter`, `ToolCall`
- **Разрешения:** `Permission`

Типизация обеспечивает:
- Валидацию данных при создании
- IDE автодополнение и type checking
- Лучшую документацию структур данных

#### 3. SessionFactory ([`protocol/session_factory.py`](src/acp_server/protocol/session_factory.py))

Фабрика для централизованного создания новых сессий:

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
    ) -> SessionState
```

Преимущества:
- Устраняет дублирование логики создания сессий
- Централизованная валидация параметров
- Автогенерация ID сессии
- Подготовка значений по умолчанию

#### 4. Разложение session_prompt — Этап 1/7

Начато разложение монолитной функции `session_prompt` (2151 строк) на специализированные обработчики (см. [`protocol/prompt_handlers/`](src/acp_server/protocol/prompt_handlers/)):

**PromptValidator** ([`prompt_handlers/validator.py`](src/acp_server/protocol/prompt_handlers/validator.py)):
- Валидация входных параметров prompt-turn
- Проверка состояния сессии (наличие active_turn)
- Валидация содержимого prompt (text, resource_link)
- Возврат `SessionState` если валидно, `ProtocolOutcome` с ошибкой если некорректно

**DirectiveResolver** ([`prompt_handlers/directive_resolver.py`](src/acp_server/protocol/prompt_handlers/directive_resolver.py)):
- Парсинг slash-команд из текста (`/tool`, `/plan`, `/fs-read`, `/term-run`)
- Разрешение directive overrides из `_meta.promptDirectives`
- Нормализация tool kinds и stop reasons
- Извлечение параметров из directives

Эти компоненты обеспечивают:
- Тестируемость отдельных функций без моков
- Переиспользование логики валидации и парсинга
- Четкое разделение ответственности
- Основу для дальнейших 6 этапов разложения

### Структура модулей

```
acp-server/src/acp_server/
├── exceptions.py             # Иерархия исключений (ФАЗ 1 ✓)
├── models.py                 # Pydantic модели типизации (ФАЗ 1 ✓)
├── protocol/
│   ├── core.py               # ACPProtocol класс
│   ├── state.py              # SessionState dataclasses
│   ├── session_factory.py    # SessionFactory (ФАЗ 1 ✓)
│   ├── handlers/
│   │   ├── auth.py           # authenticate, initialize
│   │   ├── session.py        # session/new, load, list
│   │   ├── prompt.py         # session/prompt, cancel (основная логика)
│   │   ├── permissions.py    # session/request_permission
│   │   ├── config.py         # session/set_config_option
│   │   ├── legacy.py         # ping, echo, shutdown
│   │   └── prompt_handlers/  # Разложение session_prompt (ФАЗ 1 ✓)
│   │       ├── __init__.py
│   │       ├── validator.py          # PromptValidator
│   │       ├── directive_resolver.py # DirectiveResolver
│   │       └── # 5 ещё компонентов в планах (ФАЗ 2-7)
│   └── storage/
│       ├── base.py           # SessionStorage интерфейс
│       ├── memory.py         # InMemoryStorage
│       └── json_file.py      # JsonFileStorage
└── # Остальные модули...
```

## Content Integration в Tool Calls

Начиная с Этапа 4, tool execution results поддерживают структурированный content для отправки клиенту и LLM.

### Архитектура

```
ToolExecutor → ToolExecutionResult (с content)
    ↓
ContentExtractor → ExtractedContent
    ↓
ContentValidator → валидация согласно ACP
    ↓
ContentFormatter → OpenAI/Anthropic format
    ↓
LLM Provider
```

### Поддерживаемые Content Types

- **text** - текстовый контент
- **diff** - изменения в файлах (unified diff format)
- **image** - изображения (base64)
- **audio** - аудио файлы (base64)
- **embedded** - вложенный контент
- **resource_link** - ссылки на ресурсы

### Пример использования

```python
from acp_server.tools.base import ToolExecutionResult

# Tool executor генерирует content
result = ToolExecutionResult(
    success=True,
    output="File written successfully",
    content=[
        {"type": "text", "text": "Successfully wrote file"},
        {"type": "diff", "path": "file.py", "diff": "+new line\n-old line"}
    ]
)

# Content автоматически извлекается, валидируется и форматируется для LLM
```

### Компоненты

- **[`ContentExtractor`](src/acp_server/protocol/content/extractor.py)** - извлечение content из результатов инструментов
- **[`ContentValidator`](src/acp_server/protocol/content/validator.py)** - валидация согласно ACP спецификации
- **[`ContentFormatter`](src/acp_server/protocol/content/formatter.py)** - форматирование для OpenAI и Anthropic API

### Документация

- [Архитектура Content Integration](../../doc/architecture/PROMPT_TURN_CONTENT_INTEGRATION_ARCHITECTURE.md)
- [Спецификация Content Types](../../doc/Agent%20Client%20Protocol/protocol/06-Content.md)
- [Tool Calls спецификация](../../doc/Agent%20Client%20Protocol/protocol/08-Tool%20Calls.md)

### E2E Testing

Полный набор E2E тестов для Content Integration находится в `tests/e2e/`:

```bash
# Запустить все E2E тесты
cd acp-server && uv run python -m pytest tests/e2e/ -v

# Запустить тесты для конкретного типа контента
uv run python -m pytest tests/e2e/test_e2e_text_content.py -v
```

**Покрытие:**
- 24 E2E теста
- Все 6 типов content (text, diff, image, audio, embedded, resource_link)
- Оба LLM провайдера (OpenAI, Anthropic)
- Полный цикл: Extraction → Validation → Formatting

**Архитектура тестов:**
- [`doc/architecture/CONTENT_INTEGRATION_E2E_TESTING_ARCHITECTURE.md`](../doc/architecture/CONTENT_INTEGRATION_E2E_TESTING_ARCHITECTURE.md)

## Tool Calls Integration

ACP сервер поддерживает встроенные инструменты для взаимодействия с локальной средой клиента:

### Файловая система (fs/*)

- **fs/read_text_file** - Чтение текстовых файлов
  - Параметры: `path`, `line` (опционально), `limit` (опционально)
  - Requires permission: `read`
  
- **fs/write_text_file** - Запись текстовых файлов
  - Параметры: `path`, `content`
  - Metadata: `diff` (unified diff формат)
  - Requires permission: `write`

### Терминал (terminal/*)

- **terminal/create** - Создание терминала и выполнение команды
  - Параметры: `command`, `args`, `env`, `cwd`, `output_byte_limit`
  - Metadata: `terminal_id`
  - Requires permission: `execute`
  
- **terminal/wait_for_exit** - Ожидание завершения процесса
  - Параметры: `terminal_id`
  - Metadata: `exit_code`
  
- **terminal/release** - Освобождение терминала
  - Параметры: `terminal_id`

### Permission Flow

В режиме `mode: "ask"` сервер запрашивает разрешение перед выполнением инструментов:

1. Агент возвращает tool calls в response
2. Сервер отправляет `session/request_permission` notification
3. Клиент отвечает через `session/respond_to_permission`
4. Сервер выполняет или отклоняет tool call

Поддерживаемые опции разрешений:
- `allow_once` - Разрешить один раз
- `allow_always` - Разрешить всегда (сохраняется в policy)
- `reject_once` - Отклонить один раз
- `reject_always` - Отклонить всегда (сохраняется в policy)

### Примеры использования

См. тесты в:
- `tests/test_fs_executors.py`
- `tests/test_terminal_executors.py`
- `tests/test_tool_integration.py`

### Тестирование

Подробное руководство по тестированию Tool Calls см. в [`doc/TOOL_CALLS_TESTING_GUIDE.md`](../doc/TOOL_CALLS_TESTING_GUIDE.md).

## Permission Management

ACP Server реализует комплексную систему управления разрешениями с автоматическим persistence.

### Возможности

**Session-Level Permissions:**
- `allow_once` - Разрешение для одного tool call
- `allow_always` - Разрешение для всех tool calls данного типа в сессии
- `reject_once` - Отклонение одного tool call
- `reject_always` - Отклонение всех tool calls данного типа в сессии

**Cross-Session Persistence:**
- Permission policies автоматически сохраняются при session save
- Policies автоматически восстанавливаются при session load
- No user re-prompts для already granted permissions
- Backward compatible с существующими сессиями

### Архитектура

**Компоненты:**
- [`SessionState.permission_policy`](src/acp_server/protocol/state.py) - Хранение policies (Dict[str, str])
- [`PermissionManager`](src/acp_server/protocol/handlers/permissions.py) - Decision logic
- [`JsonFileStorage`](src/acp_server/storage/json_file.py) - Serialization/deserialization
- [`resolve_remembered_permission_decision()`](src/acp_server/protocol/handlers/permissions.py) - Policy lookup

**Persistence Flow:**
```
User grants permission → SessionState.permission_policy["read"] = "allow_always"
                      ↓
                   session/save → JsonFileStorage → JSON file
                      ↓
                   session/load → _deserialize_session() → policy restored
                      ↓
                   resolve_remembered_permission_decision() → returns "allow"
```

### Тестирование

**51 permission-related тестов:**
- 15 flow tests ([`tests/test_permission_flow.py`](tests/test_permission_flow.py))
- 30 manager tests ([`tests/test_permission_manager.py`](tests/test_permission_manager.py))
- 6 persistence tests ([`tests/test_permission_policy_persistence.py`](tests/test_permission_policy_persistence.py))

**Запуск тестов:**
```bash
# Все permission тесты
uv run python -m pytest tests/test_permission*.py -v

# Только persistence тесты
uv run python -m pytest tests/test_permission_policy_persistence.py -v
```

### Документация

**Архитектурные документы:**
- [`doc/architecture/ADVANCED_PERMISSION_MANAGEMENT_ARCHITECTURE.md`](../doc/architecture/ADVANCED_PERMISSION_MANAGEMENT_ARCHITECTURE.md) - Полная архитектура с 4 диаграммами Mermaid
- [`doc/architecture/ADVANCED_PERMISSION_MANAGEMENT_ANALYSIS_REPORT.md`](../doc/architecture/ADVANCED_PERMISSION_MANAGEMENT_ANALYSIS_REPORT.md) - Анализ проблем и roadmap

**Протокол:**
- [`doc/Agent Client Protocol/protocol/05-Prompt Turn.md`](../doc/Agent%20Client%20Protocol/protocol/05-Prompt%20Turn.md) - Permission request/response flow

## Планирование задач (Agent Plan)

Агент поддерживает создание планов выполнения через инструмент `update_plan`.

### Как это работает

1. Агент получает сложную задачу
2. Вызывает `update_plan` с планом выполнения
3. План отображается в UI клиента
4. По мере выполнения агент обновляет статусы задач

### Тестирование flow планирования

**1. Запустить сервер:**
```bash
cd acp-server
cp .env.example .env  # настроить API ключ
uv run acp-server --log-level DEBUG
```

**2. Запустить клиент (в другом терминале):**
```bash
cd acp-client
uv run python -m acp_client.tui
```

**3. Отправить задачу для инициирования плана:**
```
Создай структуру проекта для REST API на FastAPI с файлами main.py, routes.py, models.py
```

Агент должен вызвать `update_plan` и план появится в панели.

### Формат плана

```json
{
  "entries": [
    {"content": "Создать main.py", "priority": "high", "status": "pending"},
    {"content": "Создать routes.py", "priority": "medium", "status": "pending"},
    {"content": "Создать models.py", "priority": "medium", "status": "pending"}
  ]
}
```

**Поля:**
- `priority`: `high`, `medium`, `low`
- `status`: `pending`, `in_progress`, `completed`, `cancelled`

### Unit тесты

```bash
uv run python -m pytest tests/test_plan*.py -v
```

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
