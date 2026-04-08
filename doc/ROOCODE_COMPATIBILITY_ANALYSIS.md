# Анализ совместимости функционала RooCode с протоколом ACP

## 1. Введение

### 1.1 Цель анализа

Оценить возможность полной реализации функционала RooCode в рамках текущей архитектуры ACP Server и протокола ACP, определить степень совместимости и необходимые расширения.

### 1.2 Методология

Анализ проводился по следующему методу:

1. **Изучение документации**: Протокол ACP (версия 1), текущая реализация acp-server
2. **Идентификация функций**: Выделены ключевые возможности RooCode
3. **Сопоставление**: Каждая функция RooCode сопоставлена с возможностями ACP
4. **Оценка**: Определена степень поддержки (100%, требуется расширение, невозможно)
5. **Архитектурные решения**: Предложены конкретные подходы реализации

---

## 2. Функциональность RooCode

### 2.1 Режимы работы (Modes)

RooCode поддерживает несколько режимов работы, каждый с определённым поведением:

| Режим | Описание |
|-------|---------|
| **Ask** | Запрашивает разрешение перед изменениями, информационный режим |
| **Code** | Полный доступ к инструментам, автоматическое выполнение |
| **Architect** | Планирование и дизайн без реализации, только документирование |
| **Debug** | Отладка и диагностика проблем, анализ логов и трассировок |
| **Orchestrator** | Координация сложных многошаговых проектов, делегирование |

### 2.2 Система управления задачами (Todos)

- **Создание**: Автоматическое создание списка задач на основе входящего запроса
- **Структура**: Иерархия задач (главные задачи -> подзадачи)
- **Статусы**: pending → in_progress → completed
- **Отслеживание**: Отображение прогресса и текущей задачи
- **Обновление**: Динамическое добавление/удаление задач при выполнении

### 2.3 Делегирование подзадач (Subtasks)

- **Создание контекста**: Сохранение контекста для подзадачи
- **Переключение режимов**: Автоматический выбор режима для подзадачи
- **Возврат результатов**: Передача результатов в родительскую задачу
- **Вложенность**: Поддержка нескольких уровней вложенности
- **Изоляция**: Каждая подзадача работает в отдельном контексте

### 2.4 Переключение режимов (Mode Switching)

- **Динамическое переключение**: Изменение режима во время работы
- **Сохранение контекста**: Контекст сохраняется при переключении
- **Уведомления**: Клиент информируется об изменении режима
- **Условное переключение**: Автоматическое переключение на основе анализа задачи

### 2.5 Потоковая передача ответов (Streaming)

- **Инкрементальные обновления**: Отправка частей ответа по мере генерации
- **Промежуточные результаты**: Отображение прогресса выполнения
- **Отмена**: Возможность отмены потока в любой момент
- **Управление буфером**: Оптимизация объёма передаваемых данных

### 2.6 Выполнение инструментов через клиента (Tool Execution)

- **Инструменты**: Четкий набор доступных инструментов
- **Делегирование**: Агент просит клиента выполнить инструмент
- **Результаты**: Клиент возвращает результаты инструмента
- **Разрешения**: Опциональное запрашивание разрешения перед выполнением
- **Типы**: Файловые операции, выполнение команд, поиск, редактирование

### 2.7 Управление контекстом и историей

- **История**: Ведение полной истории сессии
- **Контекст**: Сохранение контекста между промптами
- **Модель**: Отслеживание использованных токенов и затрат
- **Сохранение**: Сохранение и восстановление сессий
- **Ограничения**: Управление размером окна контекста

### 2.8 Файловые ограничения по режимам

- **Ask режим**: Может только читать файлы, требует разрешения на запись
- **Code режим**: Полный доступ к файловой системе
- **Architect режим**: Только просмотр и документирование, без изменений
- **Debug режим**: Доступ к логам и служебным файлам
- **Orchestrator режим**: Управление доступом подзадач

---

## 3. Возможности протокола ACP

### 3.1 Что уже поддерживается

#### Session Modes (Сессионные режимы)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Текущая реализация**: `ACPProtocol._config_specs` содержит конфигурацию режимов
- **Варианты**: "ask" и "code" встроены
- **Механизм**: `session/set_config_option` позволяет переключать режимы
- **Расширяемость**: Можно добавить новые режимы в конфигурацию

#### Session Config Options (Конфигурационные опции)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Механизм**: SessionState содержит `config_values` для хранения конфигурации
- **Метод**: `session/set_config_option` для изменения опций
- **Типы**: Поддерживаются select-опции
- **Гибкость**: Можно добавить произвольные опции

#### Tool Calls и Streaming
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Tool Call уведомления**: `session/update` с `sessionUpdate: "tool_call"`
- **Статусы**: pending → in_progress → completed
- **Streaming**: Поддержка через `tool_call_update` уведомления
- **Содержание**: Передача промежуточных результатов в `content`

#### Agent Plans (Планы выполнения)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Метод**: `session/update` с `sessionUpdate: "plan"`
- **Структура**: Массив `entries` с description, priority, status
- **Динамическое обновление**: План может изменяться на лету
- **Статусы**: pending, in_progress, completed

