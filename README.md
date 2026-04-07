# ACP Protocol Workspace

Монорепозиторий с двумя независимыми Python-проектами:

- `acp-server` — ACP-сервер с транспортами TCP и HTTP/WebSocket
- `acp-client` — ACP-клиент с транспортами TCP, HTTP и WebSocket

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

1) Запустить сервер (TCP):

```bash
make run-server-tcp
```

2) Отправить запрос с клиента:

```bash
make ping-tcp
```

Для HTTP/WebSocket:

```bash
make run-server-http
make ping-http
make ping-ws
```

## Поддерживаемые методы

- `initialize`
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
