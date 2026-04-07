# ACP Protocol Workspace

Монорепозиторий с двумя независимыми Python-проектами:

- `acp-server` — ACP-сервер с транспортами HTTP/WebSocket
- `acp-client` — ACP-клиент с транспортами HTTP/WebSocket

Каждый подпроект содержит собственные `pyproject.toml`, `uv.lock`, тесты и CLI-команды.

## Требования

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Установка зависимостей

Из корня репозитория:

```bash
make server-sync client-sync
```

или отдельно:

```bash
uv sync --directory acp-server
uv sync --directory acp-client
```

## Быстрый старт

1) Запустить сервер (HTTP/WS):

```bash
make run-server-http
```

2) Отправить запрос с клиента:

```bash
make ping-http
```

Для WebSocket:

```bash
make ping-ws
```

## Поддерживаемые методы

- `initialize`
- `session/new`
- `session/load`
- `session/list`
- `session/prompt`
- `session/cancel`
- `session/set_config_option`

Временные legacy-методы (для обратной совместимости):

- `ping`
- `echo`
- `shutdown`

## Проверки

Полный набор проверок для обоих подпроектов:

```bash
make check
```

Что включает `make check`:

- `ruff check`
- `ty check`
- `python -m pytest`

## Структура репозитория

- `acp-server/` — серверная реализация ACP
- `acp-client/` — клиентская реализация ACP
- `doc/ACP/` — рабочие материалы и спецификация ACP
