# Архитектура ACP Protocol

## Обзор

ACP (Agent Client Protocol) — протокол взаимодействия между агентами и клиентами для выполнения задач с использованием LLM.

Проект реализован как монорепозиторий с двумя независимыми Python-компонентами:
- **acp-server** — серверная реализация протокола ACP с WebSocket транспортом
- **acp-client** — клиентская реализация для подключения к ACP серверам

## Компоненты

### acp-server

Серверная реализация протокола ACP с полной поддержкой сессий, аутентификации и управления состоянием.

#### Структура модулей

```
acp-server/src/acp_server/
├── cli.py                   # CLI entry point
├── http_server.py           # WebSocket транспорт
├── logging.py               # Структурированное логирование
├── messages.py              # Pydantic модели сообщений
├── server.py                # TCP транспорт (legacy)
├── protocol/                # Ядро протокола
│   ├── __init__.py          # Экспорт публичных классов
│   ├── core.py              # ACPProtocol класс
│   ├── state.py             # Dataclasses состояния
│   └── handlers/            # Обработчики методов
│       ├── auth.py          # authenticate, initialize
│       ├── session.py       # session/new, load, list
│       ├── prompt.py        # session/prompt, cancel
│       ├── permissions.py   # session/request_permission
│       ├── config.py        # session/set_config_option
│       └── legacy.py        # ping, echo, shutdown
└── storage/                 # Хранилище сессий
    ├── base.py              # SessionStorage(ABC)
    ├── memory.py            # InMemoryStorage
    └── json_file.py         # JsonFileStorage
```

#### Слои архитектуры

1. **Transport Layer** (`http_server.py`)
   - WebSocket endpoint `/acp/ws`
   - Обработка JSON-RPC сообщений
   - Update-поток для `session/update` событий
   - Асинхронная обработка запросов с deferred responses

2. **Protocol Layer** (`protocol/`)
   - Диспетчеризация методов через `ACPProtocol.handle()`
   - Валидация запросов согласно ACP спецификации
   - Управление состоянием сессий через SessionState
   - Модульная архитектура handlers для разных категорий методов

3. **Storage Layer** (`storage/`)
   - Абстракция `SessionStorage(ABC)` для plug-and-play архитектуры
   - `InMemoryStorage` — для development и тестирования
   - `JsonFileStorage` — для production с persistence на диск
   - Расширяемая архитектура для добавления новых backends

4. **Logging Layer** (`logging.py`)
   - Структурированное логирование с structlog
   - JSON и консольный форматы с уровнями DEBUG, INFO, WARNING, ERROR
   - Интеграция с CLI флагом `--log-level`

### acp-client

Клиентская реализация для подключения к ACP серверам и выполнения операций.

#### Структура модулей

```
acp-client/src/acp_client/
├── cli.py                   # CLI команды и entry point
├── client.py                # ACPClient для запросов к серверу (654 строк)
├── logging.py               # Структурированное логирование
├── messages.py              # Pydantic модели сообщений
├── __init__.py              # Экспорт публичного API
├── helpers/                 # 🔧 Вспомогательные функции
│   ├── __init__.py          # Экспорт helper функций
│   ├── auth.py              # pick_auth_method_id() — выбор метода аутентификации
│   └── session.py           # Функции парсинга session/update событий
├── handlers/                # 🎯 Обработчики RPC запросов от сервера
│   ├── __init__.py          # Экспорт обработчиков
│   ├── permissions.py       # build_permission_result() — результат разрешений
│   ├── filesystem.py        # handle_server_fs_request() — файловая система
│   └── terminal.py          # handle_server_terminal_request() — терминал
└── transport/               # 🌐 Транспортный слой
    ├── __init__.py          # Экспорт транспортных компонентов
    └── websocket.py         # WebSocket сессия (ACPClientWSSession) и функции
```

#### Слои архитектуры

1. **Transport Layer** (`transport/websocket.py`)
   - `ACPClientWSSession` — класс для управления persistent WebSocket-сессиями
   - `await_ws_response()` — ожидание финального ответа с обработкой промежуточных событий
   - `perform_ws_initialize()` — handshake инициализация
   - `perform_ws_authenticate()` — аутентификация в WS-сессии

