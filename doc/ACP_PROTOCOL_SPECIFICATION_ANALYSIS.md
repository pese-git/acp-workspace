# Детальный анализ спецификации Agent Client Protocol (ACP)

## 1. ОБЗОР ПРОТОКОЛА

### 1.1 Назначение и философия

Agent Client Protocol (ACP) — стандартизированный протокол для взаимодействия между редакторами кода/IDE (клиентами) и AI-агентами для программирования. Протокол решает проблему фрагментации экосистемы, позволяя любому агенту работать с любым совместимым редактором.

**Ключевые принципы дизайна:**
- **MCP-friendly**: Построен на JSON-RPC, переиспользует типы из Model Context Protocol
- **UX-first**: Фокус на решении UX-задач взаимодействия с AI-агентами
- **Trusted**: Предполагает доверенную среду, где редактор предоставляет агенту доступ к локальным файлам и MCP-серверам

### 1.2 Модель коммуникации

- **Базовый протокол**: JSON-RPC 2.0
- **Типы сообщений**:
  - **Methods** (методы): запрос-ответ с ожиданием результата или ошибки
  - **Notifications** (уведомления): односторонние сообщения без ответа
- **Двунаправленность**: И клиент, и агент могут инициировать запросы
- **Потоковая передача**: Активное использование уведомлений для real-time обновлений

---

## 2. ЖИЗНЕННЫЙ ЦИКЛ ВЗАИМОДЕЙСТВИЯ

### 2.1 Фаза инициализации

#### Метод: `initialize`
**Направление**: Client → Agent

**Обязательные параметры запроса:**
- `protocolVersion` (integer): Последняя поддерживаемая версия протокола
- `clientCapabilities` (object): Возможности клиента

**Опциональные параметры:**
- `clientInfo` (object): Информация о клиенте
  - `name` (string): Программное имя
  - `title` (string): Отображаемое имя
  - `version` (string): Версия

**Обязательные поля ответа:**
- `protocolVersion` (integer): Выбранная версия протокола
- `agentCapabilities` (object): Возможности агента
- `authMethods` (array): Методы аутентификации

**Опциональные поля ответа:**
- `agentInfo` (object): Информация об агенте

**Согласование версии:**
1. Клиент отправляет последнюю поддерживаемую версию
2. Если агент поддерживает — отвечает той же версией
3. Иначе — отвечает последней поддерживаемой им версией
4. Если клиент не поддерживает версию агента — должен закрыть соединение

#### Метод: `authenticate` (опциональный)
**Направление**: Client → Agent
Используется если агент требует аутентификацию (указано в `authMethods`).

### 2.2 Фаза создания сессии

#### Метод: `session/new`
**Направление**: Client → Agent

**Обязательные параметры:**
- `cwd` (string): Абсолютный путь к рабочей директории
- `mcpServers` (array): Список MCP-серверов для подключения

**Ответ:**
- `sessionId` (string): Уникальный идентификатор сессии
- `modes` (object, опционально): Доступные режимы работы
- `configOptions` (array, опционально): Опции конфигурации

#### Метод: `session/load` (опциональный)
**Направление**: Client → Agent
**Требует capability**: `loadSession: true`

**Параметры:**
- `sessionId` (string): ID сессии для восстановления
- `cwd` (string): Рабочая директория
- `mcpServers` (array): MCP-серверы

**Поведение:**
1. Агент воспроизводит всю историю через `session/update` уведомления
2. После завершения потока — отправляет ответ на `session/load`

#### Метод: `session/list` (опциональный)
**Направление**: Client → Agent
**Требует capability**: `sessionCapabilities.list`

**Параметры:**
- `cwd` (string, опционально): Фильтр по директории
- `cursor` (string, опционально): Токен пагинации

**Ответ:**
- `sessions` (array): Массив объектов SessionInfo
- `nextCursor` (string, опционально): Токен следующей страницы

### 2.3 Фаза Prompt Turn (основной цикл)

#### Метод: `session/prompt`
**Направление**: Client → Agent

**Параметры:**
- `sessionId` (string): ID сессии
- `prompt` (ContentBlock[]): Содержимое сообщения пользователя

**Ответ (после завершения):**
- `stopReason` (string): Причина остановки
  - `end_turn`: Модель завершила ответ
  - `max_tokens`: Достигнут лимит токенов
  - `max_turn_requests`: Превышено число запросов к модели
  - `refusal`: Агент отказался продолжать
  - `cancelled`: Клиент отменил операцию

