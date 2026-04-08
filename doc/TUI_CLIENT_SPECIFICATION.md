# Техническое задание: ACP-Client TUI

**Статус документа:** Архитектурное проектирование  
**Версия:** 1.0  
**Дата:** 2026-04-08  
**Язык:** Русский

---

## 1. Обзор проекта

### 1.1 Цель

Разработать полнофункциональный TUI (Text User Interface) клиент для взаимодействия с ACP-протоколом (Agent Client Protocol) на базе фреймворка Textual. Клиент должен предоставлять интерактивный интерфейс для управления сессиями агента, отправки промптов, отслеживания выполнения инструментов и управления локальными ресурсами (файлы, терминал).

### 1.2 Область применения

- Интерактивное взаимодействие с AI-агентом через терминал
- Управление файлами проекта
- Выполнение команд в терминале под контролем агента
- Отслеживание хода выполнения операций в реальном времени
- Управление разрешениями для критических операций

### 1.3 Аудитория

- Разработчики, работающие из терминала
- DevOps инженеры
- Data Scientists
- Системные администраторы

---

## 2. Архитектура клиент-сервер

### 2.1 Разделение ответственности

#### Сервер (ACP Server) отвечает за:
- **Управление сессиями**: создание, загрузка, удаление сессий
- **Взаимодействие с LLM**: отправка промптов в нейросеть, получение ответов
- **Обработка инструментов**: интерпретация tool calls от LLM
- **Состояние разговора**: поддержание истории и контекста
- **MCP интеграция**: управление Model Context Protocol серверами

#### Клиент (TUI) отвечает за:
- **Работа с локальной файловой системой**: чтение, запись, навигация по файлам
- **Управление терминалом**: создание, выполнение команд, перехват вывода
- **Пользовательский интерфейс**: визуализация, взаимодействие с пользователем
- **Отправка промптов**: формирование запросов к серверу
- **Обработка разрешений**: запросы пользователя на выполнение критических операций
- **Кэширование и синхронизация**: локальное состояние сессий и истории

### 2.2 Коммуникационный цикл

```
Действие пользователя
    ↓
Обработка в TUI
    ↓
JSON-RPC сообщение (WebSocket)
    ↓
ACP Server
    ↓
Обработка LLM
    ↓
session/update уведомления
    ↓
Рендеринг в TUI
    ↓
Пользователь видит ответ
```

---

## 3. Функциональные требования

### 3.1 Управление сессиями

#### ТР-3.1.1: Создание новой сессии
- Клиент может создать новую сессию через `session/new`
- Указание рабочей директории (cwd) для контекста агента
- Получение уникального sessionId для последующих операций
- Отображение новой сессии в списке

#### ТР-3.1.2: Загрузка существующей сессии
- Поддержка `session/load` для возобновления разговора
- Проверка capability `loadSession` на сервере
- Воспроизведение истории из `session/update` уведомлений
- Восстановление контекста и состояния

#### ТР-3.1.3: Список сессий
- Получение списка всех доступных сессий через `session/list`
- Отображение в боковой панели с информацией:
  - ID сессии
  - Заголовок/название
  - Дата последнего обновления
  - Статус (активная, в процессе, завершена)

#### ТР-3.1.4: Переключение между сессиями
- Быстрое переключение между открытыми сессиями
- Сохранение скролл-позиции и состояния каждой сессии
- Подсвечивание активной сессии

#### ТР-3.1.5: Удаление сессии
- Возможность удалить сессию (если поддерживается сервером)
- Подтверждение перед удалением

### 3.2 Отправка промптов и управление разговором

#### ТР-3.2.1: Ввод промпта
- Многострочное поле ввода в footer панели
- Поддержка Markdown синтаксиса
- Авто-завершение на основе истории

#### ТР-3.2.2: Отправка промпта с контекстом
- `session/prompt` с поддержкой текстового контента
- Возможность вложить текущий файл как контекст (ContentBlock::Resource)
- Отправка файлов и изображений (если поддерживаются)
- Индикатор отправки

#### ТР-3.2.3: Отмена выполнения
- Горячая клавиша Ctrl+C для `session/cancel` уведомления
- Визуальная индикация отмены
- Остановка стриминга текста

#### ТР-3.2.4: История промптов
- Сохранение истории всех промптов в сессии
- Возможность просмотра истории
- Перезагрузка предыдущего промпта (↑/↓ в поле ввода)

