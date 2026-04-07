# ACP Client

Клиентская часть Agent Client Protocol (ACP) с WebSocket транспортом.

## Установка

```bash
uv sync
```

## Использование

```bash
uv run acp-client --host 127.0.0.1 --port 8080 --method ping
uv run acp-client --host 127.0.0.1 --port 8080 --method echo --params '{"message":"hello"}'
uv run acp-client --host 127.0.0.1 --port 8080 --method session/load --params '{"sessionId":"sess_1","cwd":"/tmp","mcpServers":[]}' --show-updates
```

## Полезные helper-методы ACPClient

- `initialize(...)` — выполняет handshake и возвращает типизированный результат согласования.
- `authenticate(...)` — типизированный helper для ACP `authenticate`.
- `prompt(...)` — типизированный helper для `session/prompt` с optional `_meta.promptDirectives`.
- `open_ws_session().prompt(...)` — typed helper для `session/prompt` в persistent WS-сессии.
- `open_ws_session().authenticate(...)` — typed helper для `authenticate` в persistent WS-сессии.
- `create_session_parsed(...)` — типизированный helper для ответа `session/new`.
- `load_session_setup_parsed(...)` — типизированный helper для ответа `session/load` и replay updates.
- `load_session_parsed(...)` — возвращает типизированные `session/update` события.
- `load_session_structured_updates(...)` — возвращает только известные типизированные payload `session/update`.
- `set_config_option_with_updates(...)` — меняет config option и возвращает типизированные update-события.
- `load_session_tool_updates(...)` — возвращает только события tool call.
- `load_session_plan_updates(...)` — возвращает только события `plan`.
- `list_sessions(...)` и `list_all_sessions(...)` — работа с `session/list` и cursor-пагинацией.
- `list_sessions_parsed(...)` и `list_all_sessions_parsed(...)` — типизированный разбор ответа `session/list`.

## Поведение WebSocket

- Перед вызовами `session/*` клиент автоматически выполняет `initialize` в рамках WS-соединения.
- Если в `initialize` возвращены `authMethods`, клиент автоматически выполняет `authenticate` перед `session/*` (можно отключить через `auto_authenticate=False`).
- Можно указать `preferred_auth_method_id`, чтобы выбрать конкретный advertised auth method вместо первого в списке.
- Для API key auth можно передать `auth_api_key` в `ACPClient(...)`; тогда ключ отправится в `authenticate` как `params.apiKey`.
- В auto-initialize отправляются baseline `clientCapabilities` (`fs.readTextFile=false`, `fs.writeTextFile=false`, `terminal=false`).
- Для нескольких запросов в одном WS-канале используйте `open_ws_session()`; `initialize` выполняется один раз на соединение.

Профиль транспорта клиента: только WebSocket.

## Логирование

Клиент поддерживает структурированное логирование с настраиваемым уровнем и форматом.

### Уровни логирования

```bash
# DEBUG - подробная информация для отладки
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level DEBUG

# INFO - основные события (default)
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level INFO

# WARNING - предупреждения
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level WARNING

# ERROR - только ошибки
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level ERROR
```

### JSON формат

Для production окружения можно использовать JSON формат:

```bash
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-json
```

Пример вывода:
```json
{"event": "client_started", "host": "127.0.0.1", "port": 8080, "method": "ping", "timestamp": "2026-04-07T20:00:00.000000Z", "level": "info"}
{"event": "ws_request_sent", "method": "ping", "timestamp": "2026-04-07T20:00:00.100000Z", "level": "debug"}
```

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
