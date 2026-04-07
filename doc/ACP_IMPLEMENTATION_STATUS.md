# Статус реализации ACP

Этот документ фиксирует текущее состояние соответствия ACP в репозитории.

## Матрица соответствия

| Область | Статус | Примечание |
| --- | --- | --- |
| `authenticate` | Done | Метод реализован, `auth_required` для `session/new`/`session/load` поддержан при включенном `require_auth`; добавлен local API key backend (`params.apiKey`) через `--auth-api-key`/`ACP_SERVER_API_KEY`, а также client helpers и auto-auth на WS при наличии `authMethods`. |
| `initialize` | Done | Версия и capability negotiation реализованы; runtime-ветки запускаются только при согласованных client capabilities. |
| `session/new` | Done | Поддерживается создание сессии, `configOptions` и legacy `modes`. |
| `session/load` | Done | Поддерживается replay истории и ключевых `session/update` событий. |
| `session/list` | Done | Реализованы фильтр по `cwd`, cursor pagination и `nextCursor`. |
| `session/prompt` | Partial | Основной WS-поток работает: prompt/update, permission-gate, fs/terminal client-rpc, deferred/cancel, replay. Structured `_meta.promptDirectives` используется как основной путь управления, slash-команды сохранены как compatibility-слой; stopReason `max_tokens`, `max_turn_requests`, `refusal` поддержаны. |
| `session/cancel` | Done | Cancel-flow детерминирован для race с `session/request_permission`, включая late permission responses. |
| `session/set_config_option` | Done | Реализовано с полным возвратом состояния `configOptions`. |
| `session/request_permission` | Done | Server/client оркестрация стабилизирована: race с cancel закрыт, persisted policy (`allow_always`/`reject_always`) scoped по ACP tool kind (`read/edit/delete/move/search/execute/think/fetch/switch_mode/other`), decision-flow валидирует `optionId` по объявленным options и применяет решения детерминированно. |
| `session/update: tool_call*` | Done | Создание/обновление/replay поддержаны. |
| `session/update: plan` | Done | Реализовано и типизировано: план публикуется по structured directives и реплеится через `session/load`; поддержан structured override `planEntries`. |
| `available_commands_update` | Done | Snapshot команд отправляется на prompt/load. |
| HTTP transport | Removed | Проект переведен в WS-only режим, HTTP endpoint удален. |
| WebSocket transport | Done | Поддержан update-поток, deferred response и agent->client RPC (permission/fs/terminal). |

## Рефакторинг (2026-04)

### Завершено

- ✅ **Структурированное логирование** — добавлена интеграция structlog с JSON и консольными форматами
  - Уровни логирования: DEBUG, INFO, WARNING, ERROR
  - CLI флаг `--log-level` для конфигурации
  - CLI флаг `--log-json` для JSON формата в production

- ✅ **Модуляризация protocol layer** — разбит монолитный protocol.py на модули handlers
  - `auth.py` — обработка authenticate, initialize
  - `session.py` — session/new, load, list
  - `prompt.py` — session/prompt, cancel
  - `permissions.py` — session/request_permission
  - `config.py` — session/set_config_option
  - `legacy.py` — ping, echo, shutdown

- ✅ **Storage abstraction** — создан plug-and-play storage layer
  - `SessionStorage(ABC)` — абстрактный интерфейс
  - `InMemoryStorage` — для development, данные в памяти
  - `JsonFileStorage` — для production с persistence
  - CLI флаг `--storage` для выбора backend (memory://, json://path)

- ✅ **Документация** — обновлены и созданы документы
  - Создан ARCHITECTURE.md с полным описанием архитектуры
  - Обновлен README.md со ссылкой на ARCHITECTURE.md
  - Обновлен AGENTS.md с актуальной структурой модулей
  - Создан CHANGELOG.md с историей изменений

### Результаты

- Все 118 тестов проходят (pytest)
- ruff check: 0 ошибок
- ty check: 0 ошибок типов
- Архитектура стала более модульной и расширяемой
- Упрощено добавление новых features и storage backends

## Приоритетный backlog

1. Финализировать production execution backend для `session/prompt` (убрать оставшийся in-memory executor stub и подключить реальное выполнение инструментов).
2. Продолжить расширение conformance-набора на дополнительные edge-кейсы schema/wire (terminal/fs/permission), включая редкие negative payload combinations.
3. Добавить метрики и мониторинг производительности (latency, throughput, error rates).