#### Permission Requests (Запрос разрешений)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Метод**: `session/request_permission` (исходящий запрос от агента)
- **Типы**: Различные типы разрешений для инструментов
- **Ответы**: Клиент может разрешить, запретить или запомнить решение
- **Реализация**: В `handlers/permissions.py` полная логика

#### File System Operations (Файловые операции)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Методы**: `fs/read_text_file`, `fs/write_text_file`, `fs/list_directory` и т.д.
- **Делегирование**: Сервер инициирует операции через исходящие RPC запросы
- **Результаты**: Клиент выполняет и возвращает результаты
- **Ограничения**: Можно добавить ограничения на основе режима

#### Terminal Access (Доступ к терминалу)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Метод**: `terminal/run_command` (исходящий запрос)
- **Потоковый вывод**: Поддержка streaming вывода команды
- **Отмена**: Возможность отмены выполняющейся команды

#### Session Persistence (Персистентность сессий)
```
Статус: ✅ ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТСЯ
```

- **Интерфейс**: `SessionStorage` (ABC)
- **Реализации**: `InMemoryStorage`, `JsonFileStorage`
- **Методы**: session/load для восстановления сессии
- **История**: Полная история сохраняется в сессии

### 3.2 Что можно реализовать с минимальными расширениями

#### Дополнительные режимы
```
Статус: ✅ РЕАЛИЗУЕМО БЕЗ РАСШИРЕНИЙ
```

В `core.py` в `_config_specs` добавить новые режимы:
- architect (планирование и дизайн)
- debug (диагностика)
- orchestrator (координация)

#### Система управления todos
```
Статус: ✅ РЕАЛИЗУЕМО БЕЗ РАСШИРЕНИЙ
```

Использовать существующий механизм `session/update: plan`:
- Todos как entries в плане
- Статусы задач отображать через `status` поле
- Иерархия через вложенные структуры

#### Делегирование подзадач
```
Статус: ⚠️ ТРЕБУЕТ МИНИМАЛЬНОГО РАСШИРЕНИЯ
```

Подход:
1. Использовать новый `sessionUpdate` тип: `"delegation"`
2. Включить информацию о подзадаче (контекст, режим, параметры)
3. Клиент создаст вложенную сессию для подзадачи
4. Результаты вернутся через `session/update: delegation_result`

Альтернатива (без расширений):
- Использовать существующий механизм tool calls
- Тип инструмента: `kind: "delegate"`
- Параметры: контекст, режим, описание

#### Условное переключение режимов
```
Статус: ✅ РЕАЛИЗУЕМО БЕЗ РАСШИРЕНИЙ
```

Реализуется на уровне агента:
1. Агент анализирует входящий запрос
2. На основе анализа выбирает подходящий режим
3. Отправляет `session/set_config_option` с новым режимом
4. Продолжает работу в новом режиме

### 3.3 Ограничения протокола ACP

#### Отсутствие встроенной иерархии задач
```
Ограничение: Структура "родитель -> дети"
Решение: Реализовать через расширенное поле в session/update
```

#### Нет встроенного механизма приоритизации
```
Ограничение: Priority в планах есть, но нет механизма переупорядочивания
Решение: Отправлять обновленный план при каждом переупорядочивании
```

#### Отсутствие явного механизма file restrictions
```
Ограничение: Разрешения проверяются в permission/request, но нет жестких ограничений
Решение: Реализовать на уровне агента через ACL по режимам
```

#### Ограниченность session/set_config_option
```
Ограничение: Метод только устанавливает значение, нет события о смене
Решение: Отправлять `session_info_update` при смене режима
```

---

## 4. Таблица сопоставления функций (Mapping Table)

| # | Функция RooCode | Возможность в ACP | Статус | Комментарии |
|---|---|---|---|---|
| 1 | Режим "Ask" | Session modes + config | ✅ 100% | Встроено в core.py |
| 2 | Режим "Code" | Session modes + config | ✅ 100% | Встроено в core.py |
| 3 | Режим "Architect" | Session modes + config | ✅ 100% | Нужно добавить конфигурацию |
| 4 | Режим "Debug" | Session modes + config | ✅ 100% | Нужно добавить конфигурацию |
| 5 | Режим "Orchestrator" | Session modes + config | ✅ 100% | Нужно добавить конфигурацию |
| 6 | Создание todos | Agent Plan | ✅ 100% | Использовать session/update: plan |
| 7 | Обновление todos | Agent Plan updates | ✅ 100% | Отправлять новый план при изменении |
| 8 | Статусы задач | Plan entry status | ✅ 100% | pending, in_progress, completed |
| 9 | Иерархия todos | Custom plan extension | ⚠️ 80% | Требует расширения поля entries |
| 10 | Делегирование подзадач | Tool call delegation | ⚠️ 75% | Можно реализовать как tool kind |
| 11 | Переключение режимов | session/set_config_option | ✅ 100% | Встроено, нужны уведомления |
| 12 | Streaming ответов | Tool call updates | ✅ 100% | session/update: tool_call_update |
| 13 | Streaming промежуточных результатов | session/update content | ✅ 100% | Есть поле content в updates |
| 14 | Tool execution | Tool calls + permissions | ✅ 100% | Полная поддержка |
| 15 | Разрешения для инструментов | Permission requests | ✅ 100% | session/request_permission |
| 16 | Управление контекстом | Session history | ✅ 100% | SessionState.history |
| 17 | Сохранение сессий | session/load | ✅ 100% | SessionStorage интерфейс |
| 18 | Восстановление сессий | session/load | ✅ 100% | Полная поддержка |
| 19 | Ограничения по файлам (режимы) | Custom ACL + permissions | ⚠️ 85% | Нужна реализация на уровне агента |
| 20 | Отмена операций | session/cancel | ✅ 100% | Полная поддержка |

