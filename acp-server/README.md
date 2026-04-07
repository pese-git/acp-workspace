# ACP Server

Серверная часть Agent Client Protocol (ACP) с WebSocket транспортом:

- WebSocket (`GET /acp/ws`)

## Установка

```bash
uv sync
```

## Запуск

```bash
uv run acp-server --host 127.0.0.1 --port 8080
# или с обязательной аутентификацией
uv run acp-server --host 127.0.0.1 --port 8080 --require-auth
# с локальным API key backend для authenticate
uv run acp-server --host 127.0.0.1 --port 8080 --require-auth --auth-api-key dev-secret
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

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
