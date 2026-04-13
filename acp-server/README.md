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
- **deferred prompt cancelled** — отмена отложенного prompt (connection_id, session_id)

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

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