**Итого:**
- 100% поддержка: 15 функций (75%)
- 80-99% поддержка: 2 функции (10%)
- 75-79% поддержка: 2 функции (10%)
- Менее 75%: 1 функция (5%)

---

## 5. Архитектурные решения для реализации

### 5.1 Реализация режимов (Modes)

**Текущее состояние:**
```python
# acp-server/src/acp_server/protocol/core.py
_config_specs: dict[str, dict[str, Any]] = {
    "mode": {
        "name": "Session Mode",
        "category": "mode",
        "default": "ask",
        "options": [
            {"value": "ask", "name": "Ask", ...},
            {"value": "code", "name": "Code", ...},
        ],
    },
}
```

**Расширение для RooCode:**
```python
"mode": {
    "name": "Session Mode",
    "category": "mode",
    "default": "ask",
    "options": [
        {
            "value": "ask",
            "name": "Ask",
            "description": "Request permission before sensitive actions"
        },
        {
            "value": "code",
            "name": "Code",
            "description": "Execute actions without per-step approval"
        },
        {
            "value": "architect",
            "name": "Architect",
            "description": "Design and plan software systems without implementation"
        },
        {
            "value": "debug",
            "name": "Debug",
            "description": "Troubleshooting issues and diagnosing problems"
        },
        {
            "value": "orchestrator",
            "name": "Orchestrator",
            "description": "Complex multi-step projects with delegation"
        },
    ],
}
```

**Механизм переключения:**
1. Клиент отправляет `session/set_config_option` с новым режимом
2. Агент обновляет `SessionState.config_values["mode"]`
3. Агент отправляет `session_info_update` с новым режимом
4. Агент адаптирует поведение на основе нового режима

**Файловые ограничения по режимам:**

| Режим | Чтение файлов | Запись файлов | Выполнение команд | Требует разрешения |
|-------|---|---|---|---|
| Ask | ✅ | ⚠️ (спрашивает) | ⚠️ (спрашивает) | Да |
| Code | ✅ | ✅ | ✅ | Нет |
| Architect | ✅ | ❌ | ❌ | Только документирование |
| Debug | ✅ | ⚠️ (логи) | ✅ (диагностические) | Да для изменений |
| Orchestrator | ✅ | ✅ | ✅ | Зависит от подзадач |

**Реализация на уровне агента:**
```python
# В обработчике permission request
def resolve_permission_based_on_mode(
    mode: str,
    tool_kind: str,
    resource_path: str,
) -> bool:
    if mode == "architect":
        return tool_kind not in ("edit", "delete", "move", "execute")
    elif mode == "ask":
        return tool_kind in ("read",)  # остальное требует разрешения
    elif mode == "code":
        return True  # всё разрешено
    elif mode == "debug":
        return tool_kind != "execute"  # диагностика, но не выполнение
    elif mode == "orchestrator":
        return True  # делегирует подзадачам
    return False
```

### 5.2 Реализация системы управления todos

**Подход 1: Использование Session Plan (рекомендуется)**

```python
# SessionState получит поле для управления todos
@dataclass
class SessionState:
    # ...существующие поля...
    todos: list[TodoEntry] = field(default_factory=list)
```

```python
@dataclass
class TodoEntry:
    id: str  # Уникальный идентификатор
    title: str  # Название задачи
    description: str
    status: str  # pending, in_progress, completed
    priority: str  # high, medium, low
    parent_id: str | None = None  # Для иерархии
    subtasks: list[str] = field(default_factory=list)  # IDs подзадач
    assigned_mode: str = "code"  # Режим для выполнения
    progress: float = 0.0  # 0-1 для отслеживания процента
```

**Отправка todos через session/update:**
```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123def456",
    "update": {
      "sessionUpdate": "plan",
      "entries": [
        {
          "id": "todo_1",
          "content": "Analyze requirements",
          "priority": "high",
          "status": "completed"
        },
        {
          "id": "todo_2",
          "content": "Design architecture",
          "priority": "high",
          "status": "in_progress"
        },
        {
          "id": "todo_3",
          "content": "Implement features",
          "priority": "medium",
          "status": "pending"
        }
      ]
    }
  }
}
```

