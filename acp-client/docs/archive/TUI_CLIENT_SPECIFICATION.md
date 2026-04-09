# Техническое задание: ACP-Client TUI

## Основная информация

Этот документ является техническим заданием (ТЗ) для ACP Client TUI — терминального интерфейса для взаимодействия с ACP Server.

**Статус**: АРХИВИРОВАН (актуальная информация в [ARCHITECTURE.md](../developer-guide/ARCHITECTURE.md))

## Статус реализации (факт)

- **Функциональность**: 100% реализовано
- **Тестирование**: 85% покрыто
- **Документация**: В разработке
- **Production Ready**: Да

### 1.0 Цель

Разработать полнофункциональный терминальный интерфейс (TUI) для взаимодействия с ACP Server, который позволяет:
1. Управлять сессиями (создание, загрузка, удаление)
2. Отправлять промпты с контекстом (файлы, терминал)
3. Просматривать ответы и историю
4. Взаимодействовать с файловой системой
5. Выполнять операции в терминале
6. Управлять разрешениями

### 1.1 Область применения

acp-client работает как самостоятельное приложение:
- **OS**: macOS, Linux, Windows (эмуляция)
- **Python**: 3.12+
- **Framework**: Textual (TUI framework)
- **Транспорт**: WebSocket/TCP

### 1.2 Аудитория

1. **Разработчики**: Используют для кодирования с AI ассистентом
2. **Исследователи**: Тестирование AI моделей
3. **DevOps**: Автоматизация операций через TUI
4. **Энтузиасты**: Open-source разработка

---

## Архитектура

### Роли компонентов

#### Сервер (ACP Server) отвечает за:

1. **Протокол** — реализация ACP протокола
2. **Сессии** — управление состоянием сеансов
3. **Аутентификация** — проверка клиентов
4. **Обработка запросов** — выполнение команд (файлы, терминал)

#### Клиент (TUI) отвечает за:

1. **Интерфейс** — отображение информации пользователю
2. **Навигация** — управление компонентами и переходами
3. **Состояние** — локальное состояние UI
4. **Ввод** — обработка команд и промптов пользователя

### Коммуникационный цикл

```
User ─→ TUI Input ─→ ViewModel ─→ Use Case ─→ Transport ─→ Server
 ↑                                                              │
 └──────── Rendering ←── Observable Updates ←── Response ←────┘
```

1. Пользователь вводит команду (текст, выбор файлов)
2. TUI компонент вызывает метод ViewModel
3. ViewModel использует Use Case
4. Use Case отправляет запрос через Transport
5. Server обрабатывает и отправляет ответ
6. Observable уведомляет об изменении
7. TUI компонент перерисовывается

---

## Функциональные требования

### 3.1 Управление сессиями

#### ТР-3.1.1: Создание новой сессии

- **Input**: Название сессии, параметры
- **Action**: Отправить запрос `session/new` на сервер
- **Output**: ID новой сессии, сессия становится текущей
- **UI**: Диалог ввода названия, прогресс-бар загрузки

#### ТР-3.1.2: Загрузка существующей сессии

- **Input**: ID сессии (из списка)
- **Action**: Отправить запрос `session/load` на сервер
- **Output**: Данные сессии загруженные, история восстановлена
- **UI**: Список сессий с выбором, прогресс-бар

#### ТР-3.1.3: Список сессий

- **Input**: Фильтр (опционально)
- **Action**: Получить список с сервера
- **Output**: Отсортированный список (по дате, имени)
- **UI**: Sidebar с иконками, фильтр поиска

#### ТР-3.1.4: Переключение между сессиями

- **Input**: Выбор из списка или Alt+S
- **Action**: Сохранить текущую, загрузить новую
- **Output**: UI обновляется с новой сессией
- **UI**: Быстрое переключение без диалогов

#### ТР-3.1.5: Удаление сессии

- **Input**: Выбор + Delete
- **Action**: Подтверждение, отправить `session/delete`
- **Output**: Сессия удалена, переключение на другую
- **UI**: Диалог подтверждения, feedback об успехе

---

### 3.2 Управление промптами