### 3.3 Визуализация ответов агента

#### ТР-3.3.1: Streaming текста
- Посимвольный вывод текста от агента с минимальной задержкой
- Поддержка Markdown рендеринга в Rich
- Синтаксис-подсветка для кода (python, bash, json и т.д.)

#### ТР-3.3.2: Tool Traces и инструменты
- Визуализация tool calls с иконками (читать, писать, выполнять и т.д.)
- Статусы: pending, in_progress, completed, failed
- Раскрываемые блоки с деталями инструмента
- Отображение input/output для инструментов

#### ТР-3.3.3: План выполнения
- Отображение `plan` обновлений в отдельной секции
- Пункты плана с приоритетом и статусом
- Отметка выполненных пунктов по мере хода работы

#### ТР-3.3.4: Сообщения разного типа
- **user_message**: выравнивание справа, серый фон
- **agent_message**: выравнивание слева, белый фон
- **tool_call**: индикатор выполнения с иконкой
- **error**: красное оформление с символом ⚠️

### 3.4 Управление разрешениями (Human-in-the-loop)

#### ТР-3.4.1: Запрос разрешения
- Модальное окно с описанием операции
- Список доступных вариантов (Allow, Reject, Allow Always и т.д.)
- Отправка `session/request_permission` ответа с выбором

#### ТР-3.4.2: Политика разрешений
- Сохранение решений пользователя (Allow Always)
- Автоматическое применение политики для повторных запросов
- Возможность сброса политики в настройках

#### ТР-3.4.3: Визуализация ожидания разрешения
- Изменение статуса tool call на "waiting_for_permission"
- Выделение модального окна для привлечения внимания

### 3.5 Интеграция файловой системы

#### ТР-3.5.1: Навигация по файлам
- DirectoryTree виджет в левой панели
- Отображение структуры директорий проекта
- Фильтрация скрытых файлов и .gitignore

#### ТР-3.5.2: Просмотр файлов
- Двойной клик на файл → открыть в читаемой форме
- Синтаксис-подсветка кода
- Номера строк
- Поиск в файле (Ctrl+F)

#### ТР-3.5.3: Обработка fs/* RPC запросов
- Реализация обработчиков:
  - `fs/read_text_file` → прочитать файл на клиенте
  - `fs/write_text_file` → записать файл на клиенте
- Валидация путей (абсолютные пути)
- Обработка ошибок (файл не найден и т.д.)

#### ТР-3.5.4: Обновление дерева при изменениях
- Если агент создал/изменил файл → обновить дерево
- Визуальный индикатор новых/модифицированных файлов

### 3.6 Интеграция терминала

#### ТР-3.6.1: Создание терминала
- `terminal/create` запрос с командой
- Отображение ID терминала в tool call
- Встроенный вывод в tool call контейнер

#### ТР-3.6.2: Streaming вывода терминала
- Real-time обновление вывода по мере выполнения команды
- Анси-цвета в выводе (через Rich.ANSI)
- Поддержка вывода > 1 МБ (truncation)

#### ТР-3.6.3: Контроль процесса
- `terminal/kill` для остановки команды
- `terminal/wait_for_exit` для ожидания завершения
- `terminal/release` для освобождения ресурса
- Отображение exit code

#### ТР-3.6.4: История команд
- Сохранение всех выполненных команд
- Возможность просмотра полного вывода

### 3.7 Управление состоянием

#### ТР-3.7.1: Состояние подключения
- Индикатор соединения в footer (Connected/Connecting/Disconnected)
- Автопереподключение при разрыве соединения
- Очередь сообщений при отсутствии соединения

#### ТР-3.7.2: Состояние сессии
- Активная сессия (в footer)
- Статус выполнения (ожидание ввода, обработка, выполнение)
- Счетчик сообщений в текущей сессии

#### ТР-3.7.3: Синхронизация с сервером
- Локальное кэширование истории
- Восстановление при перезагрузке клиента
- Разрешение конфликтов (сервер ≠ локальный кэш)

---

## 4. Архитектура компонентов TUI

### 4.1 Общая структура

```
ACPClientApp (Main App)
├── HeaderBar
├── Body (Container)
│   ├── Sidebar (Left)
│   │   ├── SessionsPane (список сессий)
│   │   └── FileTree (дерево файлов)
│   └── MainArea (Right)
│       ├── ChatView (ScrollableContainer)
│       │   ├── MessageContainer (история сообщений)
│       │   ├── PlanPanel (опционально)
│       │   └── ToolCallsPanel (tool traces)
│       └── PermissionModal (Modal overlay)
├── FooterBar (Bottom)
│   ├── StatusBar (left side)
│   ├── PromptInput (center/right)
│   └── ShortcutsHint (right side)
└── ConnectionManager (background)
```

