# CodeLab

Унифицированная реализация ACP (Agent Client Protocol) — сервер агента и клиент в одном пакете.

## Установка

```bash
# Базовая установка
uv pip install -e .

# С поддержкой сервера
uv pip install -e ".[server]"

# С TUI клиентом
uv pip install -e ".[tui]"

# Полная установка
uv pip install -e ".[full]"
```

## Структура проекта

```
codelab/
├── src/codelab/
│   ├── shared/           # Общие модули
│   │   ├── messages.py   # JSON-RPC сообщения
│   │   ├── logging.py    # Структурированное логирование
│   │   └── content/      # Типы контента ACP
│   ├── server/           # Серверная часть (агент)
│   └── client/           # Клиентская часть (TUI)
```

## CLI

После установки доступна команда `codelab`:

```bash
# Справка
codelab --help

# Запуск сервера агента
codelab serve --port 8765

# Запуск TUI клиента
codelab client ws://localhost:8765
```

## Использование

### Shared модули

```python
from codelab.shared import ACPMessage, JsonRpcError, setup_logging
from codelab.shared.content import TextContent, ImageContent

# Создание JSON-RPC сообщения
msg = ACPMessage.request("session/prompt", {"prompt": "Hello"})

# Настройка логирования
logger = setup_logging(level="DEBUG", log_file="default")
logger.info("app_started", version="1.0.0")
```

## Разработка

```bash
# Установка dev-зависимостей
uv pip install -e ".[dev]"

# Проверка кода
uv run ruff check src/
uv run ty check

# Запуск тестов
uv run pytest
```