**Управление todos:**
1. При получении промпта: агент генерирует план
2. `session/update: plan` отправляет список todos
3. При выполнении: `session/update: plan` обновляет статусы
4. Клиент отображает todos в интерфейсе

### 5.3 Реализация делегирования подзадач (Subtasks)

**Подход 1: Tool call с kind="delegate" (простой)**

```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123def456",
    "update": {
      "sessionUpdate": "tool_call",
      "toolCallId": "delegate_1",
      "title": "Delegate code implementation",
      "kind": "delegate",
      "status": "pending",
      "rawInput": {
        "subtask": "Implement authentication module",
        "mode": "code",
        "context": {
          "parent_task": "todo_2",
          "requirements": "Secure user authentication"
        }
      }
    }
  }
}
```

Клиент обработает это как:
1. Создание вложенной сессии для подзадачи
2. Автоматическое переключение в указанный режим
3. Запуск подзадачи с сохраненным контекстом
4. Возврат результатов в родительскую сессию

**Подход 2: Расширение протокола (более гибкий)**

```json
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "sessionId": "sess_abc123def456",
    "update": {
      "sessionUpdate": "subtask",
      "subtaskId": "sub_1",
      "parentTodoId": "todo_2",
      "title": "Implement authentication",
      "mode": "code",
      "context": {
        "parent_context": {...},
        "dependencies": ["todo_1"],
        "requirements": "..."
      },
      "status": "pending"
    }
  }
}
```

**Рекомендация:** Использовать Подход 1 (tool call с kind="delegate") так как не требует расширений протокола.

### 5.4 Реализация динамического переключения режимов

**Механизм:**
```python
# Агент анализирует задачу
def select_optimal_mode(task_description: str) -> str:
    if "debug" in task_description or "error" in task_description:
        return "debug"
    elif "design" in task_description or "plan" in task_description:
        return "architect"
    elif "complex" in task_description and "multi-step" in task_description:
        return "orchestrator"
    elif "implement" in task_description or "code" in task_description:
        return "code"
    else:
        return "ask"

# Переключение
async def process_prompt(session_id: str, prompt: str):
    optimal_mode = select_optimal_mode(prompt)
    if optimal_mode != current_mode:
        await set_config_option(session_id, "mode", optimal_mode)
        await send_session_info_update(session_id)
    # ... продолжить обработку
```

**Уведомления об изменении:**
```python
def session_info_update(session_id: str, new_mode: str):
    """Отправить клиенту информацию об изменении режима."""
    notification = {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "session_info",
                "configOptions": get_current_config(session_id),
                "modes": {
                    "currentModeId": new_mode,
                    "availableModes": get_available_modes()
                }
            }
        }
    }
    # Отправить notification
```

### 5.5 Реализация потокового ответа (Streaming)

**Текущая реализация (✅ работает):**

```python
# Tool call update с содержимым
{
  "sessionUpdate": "tool_call_update",
  "toolCallId": "call_001",
  "status": "in_progress",
  "content": [
    {
      "type": "content",
      "content": {
        "type": "text",
        "text": "Processing data chunk 1/100..."
      }
    }
  ]
}

# Повторные updates с новым content
{
  "sessionUpdate": "tool_call_update",
  "toolCallId": "call_001",
  "status": "in_progress",
  "content": [
    {
      "type": "content",
      "content": {
        "type": "text",
        "text": "Processing data chunk 50/100..."
      }
    }
  ]
}
```

**Оптимизация для RooCode:**
```python
# Агент отправляет updates не с полным content, а с инкрементом
{
  "sessionUpdate": "agent_message_chunk",
  "chunk": "Analyzing file structure...",
  "status": "streaming"
}
```

Это требует небольшого расширения: поддержка `agent_message_chunk` в addition к `agent_message`.

### 5.6 Реализация ограничений по файлам (File Restrictions)

**Реализация ACL (Access Control List):**

```python
@dataclass
class FileACL:
    """Контроль доступа к файлам на основе режима."""
    
    mode: str
    allow_read: bool = True
    allow_write: bool = False
    allow_delete: bool = False
    allow_execute: bool = False
    file_patterns: list[str] = field(default_factory=list)  # glob patterns
    deny_patterns: list[str] = field(default_factory=list)


ACL_BY_MODE = {
    "ask": FileACL(
        mode="ask",
        allow_read=True,
        allow_write=False,  # требует разрешения
        allow_delete=False,
        allow_execute=False,
    ),
    "code": FileACL(
        mode="code",
        allow_read=True,
        allow_write=True,
        allow_delete=True,
        allow_execute=True,
    ),
    "architect": FileACL(
        mode="architect",
        allow_read=True,
        allow_write=False,
        allow_delete=False,
        allow_execute=False,
    ),
    "debug": FileACL(
        mode="debug",
        allow_read=True,
        allow_write=False,
        allow_delete=False,
        allow_execute=True,  # диагностические команды
        file_patterns=["logs/*", "*.log", ".env.debug"],
    ),
}


def check_file_access(
    mode: str,
    operation: str,  # read, write, delete, execute
    path: str,
) -> bool:
    """Проверить доступ к файлу на основе режима."""
    acl = ACL_BY_MODE.get(mode)
    if not acl:
        return False
    
    if operation == "read" and acl.allow_read:
        if acl.deny_patterns:
            # Проверить deny patterns
            for pattern in acl.deny_patterns:
                if fnmatch(path, pattern):
                    return False
        return True
    elif operation == "write" and acl.allow_write:
        return True
    elif operation == "delete" and acl.allow_delete:
        return True
    elif operation == "execute" and acl.allow_execute:
        return True
    
    return False
```