**Жизненный цикл:**
1. Клиент отправляет `session/prompt`
2. Агент обрабатывает с помощью LLM
3. Агент отправляет `session/update` уведомления:
   - План выполнения (`plan`)
   - Фрагменты сообщений (`agent_message_chunk`)
   - Вызовы инструментов (`tool_call`, `tool_call_update`)
4. При необходимости запрашивает разрешения (`session/request_permission`)
5. Выполняет инструменты, отправляет результаты в LLM
6. Повторяет шаги 3-5 до завершения
7. Отправляет финальный ответ с `stopReason`

#### Уведомление: `session/cancel`
**Направление**: Client → Agent

**Параметры:**
- `sessionId` (string): ID сессии

**Поведение:**
- Клиент должен немедленно пометить незавершенные tool calls как `cancelled`
- Клиент должен ответить `cancelled` на все pending `session/request_permission`
- Агент должен остановить все операции как можно скорее
- Агент должен ответить на `session/prompt` с `stopReason: "cancelled"`

---

## 3. CAPABILITIES (ВОЗМОЖНОСТИ)

### 3.1 Client Capabilities

#### File System
```json
"fs": {
  "readTextFile": boolean,   // Поддержка fs/read_text_file
  "writeTextFile": boolean   // Поддержка fs/write_text_file
}
```

#### Terminal
```json
"terminal": boolean  // Поддержка всех terminal/* методов
```

### 3.2 Agent Capabilities

#### Базовые
```json
{
  "loadSession": boolean  // Поддержка session/load
}
```

#### Prompt Capabilities
```json
"promptCapabilities": {
  "image": boolean,           // ContentBlock::Image
  "audio": boolean,           // ContentBlock::Audio
  "embeddedContext": boolean  // ContentBlock::Resource
}
```
**Базовая поддержка (обязательно)**: `ContentBlock::Text`, `ContentBlock::ResourceLink`

#### MCP Capabilities
```json
"mcpCapabilities": {
  "http": boolean,  // HTTP транспорт для MCP
  "sse": boolean    // SSE транспорт (deprecated)
}
```
**Базовая поддержка (обязательно)**: stdio транспорт

#### Session Capabilities
```json
"sessionCapabilities": {
  "list": {}  // Поддержка session/list
}
```

---

## 4. ТИПЫ КОНТЕНТА (ContentBlock)

### 4.1 Обязательные типы

#### Text
```json
{
  "type": "text",
  "text": "string",
  "annotations": {} // опционально
}
```

#### ResourceLink
```json
{
  "type": "resource_link",
  "uri": "string",           // обязательно
  "name": "string",          // обязательно
  "mimeType": "string",      // опционально
  "title": "string",         // опционально
  "description": "string",   // опционально
  "size": number,            // опционально
  "annotations": {}          // опционально
}
```

### 4.2 Опциональные типы (требуют capabilities)

#### Image (требует `promptCapabilities.image`)
```json
{
  "type": "image",
  "data": "base64-string",   // обязательно
  "mimeType": "string",      // обязательно
  "uri": "string",           // опционально
  "annotations": {}          // опционально
}
```

#### Audio (требует `promptCapabilities.audio`)
```json
{
  "type": "audio",
  "data": "base64-string",   // обязательно
  "mimeType": "string",      // обязательно
  "annotations": {}          // опционально
}
```

#### Resource (требует `promptCapabilities.embeddedContext`)
```json
{
  "type": "resource",
  "resource": {
    "uri": "string",         // обязательно
    // Либо text:
    "text": "string",
    "mimeType": "string",    // опционально
    // Либо blob:
    "blob": "base64-string",
    "mimeType": "string"     // опционально
  },
  "annotations": {}          // опционально
}
```

---

## 5. МЕТОДЫ ПРОТОКОЛА

### 5.1 Методы агента (Agent Methods)

#### Базовые (обязательные)
1. **`initialize`** - Согласование версии и capabilities
2. **`session/new`** - Создание новой сессии
3. **`session/prompt`** - Отправка пользовательского сообщения

#### Опциональные
4. **`authenticate`** - Аутентификация (если требуется)
5. **`session/load`** - Загрузка существующей сессии
6. **`session/list`** - Список доступных сессий
7. **`session/set_mode`** - Переключение режима (deprecated, использовать config options)
8. **`session/set_config_option`** - Установка опции конфигурации

#### Уведомления
9. **`session/cancel`** - Отмена текущей операции

### 5.2 Методы клиента (Client Methods)

