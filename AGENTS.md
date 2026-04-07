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
  - `acp-server/src/acp_server/protocol.py` — обработка ACP-методов
  - `acp-server/src/acp_server/server.py` — TCP транспорт
  - `acp-server/src/acp_server/http_server.py` — HTTP/WS транспорт
- Клиент:
  - `acp-client/src/acp_client/client.py` — TCP/HTTP/WS запросы
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
