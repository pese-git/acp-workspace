# ACP Client

Клиентская часть Agent Client Protocol (ACP) с поддержкой транспортов:

- HTTP
- WebSocket

## Установка

```bash
uv sync
```

## Использование

```bash
uv run acp-client --transport http --host 127.0.0.1 --port 8080 --method ping
uv run acp-client --transport ws --host 127.0.0.1 --port 8080 --method ping
uv run acp-client --transport http --host 127.0.0.1 --port 8080 --method echo --params '{"message":"hello"}'
uv run acp-client --transport ws --host 127.0.0.1 --port 8080 --method session/load --params '{"sessionId":"sess_1","cwd":"/tmp","mcpServers":[]}' --show-updates
```

## Полезные helper-методы ACPClient

- `initialize(...)` — выполняет handshake и возвращает типизированный результат согласования.
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
- В auto-initialize отправляются baseline `clientCapabilities` (`fs.readTextFile=false`, `fs.writeTextFile=false`, `terminal=false`).

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