#### Базовые (обязательные)
1. **`session/request_permission`** - Запрос разрешения на выполнение tool call

#### Опциональные (File System)
2. **`fs/read_text_file`** - Чтение текстового файла
3. **`fs/write_text_file`** - Запись текстового файла

#### Опциональные (Terminal)
4. **`terminal/create`** - Создание терминала и запуск команды
5. **`terminal/output`** - Получение вывода терминала
6. **`terminal/wait_for_exit`** - Ожидание завершения команды
7. **`terminal/kill`** - Принудительное завершение команды
8. **`terminal/release`** - Освобождение ресурсов терминала

#### Уведомления
9. **`session/update`** - Обновления состояния сессии (множественные типы)

---

## 6. SESSION/UPDATE УВЕДОМЛЕНИЯ

### 6.1 Типы обновлений (sessionUpdate)

#### Сообщения
1. **`user_message_chunk`** - Фрагмент сообщения пользователя
2. **`agent_message_chunk`** - Фрагмент ответа агента
3. **`thought_message_chunk`** - Фрагмент внутренних размышлений

#### Tool Calls
4. **`tool_call`** - Новый вызов инструмента
5. **`tool_call_update`** - Обновление статуса tool call

#### План
6. **`plan`** - План выполнения задачи

#### Конфигурация
7. **`current_mode_update`** - Изменение текущего режима (deprecated)
8. **`config_option_update`** - Обновление опций конфигурации
9. **`available_commands_update`** - Обновление доступных slash-команд

#### Метаданные сессии
10. **`session_info_update`** - Обновление метаданных сессии (title, updatedAt)

---

## 7. TOOL CALLS

### 7.1 Структура Tool Call

```json
{
  "toolCallId": "string",        // обязательно, уникальный ID
  "title": "string",             // обязательно, описание
  "kind": "ToolKind",            // опционально
  "status": "ToolCallStatus",    // обязательно
  "content": [],                 // опционально, ToolCallContent[]
  "locations": [],               // опционально, ToolCallLocation[]
  "rawInput": {},                // опционально
  "rawOutput": {}                // опционально
}
```

### 7.2 Tool Kinds
- `read` - Чтение файлов/данных
- `edit` - Модификация файлов/контента
- `delete` - Удаление файлов/данных
- `move` - Перемещение/переименование
- `search` - Поиск информации
- `execute` - Выполнение команд/кода
- `think` - Внутренние размышления
- `fetch` - Получение внешних данных
- `other` - Прочие типы (по умолчанию)

### 7.3 Tool Call Status
- `pending` - Ожидает запуска (стриминг входных данных или ожидание разрешения)
- `in_progress` - Выполняется
- `completed` - Успешно завершен
- `failed` - Завершен с ошибкой

### 7.4 Tool Call Content Types

#### Content
```json
{
  "type": "content",
  "content": ContentBlock  // Любой ContentBlock
}
```

#### Diff
```json
{
  "type": "diff",
  "path": "string",      // обязательно, абсолютный путь
  "oldText": "string",   // опционально, null для новых файлов
  "newText": "string"    // обязательно
}
```

#### Terminal
```json
{
  "type": "terminal",
  "terminalId": "string"  // обязательно
}
```

### 7.5 Permission Request

**Метод**: `session/request_permission`

**Параметры:**
```json
{
  "sessionId": "string",
  "toolCall": ToolCallUpdate,
  "options": [
    {
      "optionId": "string",
      "name": "string",
      "kind": "PermissionOptionKind"
    }
  ]
}
```

**Permission Option Kinds:**
- `allow_once` - Разрешить один раз
- `allow_always` - Разрешить и запомнить
- `reject_once` - Отклонить один раз
- `reject_always` - Отклонить и запомнить

**Ответ:**
```json
{
  "outcome": {
    "outcome": "selected" | "cancelled",
    "optionId": "string"  // если selected
  }
}
```

---

## 8. FILE SYSTEM МЕТОДЫ

### 8.1 fs/read_text_file

**Параметры:**
```json
{
  "sessionId": "string",
  "path": "string",      // абсолютный путь
  "line": number,        // опционально, 1-based
  "limit": number        // опционально, макс. строк
}
```

**Ответ:**
```json
{
  "content": "string"
}
```

### 8.2 fs/write_text_file

**Параметры:**
```json
{
  "sessionId": "string",
  "path": "string",      // абсолютный путь
  "content": "string"
}
```

**Ответ:**
```json
null
```

