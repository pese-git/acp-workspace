# ACP Server

Серверная часть Agent Client Protocol (ACP) с транспортами:

- TCP (NDJSON over socket)
- HTTP (`POST /acp`)
- WebSocket (`GET /acp/ws`)

## Установка

```bash
uv sync
```

## Запуск

```bash
uv run acp-server --transport tcp --host 127.0.0.1 --port 8765
uv run acp-server --transport http --host 127.0.0.1 --port 8080
```

## ACP методы

- `initialize`
- `ping`
- `echo`
- `shutdown`

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
