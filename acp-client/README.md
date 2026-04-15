# ACP Client

Клиентская часть **Agent Client Protocol (ACP)** с WebSocket транспортом, реализованная на Python с использованием Clean Architecture и TUI интерфейса.

## 📚 Документация

Вся документация находится в директории [`docs/`](./docs/):

### Для разработчиков

- **[ARCHITECTURE.md](./docs/developer-guide/ARCHITECTURE.md)** — архитектура Clean Architecture (5 слоев), компоненты, принципы
- **[DEVELOPING.md](./docs/developer-guide/DEVELOPING.md)** — локальная разработка, окружение, команды, структура проекта
- **[TESTING.md](./docs/developer-guide/TESTING.md)** — стратегия тестирования, примеры, best practices
- **[NAVIGATION_MANAGER.md](./docs/developer-guide/NAVIGATION_MANAGER.md)** — управление навигацией в TUI, защита от race conditions

### Для пользователей и планирования

- **[UI_UX_IMPROVEMENTS.md](./docs/roadmap/UI_UX_IMPROVEMENTS.md)** — план улучшения интерфейса (4 фазы)

### Архивные документы

- **[MIGRATION-FROM-OLD-API.md](./docs/archive/MIGRATION-FROM-OLD-API.md)** — миграция с legacy API на Clean Architecture
- **[TUI_CLIENT_SPECIFICATION.md](./docs/archive/TUI_CLIENT_SPECIFICATION.md)** — техническое задание клиента

## 🚀 Быстрый старт

### Установка зависимостей

```bash
# Установка зависимостей проекта
uv sync
```

### Запуск TUI клиента

```bash
# Запуск с параметрами по умолчанию (localhost:8000)
python -m acp_client.tui

# Запуск с кастомными параметрами
python -m acp_client.tui --host 127.0.0.1 --port 8000 --theme dark

# Или через установленный скрипт
acp-client-tui
```

### Запуск CLI обертки

```bash
# Запуск TUI через CLI entrypoint
uv run acp-client --host 127.0.0.1 --port 8000

# Запуск с кастомной директорией истории
uv run acp-client --host 127.0.0.1 --port 8000 --history-dir ./data/client-history
```

## 🏗️ Архитектура

Проект организован по принципам **Clean Architecture** с 5 независимыми слоями:

```
┌─────────────────────────────────┐
│  TUI Layer (Textual UI)         │  ← Пользовательский интерфейс
├─────────────────────────────────┤
│  Presentation Layer (MVVM)      │  ← Observable, ViewModels
├─────────────────────────────────┤
│  Application Layer (Use Cases)  │  ← Бизнес-логика
├─────────────────────────────────┤
│  Infrastructure Layer (DI)      │  ← Реализации, сервисы
├─────────────────────────────────┤
│  Domain Layer (Core)            │  ← Entities, Events
└─────────────────────────────────┘
```

### Структура проекта

```
acp-client/
├── docs/                          # 📚 Документация
│   ├── developer-guide/           # Для разработчиков
│   │   ├── ARCHITECTURE.md        # Clean Architecture (5 слоев)
│   │   ├── DEVELOPING.md          # Локальная разработка
│   │   ├── TESTING.md             # Тестирование
│   │   └── NAVIGATION_MANAGER.md  # Управление навигацией
│   ├── roadmap/                   # Планы развития
│   │   └── UI_UX_IMPROVEMENTS.md  # Улучшение интерфейса
│   └── archive/                   # Архивные документы
│       ├── MIGRATION-FROM-OLD-API.md
│       └── TUI_CLIENT_SPECIFICATION.md
│
├── src/acp_client/
│   ├── domain/                    # 🔵 Domain Layer
│   │   ├── entities.py            # Session, Message entities
│   │   ├── events.py              # Domain events
│   │   ├── repositories.py        # Repository interfaces
│   │   └── services.py            # Service interfaces
│   │
│   ├── application/               # 🟢 Application Layer
│   │   ├── use_cases.py           # Use Cases
│   │   ├── dto.py                 # DTOs for data transfer
│   │   ├── state_machine.py       # State management
│   │   └── session_coordinator.py # Session orchestration
│   │
│   ├── infrastructure/            # 🟡 Infrastructure Layer
│   │   ├── di_container.py        # DI Container
│   │   ├── di_bootstrapper.py     # DI initialization
│   │   ├── repositories.py        # Repository implementations
│   │   ├── transport.py           # WebSocket transport
│   │   ├── events/                # Event Bus
│   │   └── services/              # Service implementations
│   │
│   ├── presentation/              # 🔴 Presentation Layer
│   │   ├── observable.py          # Observable pattern
│   │   ├── base_view_model.py     # Base ViewModel
│   │   ├── chat_view_model.py     # Chat ViewModel
│   │   ├── session_view_model.py  # Session ViewModel
│   │   └── ...                    # Other ViewModels
│   │
│   └── tui/                       # 🟣 TUI Layer (Textual)
│       ├── app.py                 # Main TUI application
│       ├── components/            # UI components
│       │   ├── chat_view.py
│       │   ├── file_viewer.py
│       │   ├── permission_modal.py
│       │   └── ...
│       ├── navigation/            # Navigation management
│       │   ├── manager.py         # NavigationManager
│       │   ├── queue.py           # Operation queue
│       │   ├── tracker.py         # Modal tracking
│       │   └── operations.py      # Operation definitions
│       └── styles/                # TUI styles (TCSS)
│
├── tests/                         # 🧪 Unit & Integration tests
│   ├── test_navigation_*.py       # Navigation tests
│   ├── test_infrastructure_*.py   # Infrastructure tests
│   ├── test_presentation_*.py     # Presentation tests
│   ├── test_domain_*.py           # Domain tests
│   ├── test_application_*.py      # Application tests
│   ├── test_tui_*.py              # TUI tests
│   └── conftest.py                # pytest fixtures
│
├── pyproject.toml                 # Зависимости и метаданные
└── README.md                      # Этот файл
```

