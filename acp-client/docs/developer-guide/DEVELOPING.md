# Разработка acp-client

Руководство для разработчиков по настройке окружения и разработке TUI клиента Agent Client Protocol (ACP).

## Требования к окружению

- **Python**: 3.12 или выше
- **Менеджер зависимостей**: `uv` ([установка](https://docs.astral.sh/uv/getting-started/installation/))
- **Git**: для работы с версионированием

### Установка uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Или через Homebrew (macOS)
brew install uv
```

Проверка установки:
```bash
uv --version
```

## Развертывание окружения разработки

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd acp-protocol
```

### 2. Установка зависимостей

Из корня репозитория установите зависимости для `acp-client`:

```bash
uv sync --directory acp-client
```

Это создаст виртуальное окружение и установит все зависимости, включая dev-зависимости.

### 3. Проверка установки

```bash
uv run --directory acp-client python --version
```

Должна вывести Python 3.12 или выше.

## Запуск приложения

### TUI клиент (рекомендуется для разработки)

Основной интерфейс — Terminal UI на базе Textual:

```bash
# Запуск с параметрами по умолчанию (localhost:8000)
uv run --directory acp-client acp-client-tui

# Запуск с указанием host и port
uv run --directory acp-client acp-client-tui --host 127.0.0.1 --port 8080

# Запуск с заданной темой
uv run --directory acp-client acp-client-tui --theme dark
```

**Горячие клавиши TUI:**

| Клавиша | Функция |
|---------|---------|
| `Ctrl+N` | Новая сессия |
| `Ctrl+J` / `Ctrl+K` | Переключение между сессиями |
| `Ctrl+S` / `Ctrl+B` | Фокус на список сессий |
| `Tab` | Циклическое переключение фокуса |
| `Ctrl+Enter` | Отправить prompt |
| `Ctrl+R` | Повторить последнюю неуспешную операцию |
| `Up` / `Down` | История prompt в активной сессии |
| `Ctrl+Up` / `Ctrl+Down` | История prompt (многострочное редактирование) |
| `Ctrl+L` | Очистить чат |
| `Ctrl+H` | Показать встроенную подсказку |
| `Ctrl+F` | Поиск в просмотрщике файлов |
| `Ctrl+T` | Открыть полный terminal output последнего tool call |
| `Ctrl+C` | Cancel текущей операции |
| `Ctrl+Q` | Выход |

### CLI клиент

Для простых запросов используйте CLI:

```bash
# Ping
uv run --directory acp-client acp-client --host 127.0.0.1 --port 8080 --method ping

# Echo
uv run --directory acp-client acp-client --host 127.0.0.1 --port 8080 --method echo --params '{"message":"hello"}'

# Создание сессии
uv run --directory acp-client acp-client --host 127.0.0.1 --port 8080 --method session/new --params '{"cwd":"/tmp"}'

# Загрузка сессии
uv run --directory acp-client acp-client --host 127.0.0.1 --port 8080 --method session/load --params '{"sessionId":"sess_1","cwd":"/tmp","mcpServers":[]}'
```

Справка по командам:

```bash
uv run --directory acp-client acp-client --help
```

## Запуск тестов

### Все тесты

```bash
uv run --directory acp-client python -m pytest
```

### Конкретный тестовый файл

```bash
uv run --directory acp-client python -m pytest tests/test_cli.py
uv run --directory acp-client python -m pytest tests/test_tui_app.py
```

### Конкретный тест

```bash
uv run --directory acp-client python -m pytest tests/test_cli.py::test_help_command
```

### С подробным выводом

```bash
uv run --directory acp-client python -m pytest -v
```

### С информацией о покрытии

```bash
uv run --directory acp-client python -m pytest --cov=acp_client --cov-report=html
```

Отчет о покрытии будет в `htmlcov/index.html`.

### С останавливающей опцией при первой ошибке

```bash
uv run --directory acp-client python -m pytest -x
```

### Параллельный запуск тестов (если установлен pytest-xdist)

```bash
uv run --directory acp-client python -m pytest -n auto
```

## Запуск линтеров и type checker

### Ruff (linter)

```bash
# Проверка синтаксиса и стилевых ошибок
uv run --directory acp-client ruff check .

# Проверка конкретной директории
uv run --directory acp-client ruff check src/acp_client/tui/

# Исправление автоматических ошибок
uv run --directory acp-client ruff check --fix .
```

### Ruff (форматер)

```bash
# Проверка форматирования
uv run --directory acp-client ruff format . --diff

# Форматирование файлов
uv run --directory acp-client ruff format .
```

### Type checker (pyright через ty)

```bash
# Проверка типов
uv run --directory acp-client ty check
```

### Все проверки сразу (из корня репозитория)

```bash
# Рекомендуемый способ — запустить все проверки сразу
make check
```

Это выполнит:
- `ruff check` для обоих проектов
- Type checking (`ty`) для обоих проектов
- Тесты (`pytest`) для обоих проектов

### Предкоммит проверки

Если вы планируете делать коммиты часто, можно создать локальный git hook:

```bash
#!/bin/bash
# .git/hooks/pre-commit
cd acp-client
uv run ruff check . && uv run ty check && uv run pytest
```

## Структура проекта

```
acp-client/
├── src/acp_client/
│   ├── __init__.py
│   ├── cli.py                      # CLI интерфейс
│   ├── client.py                   # Основной ACP клиент
│   ├── logging.py                  # Структурированное логирование
│   ├── messages.py                 # Pydantic модели сообщений
│   │
│   ├── domain/                     # 🎯 Domain слой (бизнес-логика)
│   │   ├── __init__.py
│   │   ├── entities.py             # Доменные сущности
│   │   ├── events.py               # События домена
│   │   ├── repositories.py         # Интерфейсы репозиториев
│   │   └── services.py             # Доменные сервисы
│   │
│   ├── application/                # 📋 Application слой (use cases)
│   │   ├── __init__.py
│   │   ├── dto.py                  # Data Transfer Objects
│   │   ├── session_coordinator.py  # Координатор сессий
│   │   ├── state_machine.py        # State machine
│   │   └── use_cases.py            # Use cases
│   │
│   ├── infrastructure/             # 🔧 Infrastructure слой
│   │   ├── __init__.py
│   │   ├── di_container.py         # Dependency Injection контейнер
│   │   ├── logging_config.py       # Конфигурация логирования
│   │   └── services/
│   │       └── acp_transport_service.py  # Транспортный сервис
│   │
│   ├── presentation/               # 🎨 Presentation слой (MVVM)
│   │   ├── __init__.py
│   │   ├── base_view_model.py      # Базовый ViewModel
│   │   ├── observable.py           # Observable pattern
│   │   ├── chat_view_model.py
│   │   ├── session_view_model.py
│   │   ├── terminal_view_model.py
│   │   ├── permission_view_model.py
│   │   └── ...                     # Другие ViewModels
│   │
│   ├── tui/                        # 🖥️ TUI слой (Textual)
│   │   ├── __init__.py
│   │   ├── __main__.py             # Entry point TUI
│   │   ├── app.py                  # Главное приложение
│   │   ├── config.py               # Конфигурация TUI
│   │   ├── components/             # UI компоненты
│   │   │   ├── chat_view.py
│   │   │   ├── file_tree.py
│   │   │   ├── file_viewer.py
│   │   │   ├── header.py
│   │   │   ├── footer.py
│   │   │   ├── sidebar.py
│   │   │   ├── permission_modal.py
│   │   │   └── ...
│   │   ├── navigation/             # Навигация и управление состоянием
│   │   │   ├── manager.py
│   │   │   ├── tracker.py
│   │   │   ├── queue.py
│   │   │   └── operations.py
│   │   └── styles/
│   │       └── app.tcss            # Стили Textual CSS
│   │
│   ├── transport/                  # 🌐 Транспорт
│   │   ├── __init__.py
│   │   └── websocket.py            # WebSocket сессия
│   │
│   ├── handlers/                   # 🎯 Обработчики RPC запросов
│   │   ├── __init__.py
│   │   ├── permissions.py          # Обработка разрешений
│   │   ├── filesystem.py           # Обработка файловой системы
│   │   └── terminal.py             # Обработка терминала
│   │
│   └── helpers/                    # 🔧 Вспомогательные функции
│       ├── __init__.py
│       ├── auth.py                 # Аутентификация
│       └── session.py              # Парсинг session/update
│
├── tests/                          # 🧪 Тесты
│   ├── conftest.py                 # Fixtures и конфигурация pytest
│   ├── test_cli.py
│   ├── test_domain_entities.py
│   ├── test_tui_app.py
│   ├── test_navigation_*.py
│   └── ...                         # Другие тесты
│
├── docs/                           # 📚 Документация
│   ├── developer-guide/            # Для разработчиков
│   │   ├── ARCHITECTURE.md
│   │   ├── DEVELOPING.md
│   │   ├── TESTING.md
│   │   └── NAVIGATION_MANAGER.md
│   ├── user-guide/                 # Для пользователей
│   ├── roadmap/                    # План развития
│   └── archive/                    # Устаревшие документы
│
├── pyproject.toml                  # Конфигурация проекта
├── README.md                       # Основная документация
└── uv.lock                         # Lock файл зависимостей
```

### Основные слои архитектуры (Clean Architecture)

**Domain слой** (`src/acp_client/domain/`)
- Не зависит от других слоев
- Содержит сущности, события, интерфейсы репозиториев
- Чистая бизнес-логика

**Application слой** (`src/acp_client/application/`)
- Зависит только от Domain
- Реализует use cases и бизнес-правила
- Содержит координаторы и state machines

**Infrastructure слой** (`src/acp_client/infrastructure/`)
- Может зависеть от Domain и Application
- Реализует технические детали (DI, логирование, транспорт)
- Конкретные реализации интерфейсов

**Presentation слой** (`src/acp_client/presentation/`)
- ViewModels (MVVM паттерн)
- Зависит от Application и Infrastructure
- Observable pattern для reactive обновления UI

**TUI слой** (`src/acp_client/tui/`)
- Textual компоненты и управление UI
- Зависит от Presentation
- Navigation manager для управления навигацией

## Workflow разработки

### 1. Создание feature branch

```bash
git checkout -b feature/my-feature
```

### 2. Установка локального окружения

```bash
uv sync --directory acp-client
```

### 3. Написание тестов (TDD)

```bash
# Создайте тест в tests/
vim acp-client/tests/test_my_feature.py

# Запустите его
uv run --directory acp-client python -m pytest tests/test_my_feature.py -v
```

### 4. Реализация функциональности

```bash
# Редактируйте исходные файлы в src/acp_client/
vim acp-client/src/acp_client/domain/entities.py
```

### 5. Запуск проверок

```bash
# Из корня репозитория
make check

# Или локально в acp-client
cd acp-client
uv run ruff check .
uv run ty check
uv run pytest
```

### 6. Commit и push

```bash
git add acp-client/
git commit -m "feat: добавить функцию X в Y слой"
git push origin feature/my-feature
```

## Отладка

### Логирование

Проект использует `structlog` для структурированного логирования.

#### Уровни логирования в TUI

```bash
# DEBUG - подробная информация для отладки
uv run --directory acp-client acp-client-tui --log-level DEBUG --host 127.0.0.1 --port 8080

# INFO - основные события (default)
uv run --directory acp-client acp-client-tui --log-level INFO --host 127.0.0.1 --port 8080

# WARNING - предупреждения
uv run --directory acp-client acp-client-tui --log-level WARNING --host 127.0.0.1 --port 8080

# ERROR - только ошибки
uv run --directory acp-client acp-client-tui --log-level ERROR --host 127.0.0.1 --port 8080
```

#### Логирование в коде

```python
import structlog

logger = structlog.get_logger()

# Различные уровни
logger.info("event_name", key="value", number=42)
logger.warning("something_unusual", error=str(exc))
logger.error("critical_error", exception=exc)
logger.debug("detailed_info", variable=value)
```

### Отладка с breakpoint()

```python
def my_function():
    result = complex_calculation()
    breakpoint()  # Приложение остановится здесь
    return result
```

При вызове `breakpoint()` в TUI приложении он откроет `pdb` интерпретатор.

### Использование print для отладки (не рекомендуется)

```python
# Избегайте, используйте логирование вместо этого
print(f"Debug: {variable}")  # ❌
logger.debug("Debug info", variable=variable)  # ✅
```

### Отладка WebSocket соединений

```bash
# Запустите клиент с DEBUG логированием
uv run --directory acp-client acp-client-tui --log-level DEBUG --host 127.0.0.1 --port 8080
```

В логах будут видны все WebSocket сообщения.

### Отладка тестов

```bash
# Запустить с выводом print()
uv run --directory acp-client python -m pytest -s tests/test_cli.py

# Использовать pdb в тестах
uv run --directory acp-client python -m pytest --pdb tests/test_cli.py
```

## Полезные команды

### Обновление зависимостей

```bash
# Обновить lock файл
uv sync --directory acp-client --upgrade

# Обновить конкретный пакет
uv sync --directory acp-client --upgrade-package rich

# Синхронизировать без изменений (чистая установка)
uv sync --directory acp-client
```

### Добавление новой зависимости

```bash
# Добавить в production dependencies
uv add --directory acp-client requests

# Добавить в dev dependencies
uv add --directory acp-client --group dev pytest-cov
```

### Просмотр установленных пакетов

```bash
# Показать дерево зависимостей
uv pip freeze --directory acp-client
```

### Работа с виртуальным окружением

```bash
# Показать путь к venv
uv python-path --directory acp-client

# Активировать окружение (если нужно)
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### Быстрые проверки

```bash
# Проверить только синтаксис без автоисправления
uv run --directory acp-client ruff check . --diff

# Проверить определенный файл
uv run --directory acp-client ruff check src/acp_client/cli.py

# Форматирование для конкретной директории
uv run --directory acp-client ruff format src/acp_client/tui/
```

### Просмотр информации о проекте

```bash
# Показать конфигурацию Python
uv python info

# Показать версию uv
uv --version
```

## Полезные ссылки

- [README.md](../README.md) — основная документация
- [ARCHITECTURE.md](./ARCHITECTURE.md) — архитектура acp-client
- [TESTING.md](./TESTING.md) — стратегия тестирования
- [AGENTS.md](../../AGENTS.md) — правила разработки для обоих проектов
- [Textual документация](https://textual.textualize.io/)
- [Pydantic документация](https://docs.pydantic.dev/)
- [pytest документация](https://docs.pytest.org/)

## Решение типичных проблем

### Проблема: `ModuleNotFoundError: No module named 'acp_client'`

**Решение:** Убедитесь, что запускаете команды с флагом `--directory`:

```bash
uv run --directory acp-client python -m pytest
```

### Проблема: Старые зависимости в виртуальном окружении

**Решение:** Пересоздайте окружение:

```bash
rm -rf acp-client/.venv
uv sync --directory acp-client
```

### Проблема: Type checker выдает ошибки, которых нет в runtime

**Решение:** Обновите pyright/ty:

```bash
uv add --directory acp-client --group dev ty@latest
```

### Проблема: Тесты не найдены

**Решение:** Убедитесь, что файлы тестов начинаются с `test_`:

```bash
# Правильно
acp-client/tests/test_cli.py

# Неправильно
acp-client/tests/cli_test.py
```

### Проблема: TUI зависает при подключении к серверу

**Решение:** Проверьте, запущен ли ACP сервер:

```bash
# Откройте другой терминал и запустите сервер
cd acp-protocol
uv run --directory acp-server python -m acp_server.http_server --host 127.0.0.1 --port 8000
```

Затем подключитесь с правильным портом:

```bash
uv run --directory acp-client acp-client-tui --host 127.0.0.1 --port 8000
```

## Контакты и вопросы

При возникновении проблем:
1. Проверьте логи приложения (запустите с `--log-level DEBUG`)
2. Убедитесь, что окружение установлено корректно (`uv sync`)
3. Обновите зависимости (`uv sync --upgrade`)
4. Посмотрите существующие issues в репозитории
