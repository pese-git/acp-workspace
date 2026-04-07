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

- `load_session_parsed(...)` — возвращает типизированные `session/update` события.
- `load_session_tool_updates(...)` — возвращает только события tool call.
- `load_session_plan_updates(...)` — возвращает только события `plan`.
- `list_sessions(...)` и `list_all_sessions(...)` — работа с `session/list` и cursor-пагинацией.

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
