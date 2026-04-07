# ACP Server

Серверная часть Agent Client Protocol (ACP) с транспортами:

- HTTP (`POST /acp`)
- WebSocket (`GET /acp/ws`)

## Установка

```bash
uv sync
```

## Запуск

```bash
uv run acp-server --transport http --host 127.0.0.1 --port 8080
uv run acp-server --transport ws --host 127.0.0.1 --port 8080
```

## ACP методы

- `initialize`
- `session/new`
- `session/load`
- `session/list`
- `session/prompt`
- `session/cancel`
- `session/set_config_option`

### Поведение `initialize`

- Сервер ожидает обязательные поля `protocolVersion` (integer) и `clientCapabilities` (object).
- Поле `clientInfo` опционально, но если передано — должно быть объектом.

### Поведение `session/prompt` и `session/cancel`

- Через WebSocket сервер поддерживает отложенное завершение prompt-turn.
- В режиме `ask` сервер отправляет клиенту JSON-RPC request `session/request_permission` перед выполнением tool call.
- Для demo-сценариев с маркером `[plan]` сервер отправляет `session/update` с `sessionUpdate: "plan"`.
- Для demo-сценариев также поддержаны slash-команды `/plan`, `/tool`, `/tool-pending` (с fallback на старые маркеры).
- Если turn отменяется методом `session/cancel`, исходный `session/prompt` завершается с `stopReason: "cancelled"`.
- Через HTTP deferred-turn сразу финализируется в том же запросе, чтобы клиент всегда получил JSON-RPC response.

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