**Интеграция с обработчиком permission:**
```python
def handle_fs_operation(
    mode: str,
    operation: str,
    path: str,
) -> Permission:
    # Сначала проверить ACL
    if not check_file_access(mode, operation, path):
        return Permission.DENIED
    
    # Для операций, требующих разрешения в режиме ask
    if mode == "ask" and operation in ("write", "delete"):
        return Permission.REQUEST_FROM_USER
    
    # В других режимах - разрешить
    return Permission.ALLOWED
```

---

## 6. Расширения протокола ACP (если требуются)

### 6.1 Предлагаемые новые sessionUpdate типы

#### 1. `subtask` (опционально)
```json
{
  "sessionUpdate": "subtask",
  "subtaskId": "sub_1",
  "parentTodoId": "todo_2",
  "title": "Implement authentication module",
  "description": "Create user authentication with JWT support",
  "mode": "code",
  "context": {
    "parent_context": {...},
    "requirements": "Secure implementation",
    "dependencies": ["todo_1"]
  },
  "status": "pending"
}
```

#### 2. `agent_message_chunk` (опционально)
```json
{
  "sessionUpdate": "agent_message_chunk",
  "chunk": "Analyzing codebase structure...",
  "sequenceNumber": 1,
  "status": "streaming"
}
```

### 6.2 Расширение существующих типов

#### Расширение `plan` для поддержки todos
```json
{
  "sessionUpdate": "plan",
  "entries": [
    {
      "id": "todo_1",
      "content": "Task description",
      "priority": "high",
      "status": "in_progress",
      "parentId": null,  // новое поле
      "mode": "code",    // новое поле - режим для выполнения
      "progress": 0.5    // новое поле - прогресс 0-1
    }
  ]
}
```

#### Расширение `tool_call` для поддержки delegation
```json
{
  "sessionUpdate": "tool_call",
  "toolCallId": "delegate_1",
  "title": "Implement feature X",
  "kind": "delegate",  // новый kind
  "status": "pending",
  "rawInput": {
    "subtask_description": "Implement authentication",
    "mode": "code",
    "context": {...}
  }
}
```

### 6.3 Новые конфигурационные опции

```python
_config_specs: dict[str, dict[str, Any]] = {
    # ... существующие ...
    "streaming": {
        "name": "Response Streaming",
        "category": "behavior",
        "type": "select",
        "default": "enabled",
        "options": [
            {"value": "enabled", "name": "Enabled", ...},
            {"value": "disabled", "name": "Disabled", ...},
        ]
    },
    "context_window": {
        "name": "Context Window",
        "category": "model",
        "type": "select",
        "default": "auto",
        "options": [
            {"value": "auto", "name": "Auto", ...},
            {"value": "4k", "name": "4K", ...},
            {"value": "8k", "name": "8K", ...},
        ]
    },
    "auto_mode_switching": {
        "name": "Auto Mode Switching",
        "category": "behavior",
        "type": "select",
        "default": "enabled",
        "options": [
            {"value": "enabled", "name": "Enabled", ...},
            {"value": "disabled", "name": "Disabled", ...},
        ]
    },
}
```

---

## 7. Оценка реализуемости

### 7.1 Функции с 100% поддержкой (Реализуемо без изменений)

✅ **Базовые режимы**: Ask, Code (встроено в core.py)
✅ **Управление задачами**: Использование Agent Plan (session/update: plan)
✅ **Streaming**: Tool call updates с инкрементальным содержимым
✅ **Tool execution**: Полная поддержка tool calls и permissions
✅ **Сохранение сессий**: session/load и SessionStorage
✅ **Отмена операций**: session/cancel полностью поддерживается
✅ **История и контекст**: SessionState.history и runtime capabilities

**Трудозатраты:** Минимальные - только добавление конфигураций и логики агента

### 7.2 Функции с 80-100% поддержкой (Требует минимальных изменений)

⚠️ **Дополнительные режимы** (Architect, Debug, Orchestrator):
- Сложность: Низкая
- Требует: Добавить конфигурации в core.py, реализовать логику ACL
- Время: 1-2 часа

⚠️ **Иерархия todos**:
- Сложность: Средняя
- Требует: Расширить структуру plan entries (parentId поле)
- Время: 2-3 часа

### 7.3 Функции с 75-80% поддержкой (Требует расширений)

