# ACP Protocol Workspace

Монорепозиторий с двумя независимыми Python-проектами:

- `acp-server` — ACP-сервер с WebSocket транспортом
- `acp-client` — ACP-клиент с WebSocket транспортом

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

1) Запустить сервер (WS):

```bash
make run-server-ws
# с обязательной аутентификацией
uv run --directory acp-server acp-server --host 127.0.0.1 --port 8080 --require-auth
# с local API key backend для authenticate
uv run --directory acp-server acp-server --host 127.0.0.1 --port 8080 --require-auth --auth-api-key dev-secret
```

2) Отправить запрос с клиента:

```bash
make ping-ws
```

## Поддерживаемые методы

### Agent-side методы (Client → Agent)

- `authenticate` — аутентификация клиента
- `initialize` — инициализация соединения и negotiation capabilities
- `session/new` — создание новой сессии
- `session/load` — загрузка существующей сессии
- `session/list` — список сессий с пагинацией
- `session/prompt` — отправка промпта агенту
- `session/cancel` — отмена текущей операции
- `session/set_config_option` — изменение конфигурации сессии
- `session/set_mode` — изменение режима сессии (legacy, используйте `configOptions`)

### Client-side методы (Agent → Client)

- `session/request_permission` — запрос разрешения на выполнение операции
- `fs/read_text_file` — чтение текстового файла
- `fs/write_text_file` — запись текстового файла
- `terminal/create` — создание терминала
- `terminal/output` — получение вывода терминала
- `terminal/wait_for_exit` — ожидание завершения команды
- `terminal/kill` — принудительное завершение команды
- `terminal/release` — освобождение терминала

### Notifications (Agent → Client)

- `session/update` — уведомления о ходе выполнения (tool_call, plan, message chunks и др.)

Профиль реализации в этом репозитории: только ACP over WebSocket (`GET /acp/ws`).

### Legacy-методы (для обратной совместимости)

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

## Архитектура

Подробное описание архитектуры проекта см. в [ARCHITECTURE.md](ARCHITECTURE.md).

Ключевые компоненты:
- **Protocol Layer** — модульная реализация ACP методов через handlers
- **Transport Layer** — WebSocket с асинхронной обработкой
- **Storage Layer** — plug-and-play backends (InMemoryStorage, JsonFileStorage)
- **Logging Layer** — структурированное логирование с structlog

## Структура репозитория

- `acp-server/` — серверная реализация ACP
- `acp-client/` — клиентская реализация ACP
- `doc/Agent Client Protocol/` — рабочие материалы и спецификация ACP
- `doc/ACP_IMPLEMENTATION_STATUS.md` — матрица соответствия и приоритетный backlog
