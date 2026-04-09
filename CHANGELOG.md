# Changelog

Все значительные изменения в этом проекте будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Phase 4.8: Complete MVVM Integration)

- ✅ **Завершение MVVM интеграции для всех TUI компонентов** (Phase 4.8)
   - Созданы 6 новых ViewModels: PlanViewModel, TerminalViewModel, FileSystemViewModel, FileViewerViewModel, PermissionViewModel, TerminalLogViewModel
   - Обновлены 6 TUI компонентов: PlanPanel, TerminalOutputPanel, FileTree, FileViewerModal, PermissionModal, TerminalLogModal
   - Все 12 TUI компонентов теперь используют MVVM паттерн
   - Добавлено 82 новых MVVM теста (все пройдены):
     - test_tui_plan_panel_mvvm.py - 14 тестов
     - test_tui_terminal_output_mvvm.py - 19 тестов
     - test_tui_file_tree_mvvm.py - 13 тестов
     - test_tui_file_viewer_mvvm.py - 13 тестов
     - test_tui_permission_modal_mvvm.py - 10 тестов
     - test_tui_terminal_log_modal_mvvm.py - 13 тестов
   - Количество ViewModels увеличено с 3 до 9
   - Качество кода: все проверки пройдены (ruff check ✅)
   - Статистика тестирования: 465 тестов пройдены из 488 (95.3%)
   - Создан отчет о завершении Phase 4.8: `doc/PHASE_4_PART8_COMPLETION_REPORT.md`

### Added (Phase 4.6: DIContainer Integration)

- ✅ **ViewModelFactory для DIContainer** (Phase 4.6)
  - Централизованная регистрация всех ViewModels в DIContainer
  - Singleton scope для UIViewModel, SessionViewModel, ChatViewModel
  - Поддержка опциональных EventBus и Logger
  - 17 новых тестов (100% покрытие)

- ✅ **DIContainer интеграция в ACPClientApp** (Phase 4.6)
  - Инициализация DIContainer в `__init__()`
  - Инъекция ViewModels в компоненты через `compose()`
  - Опциональные параметры ViewModel для backward compatibility
  - Fallback режим для компонентов без ViewModel

- ✅ **MVVM рефакторинг 6 TUI компонентов** (Phase 4.5)
  - HeaderBar: подписка на UIViewModel (connection_status, is_loading)
  - Sidebar: подписка на SessionViewModel (sessions, selected_session_id)
  - ChatView: подписка на ChatViewModel (messages, tool_calls, streaming)
  - PromptInput: подписка на ChatViewModel (is_streaming)
  - FooterBar: подписка на UIViewModel (error/info/warning messages)
  - ToolPanel: подписка на ChatViewModel (tool_calls)
  - 58 новых тестов для Phase 4.5 (все пройдены)

### Added (Previous)

- ✅ **Структурированное логирование** с использованием structlog
  - JSON и консольные форматы
  - Уровни логирования: DEBUG, INFO, WARNING, ERROR
  - CLI флаги: `--log-level`, `--log-json`
  - Интеграция с асинхронными операциями

- ✅ **Модульная архитектура Protocol Layer**
  - Разбиение монолитного protocol.py на модули handlers
  - `handlers/auth.py` — методы аутентификации (authenticate, initialize)
  - `handlers/session.py` — управление сессиями (session/new, load, list)
  - `handlers/prompt.py` — обработка prompt-turn (session/prompt, cancel)
  - `handlers/permissions.py` — управление разрешениями (session/request_permission)
  - `handlers/config.py` — конфигурация сессий (session/set_config_option)
  - `handlers/legacy.py` — legacy методы (ping, echo, shutdown)
  - Централизованная диспетчеризация в `protocol/core.py`

- ✅ **Storage Abstraction Layer**
  - Абстрактный интерфейс `SessionStorage(ABC)`
  - `InMemoryStorage` — для development и тестирования
    - Быстрое выполнение
    - Все данные в памяти
    - Идеально для CI/CD и локальной разработки
  - `JsonFileStorage` — для production с persistence
    - Сохранение на диск в JSON формате
    - Поддержка backup и recovery
    - Масштабируемое решение
  - CLI флаг `--storage` для выбора backend
    - `memory://` — InMemoryStorage (по умолчанию)
    - `json://path/to/sessions` — JsonFileStorage

- ✅ **Документация и материалы**
  - `ARCHITECTURE.md` — полное описание архитектуры проекта
    - Обзор компонентов
    - Слои архитектуры (Transport, Protocol, Storage, Logging)
    - Поток данных
    - Ключевые концепции (Sessions, SessionState, Handlers, Backends)
    - Конфигурация для development и production
    - Инструкции по расширению (новые storage backends, новые методы)
    - Жизненный цикл запроса
  - Обновлен README.md со ссылкой на ARCHITECTURE.md
  - Обновлен AGENTS.md с актуальной структурой модулей
  - Обновлен doc/ACP_IMPLEMENTATION_STATUS.md с информацией о рефакторинге
  - Создан CHANGELOG.md (этот файл)

### Changed

- **Организация кода** — переход от монолитного protocol.py к модульной архитектуре
  - Улучшена читаемость и maintainability
  - Упрощена навигация по коду
  - Облегчено добавление новых features

- **Storage слой** — переход от встроенного хранилища к plug-and-play архитектуре
  - Возможность подключения различных backends без изменения остального кода
  - Облегчено тестирование
  - Упрощена масштабируемость

### Fixed

- Все 118 тестов проходят успешно
  - 42 теста для protocol layer
  - 25 тестов для storage layer
  - 30 тестов для HTTP server
  - 21 интеграционный тест

### Development

- **Tooling**
  - ruff для линтинга и форматирования кода
  - PyRight для проверки типов (ty check)
  - pytest для unit и интеграционных тестов
  - Makefile для удобного запуска проверок

- **Тестовое покрытие**
  - `test_protocol.py` — основные методы протокола
  - `test_http_server.py` — WebSocket транспорт
  - `test_storage_base.py` — базовый интерфейс
  - `test_storage_memory.py` — InMemoryStorage
  - `test_storage_json_file.py` — JsonFileStorage
  - `test_conformance.py` — соответствие ACP спецификации
  - `test_integration_with_server.py` — интеграционные тесты client-server

## [0.1.0] - 2026-03

### Added

- Начальная реализация ACP протокола
- WebSocket транспорт
- JSON-RPC обработка сообщений
- Основные методы протокола (authenticate, initialize, session/new, session/load, session/list, session/prompt)
- Система сессий и управления состоянием
- Система разрешений (session/request_permission)
- Legacy методы (ping, echo, shutdown)
- Клиентская реализация (ACPClient)
- CLI для сервера и клиента
- Базовое тестирование

## Примечания по версионированию

Номер версии используется в формате MAJOR.MINOR.PATCH:

- **MAJOR** — несовместимые изменения в публичном API
- **MINOR** — новые функции, совместимые с предыдущими версиями
- **PATCH** — исправления ошибок и улучшения

Все изменения в [Unreleased] разделе будут включены в следующий релиз.

## Как вносить вклад

1. Описывайте свои изменения в CHANGELOG.md в разделе [Unreleased]
2. Используйте подрубрики: Added, Changed, Deprecated, Removed, Fixed, Security
3. Один логический блок изменений = один коммит
4. Запускайте `make check` перед commit
