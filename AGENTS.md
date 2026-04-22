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
- Документацию вести на русском языке.
- Весь код должен иметь осмысленные комментарии.
- **Каждое изменение в коде должно быть покрыто тестом** (unit тесты, интеграционные тесты, как уместно).
- **Никогда не менять документацию в `doc/Agent Client Protocol/`** — это официальный протокол.
- **Никогда не нарушать протокол, описанный в `doc/Agent Client Protocol/`** — все изменения в коде должны соответствовать спецификации.

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
    - `core.py` — основной класс ACPProtocol (диспетчеризация методов)
    - `state.py` — dataclasses состояния (SessionState, ToolCallState, и т.д.)
    - `session_factory.py` — фабрика создания сессий
    - `handlers/` — обработчики методов протокола:
      - `auth.py` — методы аутентификации (authenticate, initialize)
      - `session.py` — управление сессиями (session/new, load, list)
      - `prompt.py` — обработка prompt-turn (session/prompt, cancel)
      - `prompt_orchestrator.py` — главный оркестратор prompt-turn
      - `permissions.py` — управление разрешениями (session/request_permission)
      - `permission_manager.py` — менеджер политик разрешений
      - `global_policy_manager.py` — глобальные политики разрешений
      - `config.py` — конфигурация сессий (session/set_config_option, session/set_mode)
      - `client_rpc_handler.py` — обработка RPC вызовов к клиенту
      - `tool_call_handler.py` — обработка tool calls
      - `plan_builder.py` — построение планов агента
      - `state_manager.py` — управление состоянием
      - `turn_lifecycle_manager.py` — управление жизненным циклом turn
      - `legacy.py` — ping, echo, shutdown
    - `content/` — типы контента (ACP Content Types):
      - `base.py` — базовые классы
      - `text.py`, `image.py`, `audio.py` — типы контента
      - `embedded.py`, `resource_link.py` — ресурсы
      - `extractor.py`, `validator.py`, `formatter.py` — обработка контента
    - `prompt_handlers/` — обработчики директив промптов:
      - `directive_resolver.py` — разрешение директив
      - `validator.py` — валидация промптов
  - `acp-server/src/acp_server/storage/` — хранилище сессий:
    - `base.py` — SessionStorage(ABC) интерфейс
    - `memory.py` — InMemoryStorage (development)
    - `json_file.py` — JsonFileStorage (production с persistence)
    - `global_policy_storage.py` — хранилище глобальных политик
  - `acp-server/src/acp_server/client_rpc/` — RPC сервис для вызовов Agent → Client:
    - `service.py` — ClientRPCService
    - `models.py` — модели данных
    - `exceptions.py` — исключения
  - `acp-server/src/acp_server/agent/` — LLM агенты:
    - `orchestrator.py` — AgentOrchestrator (управление LLM-агентом)
    - `naive.py` — NaiveAgent (базовая реализация)
    - `base.py` — базовые классы агентов
    - `state.py` — состояние агента
  - `acp-server/src/acp_server/tools/` — инструменты агента:
    - `registry.py` — ToolRegistry (регистрация и управление инструментами)
    - `base.py` — базовые классы инструментов
    - `definitions/` — определения инструментов (filesystem.py, terminal.py)
    - `executors/` — исполнители инструментов (filesystem_executor.py, terminal_executor.py)
    - `integrations/` — интеграции (client_rpc_bridge.py, permission_checker.py)
  - `acp-server/src/acp_server/llm/` — LLM провайдеры
  - `acp-server/src/acp_server/http_server.py` — WebSocket транспорт
  - `acp-server/src/acp_server/messages.py` — JSON-RPC сообщения
- Клиент (Clean Architecture, 5 слоев):
  - `acp-client/src/acp_client/domain/` — Domain Layer:
    - `entities.py` — сущности (Session, Message)
    - `repositories.py` — интерфейсы репозиториев
  - `acp-client/src/acp_client/application/` — Application Layer:
    - Use Cases, DTOs, State Machine
  - `acp-client/src/acp_client/infrastructure/` — Infrastructure Layer:
    - DI Container, Transport, Event Bus, Handlers (fs/*, terminal/*)
  - `acp-client/src/acp_client/presentation/` — Presentation Layer:
    - ViewModels (MVVM), Observable
  - `acp-client/src/acp_client/tui/` — TUI Layer:
    - Textual UI компоненты
  - `acp-client/src/acp_client/cli.py` — CLI entrypoint
  - `acp-client/src/acp_client/messages.py` — JSON-RPC сообщения

## Git-правила

- Не коммитить артефакты окружения и кэши (`.venv`, `__pycache__`, `.pytest_cache`, `.ruff_cache`).
- Один логический блок изменений = один коммит.
- Сообщение коммита: коротко и по сути (что и зачем).

## Документация

- При изменении поведения обновлять соответствующие README (`README.md`, `acp-server/README.md`, `acp-client/README.md`).
- Для сверки с протоколом использовать материалы в `doc/Agent Client Protocol/`.
- **Все диаграммы, схемы описывать с помощью Mermaid**.
- **При каждом изменении архитектуры необходимо обновлять документацию и диаграммы/графики/схемы** — архитектурная документация должна отражать текущее состояние системы.