## Content Types

Клиент поддерживает полный спектр Content типов согласно ACP спецификации:

- **TextContent** - текстовые сообщения
- **ImageContent** - изображения (base64, PNG, JPEG, GIF, WebP)
- **AudioContent** - аудиоданные (base64, WAV, MP3, MPEG)
- **EmbeddedResourceContent** - встроенные ресурсы
- **ResourceLinkContent** - ссылки на ресурсы

Реализация находится в `src/acp_client/domain/content/` и полностью совместима с серверной реализацией.

Подробнее см. [`doc/architecture/CONTENT_TYPES_ARCHITECTURE.md`](../doc/architecture/CONTENT_TYPES_ARCHITECTURE.md)

## Обработка запросов от агента

Клиент обрабатывает RPC запросы от агента для выполнения операций в локальной среде пользователя.

### File System Handler

Обработка файловых операций:

- **`fs/read_text_file`** — чтение текстовых файлов с поддержкой диапазонов строк
  - Безопасное чтение с валидацией пути
  - Защита от path traversal атак
  - Поддержка start_line и end_line для чтения части файла

- **`fs/write_text_file`** — запись текстовых файлов с контролем создания
  - Валидация пути и контроля создания новых файлов
  - Sandbox режим с base_path
  - Поддержка флагов create и overwrite

**Реализация:**
- [`FileSystemHandler`](src/acp_client/infrastructure/handlers/file_system_handler.py) — обработчик запросов
- [`FileSystemExecutor`](src/acp_client/infrastructure/services/file_system_executor.py) — исполнитель операций
- Асинхронные операции через `aiofiles` для неблокирующего I/O

### Terminal Handler

Управление терминальными процессами:

- **`terminal/create`** — создание терминала и запуск команды
  - Запуск subprocess с контролем окружения
  - Поддержка аргументов и рабочей директории
  - Автоматическая буферизация output

- **`terminal/output`** — получение output терминала
  - Чтение буферизованного output с лимитом размера
  - Поддержка skip_bytes для пагинации

- **`terminal/wait_for_exit`** — ожидание завершения процесса
  - Асинхронное ожидание с таймаутом
  - Возврат exit code при завершении

- **`terminal/kill`** — принудительное завершение процесса
  - Отправка сигнала SIGTERM/SIGKILL
  - Очистка ресурсов процесса

- **`terminal/release`** — освобождение ресурсов терминала
  - Закрытие потоков ввода/вывода
  - Удаление из трекера активных терминалов

**Реализация:**
- [`TerminalHandler`](src/acp_client/infrastructure/handlers/terminal_handler.py) — обработчик запросов
- [`TerminalExecutor`](src/acp_client/infrastructure/services/terminal_executor.py) — исполнитель операций
- Жизненный цикл терминала: CREATED → RUNNING → EXITED → RELEASED

### Безопасность

- **Защита от path traversal** — валидация всех путей файлов
- **Sandbox режим** — ограничение доступа к файлам в пределах base_path
- **Валидация параметров** — проверка всех входящих параметров
- **Логирование операций** — structured logging всех операций

Подробнее см. [`doc/architecture/CLIENT_METHODS_ARCHITECTURE.md`](../doc/architecture/CLIENT_METHODS_ARCHITECTURE.md)

## 🎯 Основные возможности

### TUI Интерфейс

- **Управление сессиями** — создание, загрузка, переключение
- **Chat View** — история промптов и ответов агента
- **File Tree** — навигация по файловой системе
- **File Viewer** — просмотр файлов с подсветкой синтаксиса
- **Permission Modal** — управление разрешениями
- **Plan Panel** — визуализация плана выполнения
- **Tool Panel** — трассировка вызовов инструментов
- **Terminal Output** — просмотр логов терминала
- **NavigationManager** — безопасное управление модальными окнами

### Горячие клавиши

| Комбинация | Действие |
|-----------|----------|
| `Ctrl+Enter` | Отправить промпт |
| `Ctrl+B` | Фокус на sidebar |
| `Ctrl+N` | Новая сессия |
| `Ctrl+Tab` | Следующая вкладка sidebar |
| `Ctrl+Shift+Tab` | Предыдущая вкладка sidebar |
| `Space` | Свернуть/развернуть секцию в sidebar |
| `Enter` | Открыть файл |
| `Ctrl+H` / `F1` | Контекстная справка |
| `?` | Список горячих клавиш |
| `Ctrl+Q` | Выход |

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
uv run pytest