**Требования:**
- Клиент ДОЛЖЕН создать файл, если он не существует
- Клиент должен учитывать несохраненные изменения в редакторе

---

## 9. TERMINAL МЕТОДЫ

### 9.1 terminal/create

**Параметры:**
```json
{
  "sessionId": "string",
  "command": "string",           // обязательно
  "args": ["string"],            // опционально
  "env": [                       // опционально
    {"name": "string", "value": "string"}
  ],
  "cwd": "string",               // опционально, абсолютный путь
  "outputByteLimit": number      // опционально
}
```

**Ответ:**
```json
{
  "terminalId": "string"
}
```

**Важно:**
- Возвращается немедленно, команда выполняется в фоне
- Агент ДОЛЖЕН вызвать `terminal/release` когда терминал больше не нужен

### 9.2 terminal/output

**Параметры:**
```json
{
  "sessionId": "string",
  "terminalId": "string"
}
```

**Ответ:**
```json
{
  "output": "string",
  "truncated": boolean,
  "exitStatus": {              // опционально, если завершен
    "exitCode": number | null,
    "signal": string | null
  }
}
```

### 9.3 terminal/wait_for_exit

**Параметры:**
```json
{
  "sessionId": "string",
  "terminalId": "string"
}
```

**Ответ:**
```json
{
  "exitCode": number | null,
  "signal": string | null
}
```

### 9.4 terminal/kill

**Параметры:**
```json
{
  "sessionId": "string",
  "terminalId": "string"
}
```

**Поведение:**
- Завершает команду, но НЕ освобождает терминал
- После kill можно получить вывод через `terminal/output`
- Все равно нужно вызвать `terminal/release`

### 9.5 terminal/release

**Параметры:**
```json
{
  "sessionId": "string",
  "terminalId": "string"
}
```

**Поведение:**
- Завершает команду (если еще выполняется)
- Освобождает все ресурсы
- После release terminalId становится невалидным
- Если терминал был добавлен в tool call, клиент ДОЛЖЕН продолжать отображать его вывод

---

## 10. AGENT PLAN

### 10.1 Структура плана

```json
{
  "sessionUpdate": "plan",
  "entries": [
    {
      "content": "string",           // обязательно, описание задачи
      "priority": "PlanEntryPriority", // обязательно
      "status": "PlanEntryStatus"    // обязательно
    }
  ]
}
```

### 10.2 Plan Entry Priority
- `high` - Высокий приоритет
- `medium` - Средний приоритет
- `low` - Низкий приоритет

### 10.3 Plan Entry Status
- `pending` - Ожидает выполнения
- `in_progress` - Выполняется
- `completed` - Завершена

### 10.4 Обновление плана
- Агент ДОЛЖЕН отправлять полный список всех записей при каждом обновлении
- Клиент ДОЛЖЕН полностью заменять текущий план
- План может динамически изменяться (добавление/удаление/модификация записей)

---

## 11. SESSION CONFIGURATION

### 11.1 Session Modes (deprecated)

**Используйте Config Options вместо этого**

Структура:
```json
{
  "currentModeId": "string",
  "availableModes": [
    {
      "id": "string",
      "name": "string",
      "description": "string"
    }
  ]
}
```

### 11.2 Session Config Options (рекомендуется)

**Структура:**
```json
{
  "configOptions": [
    {
      "id": "string",              // обязательно
      "name": "string",            // обязательно
      "description": "string",     // опционально
      "category": "string",        // опционально
      "type": "select",            // обязательно
      "currentValue": "string",    // обязательно
      "options": [
        {
          "value": "string",       // обязательно
          "name": "string",        // обязательно
          "description": "string"  // опционально
        }
      ]
    }
  ]
}
```

**Категории:**
- `mode` - Режим сессии
- `model` - Выбор модели
- `thought_level` - Уровень размышлений
- `_custom_*` - Пользовательские категории (начинаются с `_`)

**Метод установки**: `session/set_config_option`

**Параметры:**
```json
{
  "sessionId": "string",
  "configId": "string",
  "value": "string"
}
```

**Ответ:** Полный список всех configOptions с обновленными значениями

---

## 12. SLASH COMMANDS

### 12.1 Структура команды

```json
{
  "sessionUpdate": "available_commands_update",
  "availableCommands": [
    {
      "name": "string",        // обязательно
      "description": "string", // обязательно
      "input": {               // опционально
        "hint": "string"
      }
    }
  ]
}
```

### 12.2 Использование
- Команды включаются в обычные prompt запросы как текст
- Формат: `/command_name optional_input`
- Могут комбинироваться с другими типами контента

