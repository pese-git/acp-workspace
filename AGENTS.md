# AGENTS

Инструкции для агентных ассистентов в этом репозитории.

## Контекст проекта

- Монорепозиторий из двух независимых Python-проектов:
  - `acp-server/`
  - `acp-client/`
- Менеджер окружения и запуск команд: `uv`
- Базовые проверки запускаются через `Makefile` из корня.

## Рабочие правила

- Вносить минимальные и целевые изменения, не трогать лишние файлы.
- Не менять публичные интерфейсы CLI без явной необходимости.
- Сохранять совместимость с Python 3.12+.
- Следовать текущему стилю кода (типизация, простые функции, явные имена).
- Не добавлять зависимости без необходимости.
- Документацию вести на русском языке
- Весь код должен иметь осмысленные коментарии

## Обязательная проверка после изменений

Из корня репозитория:

```bash
make check
```

Если изменения только в одном подпроекте, допускается локальная проверка:

```bash
uv run --directory acp-server ruff check .
uv run --directory acp-server ty check
uv run --directory acp-server python -m pytest
```

или:

```bash
uv run --directory acp-client ruff check .
uv run --directory acp-client ty check
uv run --directory acp-client python -m pytest
```

## Где что находится

- Сервер:
  - `acp-server/src/acp_server/protocol/` — модули протокола ACP:
    - `__init__.py` — экспорт публичных классов (ACPProtocol, ProtocolOutcome)
    - `core.py` — основной класс ACPProtocol
    - `state.py` — dataclasses состояния (SessionState, ToolCallState, и т.д.)
    - `handlers/` — обработчики методов протокола:
      - `auth.py` — методы аутентификации (authenticate, initialize)
      - `session.py` — управление сессиями (session/new, load, list)
      - `prompt.py` — обработка prompt-turn (session/prompt, cancel)
      - `permissions.py` — управление разрешениями (session/request_permission)
      - `config.py` — конфигурация сессий (session/set_config_option)
      - `legacy.py` — ping, echo, shutdown
  - `acp-server/src/acp_server/storage/` — хранилище сессий:
    - `base.py` — SessionStorage(ABC) интерфейс
    - `memory.py` — InMemoryStorage (development)
    - `json_file.py` — JsonFileStorage (production с persistence)
  - `acp-server/src/acp_server/http_server.py` — WebSocket транспорт
  - `acp-server/src/acp_server/logging.py` — структурированное логирование
  - `acp-server/src/acp_server/server.py` — TCP транспорт (legacy)
- Клиент:
  - `acp-client/src/acp_client/client.py` — TCP/WS запросы
  - `acp-client/src/acp_client/cli.py` — CLI
- Сообщения:
  - `acp-server/src/acp_server/messages.py`
  - `acp-client/src/acp_client/messages.py`

## Git-правила

- Не коммитить артефакты окружения и кэши (`.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`).
- Один логический блок изменений = один коммит.
- Сообщение коммита: коротко и по сути (что и зачем).

## Документация

- При изменении поведения обновлять соответствующие README (`README.md`, `acp-server/README.md`, `acp-client/README.md`).
- Для сверки с протоколом использовать материалы в `doc/ACP/`.
