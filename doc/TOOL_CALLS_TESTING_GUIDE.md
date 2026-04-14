# Tool Calls Testing Guide

## Обзор

Этот документ описывает как протестировать Tool Calls интеграцию в ACP сервере.

## Автоматическое тестирование

### Unit тесты

Запустить все тесты Tool Calls:
```bash
cd acp-server
uv run python -m pytest tests/test_fs_executors.py -v
uv run python -m pytest tests/test_terminal_executors.py -v
uv run python -m pytest tests/test_tool_definitions.py -v
uv run python -m pytest tests/test_tool_integration.py -v
uv run python -m pytest tests/test_permission_flow.py -v
```

### Интеграционные тесты

Запустить полный набор тестов:
```bash
cd acp-server
uv run python -m pytest tests/test_prompt_orchestrator.py -v
```

## Ручное тестирование

### Предварительные требования

1. **LLM Provider с поддержкой tool calls**
   - OpenAI GPT-4 или GPT-3.5-turbo
   - Anthropic Claude 3 (Opus, Sonnet, Haiku)
   - Другие модели с function calling

2. **Конфигурация сервера**
   - Файл `.env` с API ключом LLM провайдера
   - Настроенный `config.yaml` (опционально)

3. **Запущенный ACP клиент**
   - TUI клиент из `acp-client/`
   - Или любой другой ACP-совместимый клиент

### Шаг 1: Запуск сервера

```bash
cd acp-server
uv run python -m acp_server.cli --host 127.0.0.1 --port 8080
```

### Шаг 2: Подключение клиента

```bash
cd acp-client
uv run python -m acp_client.tui --host 127.0.0.1 --port 8080
```

### Шаг 3: Создание сессии

В TUI клиенте:
1. Нажать `Ctrl+N` для создания новой сессии
2. Выбрать режим `code` или `ask`

### Шаг 4: Тестирование File System tools

#### Тест 1: Чтение файла

Промпт:
```
Прочитай содержимое файла README.md
```

Ожидаемое поведение:
- Агент вызовет `fs/read_text_file` с параметром `path: "README.md"`
- В режиме `ask`: клиент запросит разрешение
- В режиме `code`: выполнится автоматически
- Результат: содержимое файла отобразится в ответе

#### Тест 2: Запись файла

Промпт:
```
Создай файл test.txt с содержимым "Hello, World!"
```

Ожидаемое поведение:
- Агент вызовет `fs/write_text_file` с параметрами `path: "test.txt"`, `content: "Hello, World!"`
- В режиме `ask`: клиент запросит разрешение
- Metadata будет содержать `diff` с изменениями
- Файл будет создан в рабочей директории

### Шаг 5: Тестирование Terminal tools

#### Тест 3: Выполнение команды

Промпт:
```
Выполни команду "ls -la" в терминале
```

Ожидаемое поведение:
- Агент вызовет `terminal/create` с параметром `command: "ls"`, `args: ["-la"]`
- В режиме `ask`: клиент запросит разрешение
- Metadata будет содержать `terminal_id`
- Агент может вызвать `terminal/wait_for_exit` для получения результата
- Результат команды отобразится в ответе

### Шаг 6: Тестирование Permission Flow

#### Тест 4: Ask режим

1. Переключиться в режим `ask`: `/mode ask`
2. Отправить промпт: "Прочитай файл config.yaml"
3. Ожидаемое поведение:
   - Появится модальное окно с запросом разрешения
   - Опции: Allow once, Allow always, Reject once, Reject always
   - После выбора "Allow once" - файл будет прочитан
   - После выбора "Reject once" - операция будет отменена

#### Тест 5: Saved policy

1. В режиме `ask` выбрать "Allow always" для `read` операции
2. Отправить новый промпт: "Прочитай файл package.json"
3. Ожидаемое поведение:
   - Разрешение НЕ запрашивается (используется saved policy)
   - Файл читается автоматически

## Проверка логов

### Логи сервера

Проверить логи на наличие:
```
tool_call_created: tool_name=fs/read_text_file
tool_execution_started: tool_name=fs/read_text_file
tool_execution_completed: success=True
```

### Логи клиента

Проверить получение notifications:
```
session/update: sessionUpdate=tool_call
session/update: sessionUpdate=tool_call_update
session/request_permission: (в ask режиме)
```

## Изменения в PROMPT

### Нужны ли изменения?

**НЕТ**, изменения в system prompt НЕ требуются для активации Tool Calls.

### Почему?

1. **Автоматическая регистрация**: Tools автоматически регистрируются в `PromptOrchestrator.__init__`
2. **LLM Provider интеграция**: Tools передаются в LLM через `available_tools` в `AgentContext`
3. **Нативная поддержка**: Современные LLM (GPT-4, Claude 3) нативно поддерживают function calling

### Опциональные улучшения PROMPT

Можно добавить в system prompt для улучшения поведения:

```
You have access to the following tools:
- fs/read_text_file: Read text files from the local filesystem
- fs/write_text_file: Write text files to the local filesystem
- terminal/create: Execute commands in the terminal
- terminal/wait_for_exit: Wait for terminal process to complete
- terminal/release: Release terminal resources

Use these tools when appropriate to help the user with their tasks.
```

Но это **опционально** - LLM автоматически видит доступные tools через API.

## Troubleshooting

### Tool calls не выполняются

1. Проверить что LLM provider поддерживает function calling
2. Проверить что `tool_registry` передан в `PromptOrchestrator`
3. Проверить логи на наличие ошибок регистрации tools

### Permission requests не появляются

1. Проверить что режим установлен в `ask`: `/mode ask`
2. Проверить что tool требует permission (`requires_permission: true`)
3. Проверить что `permission_manager` корректно инициализирован

### Tool execution fails

1. Проверить что `ClientRPCService` корректно настроен
2. Проверить что клиент поддерживает соответствующие capabilities
3. Проверить логи на наличие RPC ошибок

## Примеры промптов для тестирования

### File System
- "Покажи содержимое файла package.json"
- "Создай файл notes.txt с текстом 'Test notes'"
- "Прочитай первые 10 строк файла README.md"
- "Обнови файл config.yaml, добавив новую секцию"

### Terminal
- "Выполни команду 'pwd' чтобы показать текущую директорию"
- "Запусти 'npm install' в терминале"
- "Проверь версию Python командой 'python --version'"
- "Выполни 'git status' и покажи результат"

### Combined
- "Прочитай файл test.py и выполни его через Python"
- "Создай файл script.sh с командой 'echo Hello' и выполни его"