---

## 13. MCP SERVERS

### 13.1 Stdio Transport (обязательный)

```json
{
  "name": "string",
  "command": "string",     // абсолютный путь
  "args": ["string"],
  "env": [
    {"name": "string", "value": "string"}
  ]
}
```

### 13.2 HTTP Transport (опциональный)

**Требует**: `mcpCapabilities.http: true`

```json
{
  "type": "http",
  "name": "string",
  "url": "string",
  "headers": [
    {"name": "string", "value": "string"}
  ]
}
```

### 13.3 SSE Transport (deprecated)

**Требует**: `mcpCapabilities.sse: true`

```json
{
  "type": "sse",
  "name": "string",
  "url": "string",
  "headers": [
    {"name": "string", "value": "string"}
  ]
}
```

---

## 14. EXTENSIBILITY (РАСШИРЯЕМОСТЬ)

### 14.1 Поле _meta

**Доступно во всех типах протокола:**
- Requests, responses, notifications
- Вложенные типы (content blocks, tool calls, plan entries, capabilities)

**Зарезервированные ключи (W3C Trace Context):**
- `traceparent`
- `tracestate`
- `baggage`

**Пример:**
```json
{
  "_meta": {
    "traceparent": "00-80e1afed08e019fc1110464cfa66635c-7a085853722dc6d2-01",
    "custom.field": "value"
  }
}
```

### 14.2 Extension Methods

**Правило именования:** Начинаются с `_`