2. **Handlers Layer** (`handlers/`)
   - `build_permission_result()` — обработка запросов разрешений
   - `handle_server_fs_request()` — обработка FS операций от сервера
   - `handle_server_terminal_request()` — обработка терминала от сервера

3. **Helpers Layer** (`helpers/`)
   - `pick_auth_method_id()` — выбор метода аутентификации из доступных
   - `extract_tool_call_updates()`, `extract_plan_updates()` и другие — парсинг session updates

4. **Client Layer** (`client.py`)
   - `ACPClient` — основной асинхронный клиент для запросов к серверу
   - Поддержка методов: `authenticate`, `initialize`, `session/new`, `session/load`, `session/list`, `session/prompt`
   - Обработка `session/request_permission` и других RPC запросов от сервера

#### Функциональность

- **ACPClient** — асинхронный клиент для WebSocket соединений с серверами ACP
- Поддержка методов: `authenticate`, `initialize`, `session/new`, `session/load`, `session/list`, `session/prompt`
- Обработка `session/request_permission` и других RPC запросов от сервера
- CLI для быстрого взаимодействия с серверами
- Структурированное логирование с поддержкой JSON формата
- Модульная архитектура для легкого добавления новых обработчиков

## Поток данных

```
Client → WebSocket → ACPHttpServer → ACPProtocol → SessionStorage
                            ↓
                     Handler (auth/session/prompt/etc.)
                            ↓
                  Response/Updates → Client
```

### Agent→Client RPC (обратные запросы)

Сервер отправляет запросы клиенту для выполнения операций:
- `fs/readTextFile`, `fs/writeTextFile` — файловые операции
- `terminal/execute` — выполнение команд в терминале
- `session/request_permission` — запрос разрешений пользователя

Клиент обрабатывает операции и возвращает результаты через `session/request_permission_response`.

## Ключевые концепции

### Sessions (Сессии)

Сессии хранят контекст работы:
- История сообщений и tool calls
- Конфигурационные опции
- Активные tool calls и их статусы
- Состояние выполнения prompt-turn

Сессии могут быть созданы, загружены, перечислены и сохранены через SessionStorage.

### SessionState

Dataclass с полной информацией о сессии:
- `id`, `created_at`, `cwd` (current working directory)
- `model`, `system_prompt`, `tools`
- `config_options` (конфигурация)
- `messages` (история сообщений)
- `tool_calls` (активные tool calls)
- `stopped` (флаг завершения)

### Storage Backends

- **InMemoryStorage**: данные хранятся в памяти, идеально для development и тестирования, все данные теряются при перезагрузке
- **JsonFileStorage**: persistence в JSON файлах на диск, поддерживает backup и recovery, подходит для production

Backends могут быть переключены через CLI флаг `--storage` без изменения остального кода.

### Handlers (Обработчики методов)

Каждый handler отвечает за группу методов протокола:
- **auth.py** — `authenticate`, `initialize`
- **session.py** — `session/new`, `session/load`, `session/list`
- **prompt.py** — `session/prompt`, `session/cancel`
- **permissions.py** — `session/request_permission`, `session/request_permission_response`
- **config.py** — `session/set_config_option`
- **legacy.py** — `ping`, `echo`, `shutdown` (для обратной совместимости)

## Конфигурация

### Development режим

```bash
# Запуск с DEBUG логированием в консоль
acp-server --host 127.0.0.1 --port 8080 --log-level DEBUG

# С in-memory storage (по умолчанию)
uv run --directory acp-server acp-server --host 127.0.0.1 --port 8080
```

### Production режим

```bash
# С обязательной аутентификацией и persistence
acp-server \
  --host 0.0.0.0 \
  --port 8080 \
  --require-auth \
  --auth-api-key $ACP_SERVER_API_KEY \
  --log-json \
  --log-level INFO \
  --storage json:/var/lib/acp/sessions
```

### CLI флаги

