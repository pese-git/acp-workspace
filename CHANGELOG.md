# Changelog

Все значительные изменения в этом проекте будут документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