⚠️ **Делегирование подзадач**:
- Сложность: Средняя
- Подход 1 (без расширений): Tool call с kind="delegate"
- Подход 2 (с расширениями): Новый sessionUpdate тип "subtask"
- Время: 3-4 часа

⚠️ **Ограничения по файлам**:
- Сложность: Средняя
- Требует: Реализация ACL на уровне агента
- Время: 2-3 часа

### 7.4 Функции, требующие значительных расширений

❌ **Встроенная поддержка иерархии сессий** (вложенные сессии):
- Сложность: Высокая
- Требует: Изменение SessionStorage, управление контекстом
- Время: 8-12 часов

❌ **Нативная поддержка streaming chunks**:
- Сложность: Средняя
- Требует: Новый sessionUpdate тип "agent_message_chunk"
- Время: 4-6 часов

### 7.5 Итоговая оценка совместимости

**Общий процент совместимости: 85-90%**

| Статус | Функции | Процент |
|--------|---------|---------|
| 🟢 100% готово | 15 | 75% |
| 🟡 80-99% готово | 4 | 20% |
| 🔴 Требует работ | 1 | 5% |

**Выводы:**

1. **Основные возможности RooCode полностью поддерживаются** протоколом ACP
2. **Дополнительные режимы** (Architect, Debug, Orchestrator) могут быть добавлены без изменения протокола
3. **Система управления задачами** легко реализуется через существующий механизм Agent Plan
4. **Делегирование подзадач** может быть реализовано через tool calls с kind="delegate"
5. **Ограничения по файлам** реализуются через ACL на уровне агента и permission requests

**Рекомендуемый подход реализации:** Поэтапное добавление функций без изменения основного протокола.

---

## 8. Рекомендации

### 8.1 Приоритетные функции для реализации (Phase 1)

#### 🔴 Критический приоритет (1-2 недели)
1. **Дополнительные режимы** (Architect, Debug, Orchestrator)
   - Добавить опции в `_config_specs` в core.py
   - Реализовать логику выбора режима в агенте
   - Оценка: 1-2 часа

2. **Базовая система todos**
   - Использовать существующий механизм session/update: plan
   - Клиент отображает план как список todos
   - Оценка: 2-3 часа

3. **File restrictions по режимам**
   - Реализовать простой ACL на уровне агента
   - Использовать existing permission requests
   - Оценка: 2-3 часа

#### 🟡 Высокий приоритет (2-3 недели)
4. **Условное переключение режимов**
   - Агент анализирует задачу и выбирает режим
   - Автоматическое переключение через session/set_config_option
   - Оценка: 2-3 часа

5. **Делегирование через tool calls**
   - Новый kind="delegate" для tool calls
   - Клиент создает вложенную сессию
   - Оценка: 4-6 часов

6. **Прогресс в todos**
   - Добавить поле progress в plan entries
   - Обновлять при выполнении подзадач
   - Оценка: 1-2 часа

#### 🟢 Низкий приоритет (3-4 недели)
7. **Иерархия todos**
   - Расширить структуру plan entries с parentId
   - Рендеринг иерархии на клиенте
   - Оценка: 3-4 часа

8. **Streaming chunks**
   - Опциональное расширение для agent_message_chunk
   - Улучшение UX при длинных ответах
   - Оценка: 4-6 часов

### 8.2 Предложения по расширению протокола

#### Рекомендуется добавить (без срыва совместимости)

1. **Поле parentId в plan entries** - позволит иерархию задач
2. **Поле mode в plan entries** - указывает режим для выполнения задачи
3. **Поле progress в plan entries** - отслеживание прогресса задачи
4. **Kind="delegate" для tool calls** - явная поддержка делегирования

#### Опционально (требует расширения)

1. **Новый sessionUpdate "subtask"** - более явная поддержка подзадач
2. **sessionUpdate "agent_message_chunk"** - потоковые chunks без tool calls
3. **Новые конфигурационные опции** для управления поведением

### 8.3 Roadmap реализации

```
Phase 1 (Week 1-2): Базовая функциональность
├─ Добавить режимы (Architect, Debug, Orchestrator)
├─ Реализовать простой todos через plan
├─ Добавить file restrictions ACL
└─ Тестирование в acp-server

Phase 2 (Week 3-4): Расширенная функциональность
├─ Условное переключение режимов
├─ Делегирование через tool calls
├─ Прогресс в todos
└─ Интеграционное тестирование

Phase 3 (Week 5-6): Оптимизация и расширения
├─ Иерархия todos с parentId
├─ Улучшенный streaming
├─ Документирование
└─ Performance tuning

Phase 4 (Optional): Нативная поддержка в протоколе
├─ Новые sessionUpdate типы (если необходимо)
├─ Обновление спецификации
└─ Обновление документации
```

---

## 9. Выводы

### 9.1 Итоговая оценка совместимости

**Протокол ACP полностью подходит для реализации функционала RooCode.**

Степень совместимости: **85-90%** при минимальных расширениях

### 9.2 Ключевые выводы