### 4.2 Ключевые компоненты

#### 4.2.1 SessionsPane
- Список всех сессий
- Кнопка "+ New Session"
- Фокус на активную сессию
- Обработка `session/list` результатов

#### 4.2.2 DirectoryTree
- Навигация по структуре проекта
- Кэширование вывода дерева
- Фильтрация по gitignore
- Синхронизация при изменениях от агента

#### 4.2.3 ChatView
- Скроллируемый контейнер с историей
- Динамическое добавление сообщений по мере streaming
- Отображение user_message и agent_message блоков
- Tool call визуализация

#### 4.2.4 PlanPanel
- Отображение списка пунктов плана
- Обновление статусов при выполнении
- Визуальный прогресс выполнения

#### 4.2.5 ToolCallPanel
- Отображение одного инструмента
- Раскрываемый контент (input/output)
- Иконки статусов (⏳, ⚙️, ✓, ⚠️)
- Динамическое обновление при tool_call_update

#### 4.2.6 PromptInput
- Многострочное поле для ввода промпта
- Ctrl+Enter для отправки
- History navigation (↑/↓)
- Обработка `session/prompt` запроса

#### 4.2.7 PermissionModal
- Запрос разрешения для операции
- Список вариантов ответа
- Отправка решения на сервер

#### 4.2.8 FooterBar
- Статус соединения (Connected/Connecting/Error)
- Текущая сессия (ID и название)
- Режим выполнения (idle/processing)
- Подсказки по горячим клавишам

### 4.3 Менеджеры состояния (базирующиеся на acp-client)

#### 4.3.1 SessionManager
```python
class SessionManager:
    """Управление сессиями на основе ACPClient."""
    
    async def create_session(self, cwd: str) -> str:
        """Создать сессию через session/new."""
        pass
    
    async def load_session(self, session_id: str):
        """Загрузить сессию через session/load."""
        pass
    
    async def list_sessions(self) -> list:
        """Получить список сессий через session/list."""
        pass
```

#### 4.3.2 ACPConnectionManager
```python
class ACPConnectionManager:
    """Управление WebSocket соединением с сервером."""
    
    async def connect(self, host: str, port: int):
        """Подключиться к серверу."""
        pass
    
    async def initialize(self):
        """Выполнить initialize handshake."""
        pass
    
    async def send_prompt(self, session_id: str, content: list):
        """Отправить session/prompt."""
        pass
    
    async def handle_updates(self, callback):
        """Получать session/update уведомления."""
        pass
```

#### 4.3.3 LocalFileSystemHandler
```python
class LocalFileSystemHandler:
    """Обработка fs/* запросов от сервера."""
    
    async def read_file(self, path: str, line: int = None, limit: int = None) -> str:
        """Реализация fs/read_text_file (из acp-client/handlers/filesystem.py)."""
        pass
    
    async def write_file(self, path: str, content: str):
        """Реализация fs/write_text_file."""
        pass
```

#### 4.3.4 LocalTerminalHandler
```python
class LocalTerminalHandler:
    """Обработка terminal/* запросов от сервера."""
    
    async def create_terminal(self, command: str, args: list, cwd: str) -> str:
        """Создать терминал и вернуть ID."""
        pass
    
    async def get_output(self, terminal_id: str) -> tuple[str, bool, int]:
        """Получить вывод (из acp-client/handlers/terminal.py)."""
        pass
    
    async def wait_for_exit(self, terminal_id: str) -> tuple:
        """Ждать выхода процесса."""
        pass
```

#### 4.3.5 PermissionManager
```python
class PermissionManager:
    """Управление разрешениями пользователя."""
    
    async def request_permission(self, request: dict) -> dict:
        """Показать модальное окно и получить решение."""
        pass
    
    def save_permission_policy(self, kind: str, outcome: str):
        """Сохранить решение для повторного использования."""
        pass
```

### 4.4 Обработка сообщений

#### 4.4.1 Message Handlers Pipeline