- `--host` — IP адрес для слушания (default: 127.0.0.1)
- `--port` — порт для слушания (default: 8080)
- `--log-level` — уровень логирования: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `--log-json` — JSON формат логирования вместо консоли
- `--require-auth` — требовать аутентификацию для всех сессий
- `--auth-api-key` — API ключ для аутентификации (local backend)
- `--storage` — URI хранилища (memory:// или json://path/to/sessions)

## Тестирование

### Полная проверка (оба проекта)

```bash
# Из корня репозитория
make check
```

Запускает для обоих подпроектов:
- `ruff check .` — проверка стиля кода и линтинг
- `ty check` — проверка типов с PyRight
- `python -m pytest` — unit и интеграционные тесты

### Локальные проверки

Для server:
```bash
uv run --directory acp-server ruff check .
uv run --directory acp-server ty check
uv run --directory acp-server python -m pytest
```

Для client:
```bash
uv run --directory acp-client ruff check .
uv run --directory acp-client ty check
uv run --directory acp-client python -m pytest
```

### Тестовое покрытие

- **test_protocol.py** — основные методы протокола
- **test_http_server.py** — WebSocket транспорт
- **test_storage_*.py** — различные backends
- **test_conformance.py** — соответствие ACP спецификации
- **test_integration_with_server.py** — интеграционные тесты client-server

## Расширение

### Добавление нового storage backend

1. Создать класс наследующий `SessionStorage(ABC)` в `storage/`
2. Реализовать все абстрактные методы:
   - `create_session()` — создание новой сессии
   - `load_session()` — загрузка существующей
   - `list_sessions()` — перечисление с фильтром и pagination
   - `update_session()` — сохранение изменений
   - `delete_session()` — удаление сессии
3. Добавить класс в `storage/__init__.py` для экспорта
4. Обновить `cli.py` для парсинга нового URI формата в флаге `--storage`

Пример:

```python
from storage.base import SessionStorage

class RedisStorage(SessionStorage):
    """Storage backend на Redis для распределенных систем."""
    
    async def create_session(self, state: SessionState) -> SessionState:
        # Реализация сохранения в Redis
        pass
    
    # Остальные методы...
```

### Добавление нового метода протокола

1. Определить модель сообщения в `messages.py`
2. Добавить handler в соответствующий файл `protocol/handlers/`:
   - Для аутентификации/инициализации — `auth.py`
   - Для сессий — `session.py`
   - Для prompt-турнов — `prompt.py`
   - И т.д.
3. Зарегистрировать метод в `ACPProtocol.handle()` в `core.py`
4. Добавить unit тесты в `tests/test_protocol.py`
5. Добавить conformance тесты если требует спецификация

Пример:

```python
# handlers/new_handler.py
async def handle_new_method(protocol: ACPProtocol, request: NewMethodRequest) -> NewMethodResponse:
    """Обработка нового метода."""
    # Логика обработки
    return NewMethodResponse(...)

# protocol/core.py
elif method == "namespace/new_method":
    return await handle_new_method(self, request)
```

## Жизненный цикл запроса

```
1. Client отправляет JSON-RPC запрос на WebSocket
2. ACPHttpServer парсит JSON и создает Request
3. ACPProtocol.handle() диспетчеризует на handler
4. Handler обрабатывает запрос с использованием SessionStorage
5. Handler возвращает Response или ошибку
6. ACPHttpServer отправляет JSON-RPC результат клиенту
7. Если требуется длительное выполнение, используется deferred response
8. Session updates отправляются через отдельный update-поток
```

## Безопасность

- Аутентификация через `authenticate` с API ключами
- Permission-гейт для операций, требующих разрешения (`session/request_permission`)
- Валидация всех входных данных согласно Pydantic моделям
- Логирование всех операций для аудита
- Изоляция сессий друг от друга через SessionStorage

## Производительность

- Асинхронная обработка запросов через asyncio
- Потоковые session/update события для real-time обновлений
- Plug-and-play хранилища для оптимизации по сценариям использования
- Lazy loading сессий (загрузка только при необходимости)

## Конкурентность

- WebSocket многопользовательский, поддерживает множество одновременных соединений
- Состояние сессий synchronous (не асинхронное), но может быть расширено
- Деferred responses позволяют длительным операциям не блокировать соединение
- Cancel-flow детерминирован для race условий с permission

## Документы проекта

- **[AGENTS.md](AGENTS.md)** — инструкции для агентных ассистентов
- **[README.md](README.md)** — обзор и быстрый старт
- **[CHANGELOG.md](CHANGELOG.md)** — история изменений
- **[doc/ACP_IMPLEMENTATION_STATUS.md](doc/ACP_IMPLEMENTATION_STATUS.md)** — матрица соответствия ACP
- **[doc/ACP/](doc/ACP/)** — спецификация и рабочие материалы ACP