#### ТР-3.2.1: Ввод промпта

- **Input**: Текст в PromptInput (многострочный)
- **Action**: Ctrl+Enter или кнопка Send
- **Output**: Промпт отправлен, история обновлена
- **UI**: Поле ввода, индикатор отправки

#### ТР-3.2.2: Отправка промпта с контекстом

- **Input**: Выбранные файлы (Space в tree), промпт
- **Action**: Отправить `session/prompt` с file paths
- **Output**: Ответ от сервера, добавлено в историю
- **UI**: Показать выбранные файлы перед отправкой

#### ТР-3.2.3: Отмена выполнения

- **Input**: Ctrl+C во время обработки
- **Action**: Отправить `session/cancel`
- **Output**: Выполнение остановлено, UI обновлён
- **UI**: Кнопка Cancel видна во время загрузки

#### ТР-3.2.4: История промптов

- **Input**: ↑/↓ в PromptInput
- **Action**: Навигация по истории
- **Output**: Предыдущий/следующий промпт в поле
- **UI**: Автоматическое восстановление

---

### 3.3 Отображение ответов

#### ТР-3.3.1: Streaming текста

- **Input**: Ответ от сервера (content блоки)
- **Action**: Отображать по мере получения
- **Output**: Текст появляется постепенно (streaming)
- **UI**: ChatView с автоматическим scroll

#### ТР-3.3.2: Tool Traces и инструменты

- **Input**: Tool calls из ответа
- **Action**: Показать в отдельной панели (ToolCallPanel)
- **Output**: Трассировка выполнения tools
- **UI**: Expandable список с параметрами

#### ТР-3.3.3: План выполнения

- **Input**: Plan из ответа (если есть)
- **Action**: Отобразить в PlanPanel
- **Output**: Визуализация плана с шагами
- **UI**: Индикаторы выполнения (░ ▒ ▓)

#### ТР-3.3.4: Сообщения разного типа

- **Input**: Content blocks разных типов
- **Action**: Рендеринг в зависимости от типа
- **Output**: Текст, код, таблицы, ссылки
- **UI**: Форматирование с цветами и стилями

---

### 3.4 Управление разрешениями

#### ТР-3.4.1: Запрос разрешения

- **Input**: Запрос от сервера (permission/request)
- **Action**: Показать модаль с деталями
- **Output**: Пользователь утверждает/отказывает
- **UI**: PermissionModal с кнопками

#### ТР-3.4.2: Политика разрешений

- **Input**: Правила (всегда, никогда, спрашивать)
- **Action**: Применить политику к типам разрешений
- **Output**: Автоматическая обработка по политике
- **UI**: Настройки разрешений

#### ТР-3.4.3: Визуализация ожидания разрешения

- **Input**: Сессия ждёт разрешение
- **Action**: Показать индикатор ожидания
- **Output**: Чат в режиме паузы, footer инфо
- **UI**: Спиннер, статус "Waiting for permission"

---

### 3.5 Взаимодействие с файловой системой

#### ТР-3.5.1: Навигация по файлам

- **Input**: Стрелки, Enter в DirectoryTree
- **Action**: Навигировать по папкам
- **Output**: Содержимое папки обновлено
- **UI**: Tree структура с иконками типов файлов

#### ТР-3.5.2: Просмотр файлов

- **Input**: Enter на файле в tree
- **Action**: Загрузить содержимое файла
- **Output**: Содержимое в FileViewer (с syntax highlight)
- **UI**: Split view или отдельная панель

#### ТР-3.5.3: Обработка fs/* RPC запросов

- **Input**: fs/list, fs/read запросы от сервера
- **Action**: Обработать локально (на клиенте)
- **Output**: Ответ отправлен на сервер
- **UI**: Кэширование, быстрая обработка

#### ТР-3.5.4: Обновление дерева при изменениях

- **Input**: События от сервера (fs/changed)
- **Action**: Обновить tree структуру
- **Output**: Tree синхронизирован с сервером
- **UI**: Минимальные обновления, scroll сохранён

---

### 3.6 Управление терминалом

#### ТР-3.6.1: Создание терминала

