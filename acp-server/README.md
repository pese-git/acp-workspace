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
- `session/list`
- `session/prompt`
- `session/cancel`
- `session/set_config_option`

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
