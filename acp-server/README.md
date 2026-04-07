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
