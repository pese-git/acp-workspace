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
```

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