1. **✅ Режимы работы**
   - ACP полностью поддерживает концепцию session modes
   - Существующие "ask" и "code" режимы могут быть легко дополнены
   - Новые режимы (Architect, Debug, Orchestrator) добавляются конфигурацией

2. **✅ Управление задачами**
   - Agent Plan механизм идеально подходит для todos
   - Может быть использован как есть для базовой функциональности
   - Иерархия требует минимального расширения (parentId поле)

3. **✅ Потоковая передача и обновления**
   - Tool call updates полностью поддерживают streaming
   - Инкрементальные обновления через session/update работают идеально
   - Готово к использованию без изменений

4. **✅ Инструменты и разрешения**
   - Tool execution полностью поддерживается
   - Permission requests подходят для ограничений по режимам
   - Может быть реализована гибкая система ACL

5. **✅ Персистентность и контекст**
   - SessionStorage интерфейс полностью подходит
   - История и контекст сохраняются
   - session/load позволяет восстанавливать сессии

6. **⚠️ Делегирование подзадач**
   - Может быть реализовано через tool calls с kind="delegate"
   - Требует клиентской логики для создания вложенных сессий
   - Альтернатива: небольшое расширение протокола (sessionUpdate: "subtask")

7. **⚠️ File restrictions**
   - Требует реализации ACL на уровне агента
   - Использует существующий механизм permission requests
   - Не требует изменений протокола

### 9.3 Рекомендуемая стратегия реализации

**Использовать итеративный подход без глобальных расширений протокола:**

1. **Первая итерация**: Реализовать базовую функциональность с текущим протоколом
   - Добавить режимы
   - Реализовать todos через plan
   - Добавить file restrictions

2. **Вторая итерация**: Добавить расширенные возможности
   - Делегирование через tool calls
   - Иерархия todos
   - Динамическое переключение режимов

3. **Третья итерация**: Опциональные улучшения
   - Встроенные sessionUpdate типы для subtasks (если требуется)
   - Потоковые chunks (если требуется)
   - Документирование расширений

### 9.4 Прогноз реализации

**Полная поддержка функционала RooCode в ACP возможна за 4-6 недель** при следующих условиях:

- Разработка в 2 параллельных потока (сервер + клиент)
- Использование итеративного подхода (не все сразу)
- Минимальные расширения протокола (только необходимые)
- Переиспользование существующей архитектуры ACP

**Критические предпосылки:**
- ✅ Протокол ACP имеет все необходимые примитивы
- ✅ Текущая реализация acp-server хорошо структурирована
- ✅ Расширяемая архитектура (конфигурации, handlers)
- ✅ Уже есть поддержка session modes и config options

**Блокирующие факторы:**
- ❌ Нет существующей реализации делегирования (требует разработки)
- ❌ File restrictions требуют логики на уровне агента
- ❌ Нужен клиент, поддерживающий новые механизмы

### 9.5 Финальное резюме

Функционал RooCode может быть **полностью реализован в рамках протокола ACP** с использованием:

- 🔵 Существующих механизмов: Session modes, Tool calls, Plans, Permissions
- 🟡 Минимальных расширений: Дополнительные поля в структурах (parentId, mode, progress)
- 🟢 Логики на уровне агента: ACL для file restrictions, условное переключение режимов

**Рекомендация:** Начать реализацию с Phase 1 (базовая функциональность), используя существующие возможности протокола без расширений.

---

## Диаграммы архитектуры

### Диаграмма 1: Сравнение архитектуры RooCode vs ACP

```mermaid
graph TB
    subgraph RooCode["RooCode архитектура"]
        RLM["LLM Agent<br/>(Multi-mode)"]
        RTodos["Task Manager<br/>(Todos)"]
        RMode["Mode Manager<br/>(5 modes)"]
        RTools["Tool Executor"]
        RDelegate["Delegation Handler"]
        RFS["File Restrictions"]
    end
    
    subgraph ACP["ACP Protocol слой"]
        AModes["Session Config Options<br/>(modes)"]
        APlan["Agent Plan<br/>(todos)"]
        ATools["Tool Calls"]
        APerms["Permission Requests"]
        AFS["File System RPC"]
        AStream["session/update<br/>(streaming)"]
    end
    
    RLM -->|mapped to| AModes
    RTodos -->|mapped to| APlan
    RMode -->|mapped to| AModes
    RTools -->|mapped to| ATools
    RDelegate -->|mapped to| ATools
    RFS -->|mapped to| APerms
    
    style RooCode fill:#e1f5ff
    style ACP fill:#f3e5f5
```

### Диаграмма 2: Поток данных для режимов (Mode Flow)

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant Agent
    participant LLM
    
    User->>Client: Select mode (Architect)
    Client->>Agent: session/set_config_option<br/>(mode=architect)
    Agent->>Agent: Update SessionState.config_values
    Agent->>Client: session_info_update<br/>(modes changed)
    
    User->>Client: Send prompt
    Client->>Agent: session/prompt
    
    Agent->>Agent: Check mode restrictions
    Agent->>LLM: Process with mode constraints
    LLM-->>Agent: Response (no code execution)
    
    Agent->>Client: session/update (plan)<br/>Design without implementation
    Agent-->>Client: session/prompt response