# С отчётом о покрытии
uv run pytest --cov=src

# Конкретный файл
uv run pytest tests/test_navigation_manager.py

# Конкретный тест
uv run pytest tests/test_navigation_manager.py::test_show_screen_success
```

### Проверки качества кода

```bash
# Все проверки (из корня репозитория)
make check

# Или отдельно:
uv run ruff check .        # Linting
uv run pyright .           # Type checking
uv run pytest              # Tests
```

## 🔧 Разработка

### Установка окружения

```bash
# Синхронизировать зависимости
uv sync

# Запустить TUI в режиме разработки
uv run acp_client.tui --log-level DEBUG
```

### Структура кода

Код следует Clean Architecture с принципом **Dependency Rule**: зависимости всегда направлены внутрь, от внешних слоев к внутренним.

**Основной поток данных:**
```
User Input → TUI → ViewModel → Use Case → Domain/Infrastructure
                                              ↓
                          Observable Update ← 
```

### Добавление новой функции

1. **Определить Entity** в Domain слое (`domain/entities.py`)
2. **Создать Use Case** в Application слое (`application/use_cases.py`)
3. **Добавить ViewModel** в Presentation слое (`presentation/`)
4. **Создать UI компонент** в TUI слое (`tui/components/`)
5. **Написать тесты** для каждого уровня

Подробнее см. [DEVELOPING.md](./docs/developer-guide/DEVELOPING.md).

## 📖 Документация

### Для новых разработчиков

1. Начните с [ARCHITECTURE.md](./docs/developer-guide/ARCHITECTURE.md) — общее понимание структуры
2. Изучите [DEVELOPING.md](./docs/developer-guide/DEVELOPING.md) — как локально разрабатывать
3. Примеры в [TESTING.md](./docs/developer-guide/TESTING.md) — как писать тесты

### Для опытных разработчиков

- [NAVIGATION_MANAGER.md](./docs/developer-guide/NAVIGATION_MANAGER.md) — управление навигацией и модальными окнами
- [UI_UX_IMPROVEMENTS.md](./docs/roadmap/UI_UX_IMPROVEMENTS.md) — планы развития интерфейса
- [MIGRATION-FROM-OLD-API.md](./docs/archive/MIGRATION-FROM-OLD-API.md) — как переносить старый код

### API Reference

Смотрите типизированный код в:
- `src/acp_client/domain/` — интерфейсы
- `src/acp_client/application/` — Use Cases и DTOs
- `src/acp_client/infrastructure/` — реализации

## 🐛 Логирование

Логи сохраняются в `~/.acp-client/logs/acp-client.log`.

```bash
# DEBUG логирование
python -m acp_client.tui --log-level DEBUG

# JSON логи для production
python -m acp_client.tui --log-json
```

Для диагностики зависаний tool lifecycle добавлены trace-события (уровень `DEBUG`):
- `tool_lifecycle_notification_received` — клиент получил server->client RPC/notification
- `tool_lifecycle_rpc_received` — распознан конкретный tool RPC (`fs/*`, `terminal/*`)
- `tool_lifecycle_callback_start` / `tool_lifecycle_callback_done` — старт/завершение локального callback
- `tool_lifecycle_response_sending` / `tool_lifecycle_response_sent` — отправка ответа серверу
- `tool_lifecycle_notification_failed` — ошибка в обработке callback (ключевой сигнал места «затыка»)

## 🗂️ Локальная история чата

Клиент сохраняет локальный кэш истории по умолчанию в `~/.acp-client/history`.

Путь можно переопределить через переменную окружения `ACP_CLIENT_HISTORY_DIR`:

```bash
export ACP_CLIENT_HISTORY_DIR=./data/client-history
uv run acp-client --host 127.0.0.1 --port 8000
```

Также путь можно задать через флаг CLI `--history-dir` (`acp-client` и `acp-client-tui`).

Приоритет путей: `--history-dir`/`history_dir` в коде → `ACP_CLIENT_HISTORY_DIR` → `~/.acp-client/history`.

## 📋 Требования

- Python 3.12+
- aiohttp (WebSocket)
- textual (TUI)
- pydantic (data validation)
- structlog (logging)

Полный список см. в [pyproject.toml](./pyproject.toml).

## 🔗 Ссылки

- **[ACP Protocol Specification](../doc/ACP/)** — полная спецификация протокола
- **[acp-server](../acp-server/)** — серверная часть (Python)
- **[AGENTS.md](../AGENTS.md)** — правила разработки в репозитории

## 📝 Лицензия

Проект является частью OpenIdeaLab / CodeLab.

## 💬 Вопросы и поддержка

- Читайте документацию в [`docs/`](./docs/)
- Смотрите примеры в тестах [`tests/`](./tests/)
- Проверьте исходный код в [`src/`](./src/)