**Custom Requests:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "_vendor.name/custom_method",
  "params": {}
}
```

**Custom Notifications:**
```json
{
  "jsonrpc": "2.0",
  "method": "_vendor.name/custom_notification",
  "params": {}
}
```

**Обработка неизвестных методов:**
- Requests: Ответить ошибкой -32601 "Method not found"
- Notifications: Игнорировать

### 14.3 Custom Capabilities

**Объявление в _meta:**
```json
{
  "agentCapabilities": {
    "loadSession": true,
    "_meta": {
      "vendor.name": {
        "customFeature": true
      }
    }
  }
}
```

---

## 15. TRANSPORTS

### 15.1 stdio (обязательный)

**Характеристики:**
- Клиент запускает агента как подпроцесс
- Агент читает из stdin, пишет в stdout
- Сообщения разделяются символом новой строки (`\n`)
- Сообщения НЕ ДОЛЖНЫ содержать встроенные переводы строк
- Агент МОЖЕТ писать логи в stderr
- Агент НЕ ДОЛЖЕН писать в stdout ничего кроме валидных ACP сообщений
- Клиент НЕ ДОЛЖЕН писать в stdin агента ничего кроме валидных ACP сообщений

### 15.2 Streamable HTTP (в разработке)

Спецификация в процессе обсуждения.

### 15.3 Custom Transports

Разрешены, но ДОЛЖНЫ:
- Сохранять формат JSON-RPC сообщений
- Соблюдать требования жизненного цикла ACP
- Документировать паттерны установки соединения и обмена сообщениями

---

## 16. КЛЮЧЕВЫЕ ТРЕБОВАНИЯ К РЕАЛИЗАЦИИ

### 16.1 Требования к АГЕНТУ

#### Обязательная функциональность:

**Методы (MUST implement):**
1. `initialize` - согласование версии и capabilities
2. `session/new` - создание сессии
3. `session/prompt` - обработка пользовательских сообщений

**Уведомления (MUST send):**
1. `session/update` с различными типами обновлений

**Capabilities (MUST support):**
1. Базовые типы контента: `Text`, `ResourceLink`
2. MCP stdio транспорт

**Транспорт (MUST support):**
1. stdio

#### Опциональная функциональность:

**Методы:**
1. `authenticate` - если требуется аутентификация
2. `session/load` - восстановление сессий
3. `session/list` - список сессий
4. `session/set_config_option` - управление конфигурацией

**Capabilities:**
1. `loadSession` - поддержка загрузки сессий
2. `promptCapabilities.image` - поддержка изображений
3. `promptCapabilities.audio` - поддержка аудио
4. `promptCapabilities.embeddedContext` - поддержка встроенных ресурсов
5. `mcpCapabilities.http` - HTTP транспорт для MCP
6. `sessionCapabilities.list` - список сессий

**Использование Client Methods:**
1. `session/request_permission` - запрос разрешений
2. `fs/read_text_file`, `fs/write_text_file` - файловые операции
3. `terminal/*` - управление терминалами

#### Критические требования:

1. **Версионирование:**
   - MUST согласовывать версию протокола в `initialize`
   - MUST поддерживать обратную совместимость в рамках мажорной версии

2. **Capabilities:**
   - MUST проверять client capabilities перед использованием опциональных методов
   - MUST корректно обрабатывать отсутствующие capabilities

3. **Пути:**
   - MUST использовать абсолютные пути для всех файловых операций
   - MUST использовать `cwd` из session/new как базовую директорию

4. **Cancellation:**
   - SHOULD останавливать все операции при получении `session/cancel`
   - MUST отвечать на `session/prompt` с `stopReason: "cancelled"`
   - MUST перехватывать исключения от отмененных операций

5. **Tool Calls:**
   - SHOULD отправлять обновления статуса tool calls
   - MAY запрашивать разрешения через `session/request_permission`

6. **Session State:**
   - MUST поддерживать контекст сессии между prompt turns
   - SHOULD сохранять историю для возможной загрузки

### 16.2 Требования к КЛИЕНТУ

#### Обязательная функциональность:

**Методы (MUST implement):**
1. `session/request_permission` - обработка запросов разрешений

**Инициализация (MUST do):**
1. Отправить `initialize` с корректными capabilities
2. Обработать согласование версии
3. Создать сессию через `session/new`

**Обработка уведомлений (MUST handle):**
1. `session/update` - все типы обновлений

#### Опциональная функциональность:

**Методы:**
1. `fs/read_text_file` - чтение файлов
2. `fs/write_text_file` - запись файлов
3. `terminal/create`, `terminal/output`, `terminal/wait_for_exit`, `terminal/kill`, `terminal/release`

**Capabilities:**
1. Объявлять поддерживаемые capabilities в `initialize`

#### Критические требования:

1. **Capabilities:**
   - MUST объявлять только поддерживаемые capabilities
   - MUST корректно реализовывать объявленные capabilities

2. **Cancellation:**
   - SHOULD немедленно помечать tool calls как `cancelled` при отправке `session/cancel`
   - MUST отвечать `cancelled` на все pending `session/request_permission`

3. **File System:**
   - MUST создавать файлы при `fs/write_text_file` если они не существуют
   - SHOULD учитывать несохраненные изменения в редакторе при `fs/read_text_file`

4. **Terminal:**
   - MUST корректно управлять жизненным циклом терминалов
   - SHOULD продолжать отображать вывод терминала после `terminal/release`
   - MUST обрезать вывод по границам символов при достижении `outputByteLimit`

5. **Session Updates:**
   - MUST обрабатывать все типы `session/update`
   - SHOULD отображать real-time обновления пользователю

6. **Config Options:**
   - SHOULD использовать `configOptions` вместо deprecated `modes`
   - SHOULD уважать порядок опций при отображении

### 16.3 Общие требования

1. **JSON-RPC:**
   - MUST использовать JSON-RPC 2.0
   - MUST кодировать сообщения в UTF-8

2. **Error Handling:**
   - MUST следовать стандартной обработке ошибок JSON-RPC 2.0
   - Успешные ответы включают поле `result`
   - Ошибки включают объект `error` с `code` и `message`

3. **Extensibility:**
   - MUST НЕ добавлять кастомные поля в корень типов спецификации
   - SHOULD использовать `_meta` для кастомных данных
   - SHOULD использовать префикс `_` для кастомных методов
   - MUST корректно обрабатывать неизвестные capabilities

4. **Line Numbers:**
   - MUST использовать 1-based нумерацию строк

5. **Paths:**
   - MUST использовать абсолютные пути для всех файловых операций

---

## ЗАКЛЮЧЕНИЕ

Agent Client Protocol предоставляет полноценную спецификацию для стандартизированного взаимодействия между AI-агентами и редакторами кода. Протокол:

- **Гибкий**: Поддерживает различные уровни функциональности через систему capabilities
- **Расширяемый**: Механизмы `_meta` и custom methods позволяют добавлять функциональность
- **Совместимый**: Использует JSON-RPC 2.0 и переиспользует типы из MCP
- **Практичный**: Фокусируется на реальных UX-задачах взаимодействия с AI-агентами

Ключевые области для реализации:
1. Базовый цикл инициализация → сессия → prompt turn
2. Система capabilities для опциональной функциональности
3. Real-time обновления через session/update
4. Интеграция с файловой системой и терминалом
5. Механизмы разрешений для безопасного выполнения операций