Использует существующие handlers из acp-client:
- `FileSystemHandler` - для fs/* запросов
- `TerminalHandler` - для terminal/* запросов
- `PermissionHandler` - для session/request_permission

#### 4.4.2 Update Message Routing

```
session/update полученно
    ↓
Извлечь sessionUpdate тип
    ↓
Switch на тип:
    - agent_message_chunk → добавить в ChatView, streaming
    - user_message_chunk → добавить в ChatView
    - tool_call → создать ToolCallPanel
    - tool_call_update → обновить ToolCallPanel статус
    - plan → обновить PlanPanel
    - available_commands_update → обновить slash команды
    - ...
```

---

## 5. Спецификация UI/UX

### 5.1 Макет интерфейса

```
┌─────────────────────────────────────────────────────────────┐
│ ACP-Client v1.0                    Connected · Session: s_1 │
├─────────────────────┬──────────────────────────────────────┤
│  Сессии             │                                       │
│  ───────────        │          История чата                │
│  [+] Новая          │  ┌─────────────────────────────────┐ │
│                     │  │ User: Проанализируй этот код    │ │
│  [✓] Сессия 1       │  │ 2026-04-08 14:30:45             │ │
│      (активна)      │  └─────────────────────────────────┘ │
│                     │                                       │
│  [ ] Сессия 2       │  ┌─────────────────────────────────┐ │
│  [ ] Сессия 3       │  │ План:                           │ │
│                     │  │ ✓ Распарсить структуру кода     │ │
│  Файлы              │  │ ⏳ Анализировать паттерны       │ │
│  ──────────         │  │ ○ Генерировать рекомендации     │ │
│  ▼ project          │  └─────────────────────────────────┘ │
│    ▼ src            │                                       │
│      • main.py      │  ┌─────────────────────────────────┐ │
│      • utils.py     │  │ 🔍 Чтение файла: main.py        │ │
│    • config.json    │  │ Статус: выполняется             │ │
│    • README.md      │  └─────────────────────────────────┘ │
│                     │                                       │
│  Поиск: [______]    │  ┌─────────────────────────────────┐ │
│                     │  │ Я проанализирую код на наличие  │ │
│                     │  │ потенциальных проблем...        │ │
│                     │  └─────────────────────────────────┘ │
├─────────────────────┴──────────────────────────────────────┤
│ Промпт: [Напиши сообщение... (Ctrl+Enter для отправки)   ] │
│ Статус: Connected · Ready · Ctrl+N=Новая · Ctrl+L=Очистить
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Цветовая схема

**Светлая тема (default):**
- Background: White (#FFFFFF)
- Text: Black (#000000)
- Sidebar: Light gray (#F5F5F5)
- Accents: Blue (#0066CC)
- Success: Green (#00AA00)
- Warning: Orange (#FF9900)
- Error: Red (#CC0000)

**Темная тема (optional):**
- Background: Dark gray (#1E1E1E)
- Text: Light gray (#E0E0E0)
- Sidebar: Dark gray (#2D2D2D)
- Accents: Light blue (#66B2FF)
- Success: Light green (#66FF66)
- Warning: Light orange (#FFCC66)
- Error: Light red (#FF6666)

### 5.3 Иконки и символы

| Элемент | Иконка | Описание |
|---------|--------|---------|
| Чтение файла | 📖 | fs/read_text_file |
| Запись файла | ✍️ | fs/write_text_file |
| Удаление файла | 🗑️ | Удаление файла |
| Терминал | 💻 | terminal/* операции |
| Tool ожидание | ⏳ | Инструмент в ожидании |
| Tool выполнение | ⚙️ | Инструмент выполняется |
| Tool завершен | ✓ | Инструмент завершен |
| Tool ошибка | ⚠️ | Ошибка в инструменте |
| Ждет разрешения | 🔒 | Ожидание разрешения |
| Соединено | ● | Соединение активно |
| Подключение | ◐ | Подключение... |
| Отключено | ○ | Соединение разорвано |

### 5.4 Горячие клавиши

| Комбинация | Действие |
|-----------|----------|
| `Ctrl+N` | Новая сессия |
| `Ctrl+S` | Фокус на список сессий |
| `Ctrl+L` | Очистить чат |
| `Ctrl+C` | Отмена выполнения (cancel) |
| `Tab` | Переключение между панелями |
| `Enter` | В PromptInput: перевод строки |
| `Ctrl+Enter` | В PromptInput: отправка |
| `↑/↓` | В PromptInput: навигация по истории |
| `Esc` | Закрыть модальное окно |
| `Ctrl+Q` | Выход |

---

## 6. Интеграция с ACP-протоколом

### 6.1 Сеанс инициализации

**Шаг 1: Initialize (из acp-client.client.ACPClient.initialize)**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "clientCapabilities": {
      "fs": {
        "readTextFile": true,
        "writeTextFile": true
      },
      "terminal": true
    },
    "clientInfo": {
      "name": "acp-client-tui",
      "title": "ACP-Client TUI",
      "version": "1.0.0"
    }
  }
}
```

**Шаг 2: Create Session (из acp-client.helpers.session)**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "session/new",
  "params": {
    "cwd": "/home/user/project",
    "mcpServers": []
  }
}
```

**Шаг 3: Prompt Loop (из acp-client.client.ACPClient.request)**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "session/prompt",
  "params": {
    "sessionId": "sess_xyz123",
    "prompt": [
      {
        "type": "text",
        "text": "Пользовательское сообщение"
      }
    ]
  }
}
```

### 6.2 Поток session/update

```
Получено session/update уведомление
    ↓
Распарсить sessionUpdate тип (из acp-client.messages)
    ↓
Маршрутизировать на обработчик:
    - agent_message_chunk: добавить в чат с streaming
    - tool_call: создать tool panel с иконкой
    - tool_call_update: обновить tool panel статус
    - plan: отобразить пункты плана
    - error: показать сообщение об ошибке
    - ...
    ↓
Обновить UI реактивно
    ↓
Если streaming: продолжить принимать chunks
    ↓
Если final response: закрыть indicator прогресса
```

### 6.3 Обработка tool calls и fs/terminal

**Tool Call Sequence:**
```
1. Получено tool_call update со статусом: pending
2. Отобразить tool panel
3. Если tool требует fs/* или terminal/*:
   - Отправить RPC запрос от клиента
   - Получить response с данными
   - Использовать данные для завершения операции
4. Получено tool_call_update со статусом: in_progress
5. Streamen контент в tool panel
6. Получено tool_call_update со статусом: completed
7. Отметить tool как завершено
```

**Permission Request (из acp-client.handlers.permissions):**
```
1. Получено session/request_permission метод
2. Распарсить toolCall и options
3. Показать PermissionModal с вариантами
4. Пользователь выбирает вариант
5. Отправить response: {outcome: {outcome: "selected", optionId: ...}}
6. Tool продолжает выполнение
```

### 6.4 Обработка ошибок

**Стратегия обработки:**

| Тип ошибки | Действие |
|-----------|----------|
| JSON-RPC Parse Error | Логировать, показать generic error toast |
| Method not found (-32601) | Feature not supported warning |
| Invalid params (-32602) | Логировать validation error, retry или skip |
| Server error (-32000 to -32099) | Показать error popup с деталями |
| Network error | Переподключиться с backoff, очередь сообщений |
| Permission denied | Показать user-friendly сообщение |

---

## 7. Требования к производительности и UX

### 7.1 Производительность

| Метрика | Требование |
|---------|-----------|
| Время отклика на ввод | < 100 мс |
| Rendering text chunk | < 50 мс |
| File tree load | < 500 мс (для 1000+ файлов) |
| Terminal output update | < 100 мс per chunk |
| Session switch | < 200 мс |
| UI responsiveness | 60 FPS (где возможно) |

### 7.2 Потребление памяти

- История чата: max 10 MB (прокрутка при переполнении)
- Кэш файлов: max 50 MB
- Terminal buffers: max 100 MB total
- Background processes: < 100 MB

### 7.3 UX требования

- **Ощущение реальности**: Streaming текста без заметных пауз
- **Контроль**: Пользователь может отменить операцию (Ctrl+C)
- **Видимость**: Статус всегда показан в footer
- **Обратная связь**: Каждое действие имеет визуальный отклик
- **Accessibility**: Support для высокого контраста

---

## 8. Кросс-платформность

### 8.1 Поддерживаемые платформы

- **Linux** (Ubuntu 20.04+, Debian 11+)
- **macOS** (10.14+)
- **Windows** (WSL2, native через pyreadline)

### 8.2 Зависимости платформы

- POSIX терминал (PTY) - Linux/macOS
- Windows: subprocess (без PTY)
- WebSocket: работает на всех платформах

---

## 9. Тестирование

### 9.1 Unit-тесты

- Парсинг ACP сообщений (использовать acp-client.messages)
- Валидация путей файлов
- Обработчики сообщений
- Менеджеры состояния

### 9.2 Integration-тесты

- Полный цикл: prompt → session/update → UI update
- Tool call execution with fs/terminal
- Permission request flow
- Session switching and loading

### 9.3 E2E-тесты

- Interaction с реальным ACP сервером
- Manual UI testing scenarios
- Performance benchmarks

---

## 10. Развертывание и инфраструктура

### 10.1 Distribution

- PyPI пакет: `acp-client-tui` (или расширение acp-client)
- Требования: Python 3.11+
- Установка: `pip install acp-client-tui`

### 10.2 Конфигурация

**Файл `~/.acp-client/config.toml`:**
```toml
[server]
host = "127.0.0.1"
port = 8765
auto_connect = true

[ui]
theme = "dark"
font_size = 12

[permissions]
auto_approve_kinds = []
auto_reject_kinds = []
```

### 10.3 Логирование

- Уровень: DEBUG, INFO, WARNING, ERROR
- Вывод: файл + консоль (optional)
- Формат: JSON для parsing (использовать acp-client.logging)

---

## 11. Интеграция с существующим acp-client

### 11.1 Переиспользование компонентов

- **ACPClient** - базовый класс для WebSocket коммуникации
- **Messages** - парсинг JSON-RPC сообщений
- **Handlers** - fs, terminal, permissions
- **Helpers** - session, auth операции
- **Transport** - WebSocket транспорт

### 11.2 Новые компоненты для TUI

- **Textual Components** - UI виджеты
- **ChatView** - визуализация сообщений
- **ToolCallPanel** - отображение инструментов
- **SessionManager** - управление сессиями (над ACPClient)
- **UIStateMachine** - управление состоянием UI

### 11.3 Архитектура расширения

```
acp-client/
├── src/acp_client/
│   ├── ... (существующий код)
│   ├── tui/                    # Новый модуль TUI
│   │   ├── __init__.py
│   │   ├── app.py              # Main Textual app
│   │   ├── components/         # Textual компоненты
│   │   │   ├── header.py
│   │   │   ├── sidebar.py
│   │   │   ├── chat_view.py
│   │   │   ├── prompt_input.py
│   │   │   ├── footer.py
│   │   │   └── ...
│   │   ├── managers/           # State managers
│   │   │   ├── session.py
│   │   │   ├── connection.py
│   │   │   ├── filesystem.py
│   │   │   ├── terminal.py
│   │   │   └── permission.py
│   │   └── styles/             # Textual CSS
│   │       └── app.tcss
│   ├── cli.py                  # Обновить для TUI
│   └── ...
```

---

## 12. Документация для пользователя

### 12.1 Структура документов

- `acp-client/README.md` - Обновить с информацией о TUI
- `acp-client/TUI.md` - Руководство по TUI клиенту
- `acp-client/HOTKEYS.md` - Справочник горячих клавиш
- `acp-client/TROUBLESHOOTING.md` - Решение проблем
- `DEVELOPMENT.md` - Для контрибьюторов

### 12.2 Встроенная справка

- Help modal (Ctrl+H)
- Tooltips для кнопок
- Подсказки в footer

---

## 13. Известные ограничения и future work

### 13.1 MVP 1.0 Ограничения

- Нет embedded images в чате (только текст)
- Нет audio support
- Нет multi-session parallelization
- Basic syntax highlighting (python, bash, json)
- No custom CSS theming

### 13.2 Future Features (v1.1+)

- Image attachment support
- Custom theme editor
- Plugin system
- Collaborative sessions
- Advanced search in history
- Code generation and insertion
- Branching conversations

---

## Приложение A: Примеры JSON-RPC сообщений

### A.1 Initialize

```json
Request:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "clientCapabilities": {
      "fs": {"readTextFile": true, "writeTextFile": true},
      "terminal": true
    },
    "clientInfo": {
      "name": "acp-client-tui",
      "title": "ACP-Client TUI",
      "version": "1.0.0"
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": 1,
    "agentCapabilities": {
      "loadSession": true,
      "promptCapabilities": {"image": false, "audio": false},
      "mcpCapabilities": {"http": true}
    },
    "agentInfo": {
      "name": "acp-agent",
      "title": "ACP Agent",
      "version": "1.0.0"
    },
    "authMethods": []
  }
}
```

---

**Конец документа TUI_CLIENT_SPECIFICATION.md**
