# ACP Client

Клиентская часть Agent Client Protocol (ACP) с WebSocket транспортом.

## Архитектура

### Структура модулей

Клиент организован в логичные компоненты для лучшей модульности и тестируемости:

```
acp-client/src/acp_client/
├── client.py                 # Основной клиент ACPClient (654 строк)
├── cli.py                    # CLI интерфейс
├── logging.py                # Структурированное логирование
├── messages.py               # Pydantic модели сообщений
├── tui/                       # Textual TUI подсистема
│
├── transport/                # 🌐 Транспортный слой
│   └── websocket.py          # WebSocket сессия (ACPClientWSSession)
│
├── handlers/                 # 🎯 Обработчики RPC запросов
│   ├── permissions.py        # Обработка разрешений
│   ├── filesystem.py         # Обработка файловой системы
│   └── terminal.py           # Обработка терминала
│
└── helpers/                  # 🔧 Вспомогательные функции
    ├── auth.py              # Выбор метода аутентификации
    └── session.py           # Парсинг session/update событий
```

### Компоненты

- **`client.py`** — основной класс `ACPClient` для взаимодействия с ACP серверами
- **`transport/websocket.py`** — транспортный слой для WebSocket соединений
  - `ACPClientWSSession` — управление persistent WebSocket-сессиями
  - `await_ws_response()` — ожидание финального ответа
  - `perform_ws_initialize()`, `perform_ws_authenticate()` — handshake функции
- **`handlers/`** — модули для обработки RPC запросов от сервера
  - Разделение по типам: permissions, filesystem, terminal
- **`helpers/`** — вспомогательные функции для аутентификации и парсинга

## Установка

```bash
uv sync
```

## Использование

```bash
uv run acp-client --host 127.0.0.1 --port 8080 --method ping
uv run acp-client --host 127.0.0.1 --port 8080 --method echo --params '{"message":"hello"}'
uv run acp-client --host 127.0.0.1 --port 8080 --method session/load --params '{"sessionId":"sess_1","cwd":"/tmp","mcpServers":[]}' --show-updates
uv run acp-client --tui --host 127.0.0.1 --port 8080
uv run acp-client-tui --host 127.0.0.1 --port 8080
```

Горячие клавиши TUI: `Ctrl+B` фокус сессий (дальше `Up/Down + Enter`), `Ctrl+Enter` отправить prompt, `Ctrl+R` повторить последнюю неуспешную операцию из очереди retry, `Ctrl+Up/Down` история prompt в активной сессии, `Ctrl+N` новая сессия, `Ctrl+J/K` переключение сессий, `Ctrl+C` cancel, `Ctrl+Q` выход. При выборе сессии клиент загружает replay-обновления и дорисовывает текстовую историю.

В правой панели TUI отображаются события `tool_call` и `tool_call_update` с текущими статусами вызовов инструментов.

При получении `session/request_permission` клиент показывает модальное окно с вариантами решения и отправляет выбранную опцию обратно агенту.
В модальном окне разрешений работают быстрые клавиши: `A` (allow once/always), `R` (reject once/always), `Esc` (cancel).
TUI сохраняет последнюю активную сессию и черновик prompt в локальный файл состояния и восстанавливает их при следующем запуске.
Если соединение с сервером недоступно, отправка prompt мягко блокируется: черновик остается в поле ввода, а footer показывает статус `Offline` и подсказку по retry.
Строки Header/Footer синхронизируются через единые состояния подключения: `Connected`, `Reconnecting`, `Degraded`, `Offline`.
Политика ошибок единая: при доступном соединении UI переходит в `Degraded`, при потере соединения — в `Offline`.
При неуспешном `cancel` операция также попадает в очередь retry и может быть повторена через `Ctrl+R`.

## Полезные helper-методы ACPClient

- `initialize(...)` — выполняет handshake и возвращает типизированный результат согласования.
- `authenticate(...)` — типизированный helper для ACP `authenticate`.
- `prompt(...)` — типизированный helper для `session/prompt` с optional `_meta.promptDirectives`.
- `open_ws_session().prompt(...)` — typed helper для `session/prompt` в persistent WS-сессии.
- `open_ws_session().authenticate(...)` — typed helper для `authenticate` в persistent WS-сессии.
- `create_session_parsed(...)` — типизированный helper для ответа `session/new`.
- `load_session_setup_parsed(...)` — типизированный helper для ответа `session/load` и replay updates.
- `load_session_parsed(...)` — возвращает типизированные `session/update` события.
- `load_session_structured_updates(...)` — возвращает только известные типизированные payload `session/update`.
- `set_config_option_with_updates(...)` — меняет config option и возвращает типизированные update-события.
- `load_session_tool_updates(...)` — возвращает только события tool call.
- `load_session_plan_updates(...)` — возвращает только события `plan`.
- `list_sessions(...)` и `list_all_sessions(...)` — работа с `session/list` и cursor-пагинацией.
- `list_sessions_parsed(...)` и `list_all_sessions_parsed(...)` — типизированный разбор ответа `session/list`.

## Поведение WebSocket

- Перед вызовами `session/*` клиент автоматически выполняет `initialize` в рамках WS-соединения.
- Если в `initialize` возвращены `authMethods`, клиент автоматически выполняет `authenticate` перед `session/*` (можно отключить через `auto_authenticate=False`).
- Можно указать `preferred_auth_method_id`, чтобы выбрать конкретный advertised auth method вместо первого в списке.
- Для API key auth можно передать `auth_api_key` в `ACPClient(...)`; тогда ключ отправится в `authenticate` как `params.apiKey`.
- В auto-initialize отправляются baseline `clientCapabilities` (`fs.readTextFile=false`, `fs.writeTextFile=false`, `terminal=false`).
- Для нескольких запросов в одном WS-канале используйте `open_ws_session()`; `initialize` выполняется один раз на соединение.

Профиль транспорта клиента: только WebSocket.

## Логирование

Клиент поддерживает структурированное логирование с настраиваемым уровнем и форматом.

### Уровни логирования

```bash
# DEBUG - подробная информация для отладки
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level DEBUG

# INFO - основные события (default)
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level INFO

# WARNING - предупреждения
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level WARNING

# ERROR - только ошибки
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-level ERROR
```

### JSON формат

Для production окружения можно использовать JSON формат:

```bash
uv run acp-client --host 127.0.0.1 --port 8080 --method ping --log-json
```

Пример вывода:
```json
{"event": "client_started", "host": "127.0.0.1", "port": 8080, "method": "ping", "timestamp": "2026-04-07T20:00:00.000000Z", "level": "info"}
{"event": "ws_request_sent", "method": "ping", "timestamp": "2026-04-07T20:00:00.100000Z", "level": "debug"}
```

## Проверки

```bash
uv run ruff check .
uv run ty check
uv run pytest
```