- **Input**: Команда от пользователя
- **Action**: Отправить `terminal/new` на сервер
- **Output**: Terminal ID, готов к выполнению команд
- **UI**: TerminalOutput компонент

#### ТР-3.6.2: Streaming вывода терминала

- **Input**: Output блоки из терминала
- **Action**: Отображать по мере получения
- **Output**: Output появляется в реальном времени
- **UI**: Auto-scroll, история хранится

#### ТР-3.6.3: Контроль процесса

- **Input**: Ctrl+C, отправка сигналов
- **Action**: Interrupt процесс, Ctrl+D для exit
- **Output**: Процесс остановлен, terminal закрыт
- **UI**: Кнопки управления в footer

#### ТР-3.6.4: История команд

- **Input**: ↑/↓ в терминале или отдельно
- **Action**: Навигация по истории команд
- **Output**: Команда вставлена в ввод
- **UI**: Встроенная история или отдельная панель

---

### 3.7 Состояние приложения

#### ТР-3.7.1: Состояние подключения

- **Input**: WebSocket events (connect, disconnect)
- **Action**: Обновить индикатор в footer
- **Output**: Статус видна пользователю
- **UI**: Иконка и текст в footer

#### ТР-3.7.2: Состояние сессии

- **Input**: Events из сессии (ready, busy, error)
- **Action**: Обновить UI в зависимости от состояния
- **Output**: Компоненты en/disabled в зависимости от состояния
- **UI**: Индикаторы и disabled состояния

#### ТР-3.7.3: Синхронизация с сервером

- **Input**: Heartbeat, session/update
- **Action**: Проверить синхронизацию
- **Output**: Оффлайн-режим если нет sync
- **UI**: Индикатор синхронизации

---

## Архитектура и дизайн

### Общая структура

Приложение строится на основе Clean Architecture с 5 слоями:

```
┌─────────────────────────────────┐
│  TUI Layer (компоненты)         │  ← Пользовательский интерфейс
├─────────────────────────────────┤
│  Presentation Layer             │  ← Observable, ViewModels
│  (состояние для UI)             │
├─────────────────────────────────┤
│  Application Layer              │  ← Use Cases, State Machine
│  (бизнес-логика)               │
├─────────────────────────────────┤
│  Infrastructure Layer           │  ← DI, Transport, Repositories
│  (внешние сервисы)             │
├─────────────────────────────────┤
│  Domain Layer                   │  ← Entities, Services, Events
│  (основные концепции)          │
└─────────────────────────────────┘
```

### Компоненты (UI элементы)

#### 4.2.1 SessionsPane

- **Функция**: Отображение и управление сессиями
- **Input**: Список сессий, фильтр поиска
- **Output**: Выбранная сессия
- **State**: Текущая сессия, список загруженных

#### 4.2.2 DirectoryTree

- **Функция**: Навигация по файлам
- **Input**: Путь, список файлов
- **Output**: Выбранный файл, путь
- **State**: Текущий путь, выбранные файлы

#### 4.2.3 ChatView

- **Функция**: История промптов и ответов
- **Input**: Сообщения из сессии
- **Output**: Выбранное сообщение, scrolling
- **State**: История, текущий scroll

#### 4.2.4 PlanPanel

- **Функция**: Отображение плана выполнения
- **Input**: План из Use Case
- **Output**: Инфо о шагах
- **State**: Текущий шаг, прогресс

#### 4.2.5 ToolCallPanel

- **Функция**: Трассировка tool calls
- **Input**: Список tool calls из ответа
- **Output**: Детали конкретного call
- **State**: Выбранный call, expanded

#### 4.2.6 PromptInput

- **Функция**: Ввод нового промпта
- **Input**: Текст пользователя, выбранные файлы
- **Output**: Промпт текст, files list
- **State**: Текущий текст, история

#### 4.2.7 PermissionModal

- **Функция**: Запрос разрешения
- **Input**: Детали разрешения
- **Output**: Approve/Deny действие
- **State**: Видна ли модаль

#### 4.2.8 FooterBar