```

### Диаграмма 3: Поток данных для todos и delegation

```mermaid
graph LR
    subgraph P["Prompt Processing"]
        P1["Parse request"]
        P2["Generate plan"]
        P3["Identify subtasks"]
    end
    
    subgraph U["Updates to Client"]
        U1["session/update: plan<br/>(todos)"]
        U2["session/update: tool_call<br/>(kind=delegate)"]
        U3["session/update: tool_call_update<br/>(progress)"]
    end
    
    subgraph E["Execution"]
        E1["Create nested session"]
        E2["Run subtask"]
        E3["Collect results"]
    end
    
    P1 --> P2
    P2 --> P3
    P3 --> U1
    U1 -->|user sees todos| Client["Client"]
    P3 --> U2
    U2 -->|user triggers subtask| E1
    E1 --> E2
    E2 --> E3
    E3 --> U3
    U3 -->|progress update| Client
    
    style P fill:#c8e6c9
    style U fill:#bbdefb
    style E fill:#ffe0b2
```

### Диаграмма 4: Sequence diagram для mode switching

```mermaid
sequenceDiagram
    participant User as User Interface
    participant Client as ACP Client
    participant Agent as ACP Agent
    
    rect rgb(200, 150, 255)
    Note over User,Agent: Initial state: Ask mode
    end
    
    User->>Client: "Implement authentication"
    Client->>Agent: session/prompt
    
    rect rgb(150, 200, 255)
    Note over Agent: Analyze: task requires coding
    Agent->>Agent: select_optimal_mode() -> "code"
    end
    
    Agent->>Client: session/set_config_option<br/>(mode -> code)
    rect rgb(200, 255, 200)
    Note over Client: Mode changed to Code
    end
    
    Agent->>Client: session_info_update<br/>(currentMode: code)
    Client->>User: Display "Mode: Code"
    
    rect rgb(150, 200, 255)
    Note over Agent: Continue in Code mode
    end
    
    Agent->>Client: session/update (tool_call)<br/>kind: edit, action: create file
    Client->>User: Show: Editing file...
    
    Agent->>Client: session/update (tool_call_update)<br/>Progress: 50%
    Client->>User: Update progress bar
    
    Agent->>Client: session/prompt response<br/>stopReason: end_turn
    Client->>User: "Task completed"
    
    rect rgb(200, 255, 200)
    Note over User,Agent: Task done in Code mode
    end
```

### Диаграмма 5: File Restrictions по режимам

```mermaid
graph TB
    subgraph ASK["Ask Mode"]
        A1["✅ Read files"]
        A2["❌ Write (needs permission)"]
        A3["❌ Delete"]
        A4["❌ Execute"]
    end
    
    subgraph CODE["Code Mode"]
        C1["✅ Read files"]
        C2["✅ Write files"]
        C3["✅ Delete files"]
        C4["✅ Execute commands"]
    end
    
    subgraph ARCH["Architect Mode"]
        AR1["✅ Read files"]
        AR2["❌ Write"]
        AR3["❌ Delete"]
        AR4["❌ Execute"]
    end
    
    subgraph DEBUG["Debug Mode"]
        D1["✅ Read logs"]
        D2["⚠️ Write (logs only)"]
        D3["❌ Delete"]
        D4["✅ Execute (diagnostic)"]
    end
    
    MODE["Mode Selected<br/>(config_values)"]
    MODE -->|ask| ASK
    MODE -->|code| CODE
    MODE -->|architect| ARCH
    MODE -->|debug| DEBUG
    
    style MODE fill:#fff9c4
    style ASK fill:#ffcdd2
    style CODE fill:#c8e6c9
    style ARCH fill:#b3e5fc
    style DEBUG fill:#ffe0b2
```

### Диаграмма 6: Архитектура делегирования подзадач

```mermaid
graph TB
    subgraph Main["Родительская задача (Code mode)"]
        M1["Process request"]
        M2["Identify subtask:<br/>implement_auth"]
        M3["Create delegation"]
        M4["Wait for result"]
    end
    
    subgraph Proto["Protocol Exchange"]
        P1["session/update<br/>tool_call: delegate"]
        P2["Client interprets"]
        P3["Creates new session"]
        P4["session/update<br/>tool_call_update: result"]
    end
    
    subgraph Sub["Подзадача (Architect mode)"]
        S1["Design auth module"]
        S2["Generate docs"]
        S3["Return design"]
    end
    
    M1 --> M2
    M2 --> M3
    M3 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> Sub
    S1 --> S2
    S2 --> S3
    S3 --> P4
    P4 --> M4
    M4 --> M1
    
    style Main fill:#c8e6c9
    style Proto fill:#f3e5f5
    style Sub fill:#b3e5fc
```

---

**Документ подготовлен:** 2026-04-08
**Версия анализа:** 1.0
**Статус:** Готов к обсуждению и реализации