- **Функция**: Статус, горячие клавиши, версия
- **Input**: Статус подключения, сессия
- **Output**: Справка по клавишам
- **State**: Текущий статус, помощь

---

### Services и Managers

#### 4.3.1 SessionManager

- **Функция**: Управление сессиями
- **API**: create(), load(), list(), delete(), switch()
- **Зависимости**: Transport, Repository
- **Events**: session_created, session_switched

#### 4.3.2 ACPConnectionManager

- **Функция**: Управление соединением с сервером
- **API**: connect(), disconnect(), send_message(), is_connected()
- **Зависимости**: Transport
- **Events**: connected, disconnected, error

#### 4.3.3 LocalFileSystemHandler

- **Функция**: Обработка fs/* RPC запросов
- **API**: list_files(), read_file(), write_file()
- **Зависимости**: FileSystem API
- **Events**: file_changed

#### 4.3.4 LocalTerminalHandler

- **Функция**: Обработка terminal/* RPC запросов
- **API**: exec_command(), kill(), get_output()
- **Зависимости**: Shell/Subprocess
- **Events**: output, closed

#### 4.3.5 PermissionManager

- **Функция**: Управление разрешениями
- **API**: request_permission(), set_policy(), check()
- **Зависимости**: Storage
- **Events**: permission_requested, permission_granted

---

### Обработка сообщений

#### 4.4.1 Message Handlers Pipeline

```
Message from Server
        │
        ├─→ Message Parser (parse JSON)
        │
        ├─→ Message Validator (check schema)
        │
        ├─→ Handler Router (dispatch to handler)
        │   ├─→ SessionHandler
        │   ├─→ FileSystemHandler
        │   ├─→ TerminalHandler
        │   └─→ PermissionHandler
        │
        └─→ Observable Update (notify subscribers)
```

#### 4.4.2 Update Message Routing

1. **Получить message** из Transport
2. **Распарсить** JSON
3. **Определить тип** (response, error, update)
4. **Выбрать handler** в зависимости от типа
5. **Обработать** (обновить состояние)
6. **Уведомить** Observable (for UI refresh)

---

## UI/UX Спецификация

### 5.1 Макет интерфейса

```
┌─────────────────────────────────────────────────────┐
│ acp-client v0.2.0 | Connected | Session: project-1 │ Header
├──────────────┬────────────────────────────────────┤
│              │                                    │
│  Sessions    │           Chat View                │
│  (sidebar)   │  (промпты и ответы)               │
│              │                                    │
│  • project-1 │  > Analyze this code               │
│  • work-2    │                                    │
│              │  AI: Here's the analysis...        │
│  Files       │  - Function A does X              │
│  (tree)      │  - Function B does Y              │
│              │                                    │
│  ├─ src/     │  Plan:                            │
│  │ ├─ main.py│  [▓▓░░░░░░] Step 1 (2/5)        │
│  │ └─ utils │                                    │
│  └─ tests/   │  Files in context:                │
│              │  • main.py (45 lines)             │
│              │  • utils.py (23 lines)            │
├──────────────┼────────────────────────────────────┤
│ Type prompt> │ [Ctrl+Enter: Send] [Files: 2]    │ Input
├──────────────┴────────────────────────────────────┤
│ F1: Help | ?: Hotkeys | Connected | Ready        │ Footer
└─────────────────────────────────────────────────────┘
```

### 5.2 Цветовая схема

**Светлая тема**:
- Background: #FFFFFF
- Text: #000000
- Accent: #0066CC
- Success: #009900
- Error: #CC0000
- Warning: #FF6600

**Тёмная тема** (по умолчанию):
- Background: #1E1E1E
- Text: #E0E0E0
- Accent: #0099FF
- Success: #00CC00
- Error: #FF3333
- Warning: #FFAA00

### 5.3 Иконки и символы

| Символ | Значение |
|--------|----------|
| 📁 | Папка |
| 📄 | Файл |
| 🔒 | Защищённо |
| ✓ | Успех |
| ✗ | Ошибка |
| ⟳ | Загрузка |
| ▶ | Expandable |
| ▼ | Collapsed |

### 5.4 Горячие клавиши

| Комбинация | Действие |
|-----------|----------|
| Ctrl+Enter | Отправить промпт |
| Shift+Enter | Новая строка |
| Alt+S | Переключить сессию |
| Ctrl+N | Новая сессия |
| Ctrl+D | Удалить сессию |
| Space | Toggle файл в контексте |
| Enter | Открыть файл |
| ? | Список клавиш |
| F1 | Справка |
| Ctrl+C | Cancel текущую операцию |
| Ctrl+Q | Выход |

---

## Примеры использования

### 6.1 Сеанс инициализации

1. Пользователь запускает `python -m acp_client.tui`
2. TUI приложение загружается (DIBootstrapper инициализирует)
3. Выполняется `InitializeUseCase` — подключение к серверу
4. Список сессий загружается из сервера
5. Последняя сессия загружается автоматически (если есть)
6. UI готов к взаимодействию

**Flow**:
```
User starts app
    ↓
DIBootstrapper initializes (DI container)
    ↓
ACPConnectionManager.connect()
    ↓
InitializeUseCase.execute()
    ↓
ListSessionsUseCase.execute()
    ↓
LoadSessionUseCase.execute(last_session_id)
    ↓
UI renders with loaded data
```

### 6.2 Поток session/update

1. Пользователь отправляет промпт (Ctrl+Enter)
2. PromptInput.on_send() вызывает ChatViewModel.send_prompt()
3. Use Case отправляет message через Transport
4. Server обрабатывает и отправляет события
5. Message Handler обновляет Observable
6. ChatView перерисовывается автоматически

**Flow**:
```
User presses Ctrl+Enter
    ↓
PromptInput emits "message_sent" event
    ↓
ChatViewModel.send_prompt(text)
    ↓
SendPromptUseCase.execute(request)
    ↓
Transport.send_message(request)
    ↓
Server processes, sends response
    ↓
Message Handler updates Observable (messages)
    ↓
ChatView detects change, rerenders
```

### 6.3 Обработка tool calls и fs/terminal

1. Server отправляет tool_call в ответе
2. Message Handler передаёт ToolCallPanel
3. ToolCallPanel отображает детали
4. Client выполняет локально (fs/read, terminal exec)
5. Результат отправляется на сервер

**Flow**:
```
Server sends tool_call
    ↓
ToolHandler detects it
    ↓
FileSystemHandler.read_file() or TerminalHandler.exec()
    ↓
Result cached locally
    ↓
Response sent back to server
    ↓
ToolCallPanel updates (shows result)
```

### 6.4 Обработка ошибок

**Сценарий 1: Ошибка подключения**
- ConnectionManager.connect() выбрасывает исключение
- UIViewModel.connection_error.set(error_message)
- Footer обновляется красным "Disconnected"

**Сценарий 2: Ошибка Use Case**
- Use Case выбрасывает исключение
- ChatViewModel ловит и обновляет error Observable
- ChatView показывает красное сообщение об ошибке

**Сценарий 3: Server error в ответе**
- Message Parser видит "error" поле
- ErrorHandler обновляет error Observable
- UI показывает ошибку пользователю

---

## Требования к производительности и качеству

### 7.1 Производительность

| Метрика | Целевое значение |
|---------|-----------------|
| Startup time | < 2 сек |
| Prompt latency | < 500 мс (UI response) |
| Chat render (100 msgs) | < 100 мс |
| Memory usage | < 100 MB |
| FPS | 30+ (при анимациях) |

### 7.2 Потребление памяти

- Chat history: максимум 10 MB (ограничить размер буфера)
- File tree: зависит от размера проекта (кэшировать)
- Observable subscriptions: автоматически очищать при dispose

### 7.3 UX требования

- **Responsiveness**: UI должен откликаться на ввод < 100 мс
- **Feedback**: Пользователь видит что происходит (loading, error)
- **Shortcuts**: Горячие клавиши для частых операций
- **History**: Запоминать историю сессий и команд

---

## Требования к окружению

### 8.1 Поддерживаемые платформы

- macOS 10.15+
- Linux (Ubuntu 20.04+, Fedora 34+)
- Windows 10+ (с WSL или MobaXTerm)

### 8.2 Зависимости платформы

**macOS**:
- Homebrew (для установки Python и зависимостей)

**Linux**:
- apt-get / yum (для Python и зависимостей)

**Windows**:
- WSL2 или эмулятор терминала

---

## Тестирование

### 9.1 Unit-тесты

- **Слой**: Domain, Application, Presentation
- **Coverage**: 80%+
- **Framework**: pytest

### 9.2 Integration-тесты

- **Тесты**: Use Cases + Mock Transport
- **Тесты**: ViewModels + Observable
- **Тесты**: Message handlers

### 9.3 E2E-тесты

- **Тесты**: Full flow (UI → Server → Response)
- **Framework**: textual test framework
- **Coverage**: Критичные пути

---

## Deployment

### 10.1 Distribution

- **PyPI**: pip install acp-client
- **GitHub**: Releases со встроенным интерпретатором Python
- **Docker**: Docker image с TUI

### 10.2 Конфигурация

```yaml
# ~/.config/acp-client/config.yaml
server:
  host: localhost
  port: 8000
  ssl: false

ui:
  theme: dark
  font_size: 12
  language: en

permissions:
  file_write: ask
  terminal_exec: ask
  
history:
  max_items: 100
  persist: true
```

### 10.3 Логирование

- **Level**: INFO (production), DEBUG (development)
- **Output**: ~/.local/share/acp-client/logs/
- **Rotation**: Daily, 7 дней retention

---

## Расширяемость

### 11.1 Переиспользование компонентов

Компоненты разработаны для переиспользования:
- `Observable[T]` — generic реактивный тип
- `BaseViewModel` — базовый класс для всех ViewModels
- `UseCase` — интерфейс для бизнес-логики

### 11.2 Компоненты, добавляемые в acp-client для TUI

1. **Presentation Layer**: Observable, ViewModels
2. **TUI Layer**: Textual компоненты
3. **Managers**: SessionManager, ConnectionManager
4. **Handlers**: FileSystemHandler, TerminalHandler

### 11.3 Архитектура расширения

**Plugin система** (в future):
```python
class Plugin(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass
    
    @abstractmethod
    async def handle_message(self, msg: Message) -> Optional[Message]:
        pass
```

---

## Документация и справка

### 12.1 Структура документов

- `README.md` — обзор и быстрый старт
- `DEVELOPING.md` — разработка и расширение
- `TESTING.md` — тестирование
- `ARCHITECTURE.md` — архитектура (5 слоев)

### 12.2 Встроенная справка

- `F1` — справка по текущему компоненту
- `?` — список горячих клавиш
- `/help` — справка по командам
- `Tutorial` — интерактивный тур для новичков

---

## Ограничения и будущие версии

### 13.1 MVP 1.0 Ограничения

- Одно соединение на приложение (не поддерживается 2+ серверов)
- Максимум 1000 сообщений в истории (более старые удаляются)
- Встроенная справка на английском только
- Плагины не поддерживаются (в v1.1+)

### 13.2 Future Features (v1.1+)

1. **Multi-Server Support** — одновременное подключение к 2+ серверам
2. **Plugin System** — добавлять custom компоненты и handlers
3. **Themes & Customization** — создавать собственные темы
4. **Advanced Search** — полнотекстовый поиск по истории
5. **Session Export/Import** — сохранение и восстановление из файла
6. **Local LLM Integration** — вызов локальных моделей
7. **Voice Input** — голосовой ввод команд
8. **Mobile Client** — мобильный клиент (iOS/Android)

---

## Приложения

### A.1 Initialize

**Запрос**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocol_version": "1.0.0"
  }
}
```

**Ответ**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "capabilities": [
      "session/new",
      "session/load",
      "session/prompt",
      "fs/*",
      "terminal/*"
    ]
  }
}
```

---

**Примечание**: Этот документ архивирован. Актуальная информация о клиентской архитектуре находится в [ARCHITECTURE.md](../developer-guide/ARCHITECTURE.md) и [DEVELOPING.md](../developer-guide/DEVELOPING.md).
