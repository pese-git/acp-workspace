# План улучшения UI/UX в acp-client

## Содержание

1. [Текущее состояние](#текущее-состояние)
2. [Анализ конкурентов и best practices](#анализ-конкурентов-и-best-practices)
3. [Фазы улучшения](#фазы-улучшения)
4. [Метрики успеха и измерение](#метрики-успеха-и-измерение)
5. [Риски и смягчение](#риски-и-смягчение)
6. [Приложения](#приложения)

---

## Текущее состояние

### Краткое резюме текущего состояния

**acp-client** — это TUI приложение для взаимодействия с ACP Server. Текущее состояние:

- ✅ **Функциональность**: Все ключевые функции реализованы (сессии, промпты, файлы, терминал)
- ⚠️ **UI/UX**: Интерфейс функционален но требует улучшений для лучшего UX
- ✅ **Архитектура**: Clean Architecture (5 слоёв) хорошо структурирована
- ⚠️ **Читаемость**: Много информации на экране, иерархия не очевидна

### Ключевые проблемы

1. **Информационная перегруженность** — слишком много элементов на экране одновременно
2. **Плохая иерархия** — не ясно что главное, что вспомогательное
3. **Отсутствие feedback** — пользователь не всегда понимает что происходит
4. **Неудобная навигация** — быстрая смена контекста требует многих клавиш
5. **Нет встроенной помощи** — новичку сложно разобраться
6. **Мало состояний** — не ясны состояния подключения, загрузки, ошибок

### Главные рекомендации

Основываясь на анализе конкурентов и принципах TUI дизайна:

1. **Упростить информационную архитектуру** (убрать второстепенное из viewport)
2. **Добавить интерактивный help** (F1, ?, контекстная справка)
3. **Реализовать контекстные меню** (Ctrl+/ для команд)
4. **Улучшить состояния UI** (явные индикаторы загрузки, ошибок)
5. **Добавить undo/redo** (для операций с файлами, сессиями)
6. **Поиск и фильтрация** (быстрый доступ к сессиям, файлам)
7. **Кастомизация интерфейса** (темы, раскладки, сочетания клавиш)

---

## Анализ конкурентов и best practices

### Архитектура

- **RooCode**: Боковая панель (навигация) + основная область + tool panel
- **Cursor**: Разделённые панели с фокусировкой и полноэкранными режимами
- **Cline**: Компактный sidebar, большой chat area, контекстное меню
- **Continue**: Минимальный UI, фокус на content
- **Windsurf**: Multi-pane layout с динамическим переразмещением
- **Copilot Chat**: Простой 2-panel layout, минимальный металл

### Компоненты (13 шт)

1. **SessionsPane** — список сессий (с иконками, фильтром)
2. **DirectoryTree** — дерево файлов (с поиском, collapse)
3. **ChatView** — история промптов и ответов
4. **PlanPanel** — план выполнения (если есть)
5. **ToolCallPanel** — инструменты и их вызовы
6. **PromptInput** — ввод нового промпта
7. **PermissionModal** — диалог разрешений
8. **FooterBar** — статус, горячие клавиши, версия
9. **CommandPalette** — поиск команд (Ctrl+K / Cmd+K)
10. **ContextMenu** — контекстное меню (Ctrl+/)
11. **SearchBar** — поиск по сессиям/файлам
12. **ValidationDisplay** — ошибки и предупреждения
13. **FileViewer** — просмотр содержимого файла

### Текущие возможности

- Создание/загрузка/удаление сессий
- Отправка промптов с контекстом (файлы)
- Просмотр истории (chat view)
- Просмотр файлов (tree + viewer)
- Перемещение в файловой системе
- Просмотр плана выполнения
- Отправка разрешений
- Просмотр терминальных команд

### Сильные стороны

Текущий интерфейс хорошо организован:

1. **Логическое разделение** — sidebar слева (навигация), основная область справа (контент)
2. **Проверенные паттерны** — похож на IDE (VS Code, JetBrains)
3. **Многопанельный** — видны все основные элементы
4. **Отзывчивый** — реагирует на события сервера
5. **Кроссплатформенный** — работает везде где есть Python

---

### Industry Best Practices

#### 1. Информационная иерархия (из RooCode, Cursor)

- **Первичная зона** (60%): Основной контент (chat, file content)
- **Вторичная зона** (20%): Навигация (files, sessions)
- **Третичная зона** (20%): Дополнительно (settings, help)
- **Модальные окна**: Только для критичных действий (confirm, permission)

#### 2. Контекстное меню (из Cline, Continue)

- Правый клик = контекстное меню
- Ctrl+/ = команды (command palette)
- Alt+S = быстрая смена сессии
- Ctrl+P = быстрый поиск файла

#### 3. Встроенный help и tutorial (из Aider, OpenCode)

- F1 = справка по текущему компоненту
- ? = список горячих клавиш
- Ctrl+H = tutorial для новичков
- Встроенные подсказки при first launch

#### 4. Состояния UI (из Windsurf, Copilot Chat)

- **Connecting...** → пульсирующий индикатор
- **Loading...** → progress bar
- **Error** → красный текст, звуковой сигнал (опционально)
- **Success** → зелёный текст, краткий feedback

#### 5. История операций (из RooCode, Cursor)

- Undo/Redo (Ctrl+Z / Ctrl+Y)
- История промптов (стрелки вверх/вниз)
- История команд терминала
- Просмотр истории изменений файлов

#### 6. Визуальная обратная связь (из Cline, Continue)

- Highlight активного элемента
- Анимация при загрузке (спиннер, progress)
- Изменение цвета при hover (если поддерживается)
- Toast-уведомления для успешных операций

#### 7. Поиск и фильтрация (из RooCode, Windsurf)

- Ctrl+F = поиск в текущем файле/чате
- Ctrl+Shift+F = поиск везде
- Фильтр сессий (введи префикс)
- Фильтр файлов (регулярные выражения)

#### 8. Команды и палитра (из Cursor, VS Code)

- Ctrl+K Ctrl+K = очистить чат
- Ctrl+Shift+P = список всех команд
- Раскрывающиеся меню с подсказками
- Сокращения для частых операций

#### 9. Кастомизация (из Continue, RooCode)

- Выбор цветовой схемы (светлая/тёмная)
- Переразмещение панелей (drag-n-drop)
- Настройка горячих клавиш (config file)
- Выбор шрифта и размера

#### 10. Микроанимации (из Copilot Chat, Windsurf)

- Плавное появление элементов
- Переходы между экранами
- Indication of progress (spinning indicator)
- Subtle feedback (color change, sound)

### Что НЕ подходит для TUI

- Drag-n-drop (ограничения терминала)
- Hover-state (не все терминалы поддерживают)
- Animations (могут замедлить TUI)
- Gestures (мышка работает ограниченно)

---

## Фазы улучшения

### Фаза 1: Критичные улучшения (2-4 недели)

Приоритет: **HIGH** — значительно улучшит UX новичков и опытных пользователей.

#### MVP фазы 1 (обязательный объём)

Чтобы снизить риск scope creep, Фаза 1 делится на две части:

- **MVP (релиз v1)**: 1.1 Информационная архитектура, 1.2 Help/Hotkeys, 1.4 Состояния UI
- **Расширение (релиз v1.1)**: 1.3 Контекстное меню (Command Palette)
- **Правило завершения фазы**: сначала выпускается MVP и собирается обратная связь, затем принимается решение о v1.1

#### Acceptance criteria для MVP фазы 1

1. Пользователь отправляет первый промпт без внешней помощи за целевое время (см. метрики).
2. В любом экране доступна встроенная справка (`F1`) и список горячих клавиш (`?`).
3. Статус подключения и обработки промпта всегда отображается в явном виде (connecting/loading/error/success).
4. Sidebar переключается между вкладками без потери текущего контекста.
5. Существующие горячие клавиши не ломаются без documented migration.

#### 1.1 Переработка информационной архитектуры

**Проблема**

Текущий интерфейс показывает слишком много одновременно:
- Все сессии в full-height sidebar
- Все файлы в full-height tree
- Chat + Plan + ToolCalls в основной области
- Много иконок, которые не сразу понятны

**Предложенное решение**

Три режима просмотра (вкладки в sidebar):

```
┌────────────────────────────────────┐
│ 📁 Sessions | 🗂️ Files | ⚙️ Settings │
├────────────────────────────────────┤
│ [Current Session]                  │
│ • New Session...                   │
│ • Existing Sessions...             │
│   └─ Session 1 (Oct 15)            │
│   └─ Session 2 (Oct 12)            │
│                                    │
│ ✨ Recent                          │
│ • session-42                       │
│ • project-refactor                 │
├────────────────────────────────────┤
│ ▶️ (expand/collapse)              │
└────────────────────────────────────┘
```

Новый sidebar имеет три вкладки: Sessions, Files, Settings.

**Технические детали**

Добавить обработку collapse/expand:

```python
# presentation/ui_state.py
@dataclass
class UIState:
    sidebar_tab: Literal["sessions", "files", "settings"] = "sessions"
    sessions_expanded: bool = True
    files_expanded: bool = True
    
    def toggle_sessions_expand(self) -> None:
        self.sessions_expanded = not self.sessions_expanded
        
    def toggle_files_expand(self) -> None:
        self.files_expanded = not self.files_expanded
```

```python
# tui/components/sidebar.py
class Sidebar(Static):
    def render_sessions_tab(self) -> str:
        if not self.ui_state.sessions_expanded:
            return "▼ Sessions [Press Space to expand]"
        return self._render_session_list()
    
    def render_files_tab(self) -> str:
        if not self.ui_state.files_expanded:
            return "▶ Files [Press Space to expand]"
        return self._render_file_tree()
```

Пример UI в TUI:

```
acp-client v0.2.0 | Connected to localhost:8000
┌─ 📁 Sessions | 🗂️ Files | ⚙️ Settings ─────────┐  ┌────────────────────────────────┐
│                                                │  │ Project Setup                  │
│ Current Session: refactor-ui                  │  │                                │
│ Created: Oct 15, 2024                         │  │ > Analyze the structure of:    │
│ Prompt: "analyze code structure"              │  │ - package.json                 │
│                                                │  │ - src/components/              │
│ ✨ Pinned                                      │  │                                │
│ • refactor-ui                                 │  │ AI: I'll analyze the project  │
│ • setup-docker                                │  │ structure for you.             │
│                                                │  │                                │
│ 📚 Recent                                      │  │ Files analyzed:                │
│ • session-42 (2h ago)                         │  │ • package.json ✓              │
│ • project-refactor (5h ago)                   │  │ • src/index.ts ✓              │
│ • debug-issue (1d ago)                        │  │                                │
│                                                │  │ [Input prompt here...]        │
│ + New Session                                 │  │                                │
└────────────────────────────────────────────────┘  └────────────────────────────────┘
```

**Метрики успеха**

1. Меньше scrolling в sidebar (compact по умолчанию)
2. Большее viewport для основного контента
3. Быстрее переключение между сессиями (Tab ключ)
4. Новичкам понятнее структура

---

#### 1.2 Интерактивный help и tutorial

**Проблема**

Новому пользователю не ясны:
- Что делать при первом запуске
- Какие горячие клавиши доступны
- Как создать/загрузить сессию
- Как работает file context

**Предложенное решение**

Встроенный tutorial на первом запуске:

```python
# tui/commands/tutorial.py
class TutorialCommand(UseCase):
    """Интерактивный tutorial для новичков"""
    
    async def execute(self) -> None:
        await self._show_welcome_screen()
        await self._show_basic_workflow()
        await self._show_hotkeys()
        await self._show_tips()
```

F1 = Help (зависит от контекста):
- F1 в chat → help по промптам
- F1 в file tree → help по файлам
- F1 в prompt input → help по синтаксису

? = Список горячих клавиш:

```
Global Hotkeys:
┌─────────────────────────────────────────────┐
│ F1              → Show help (context-aware) │
│ ?               → Show this                 │
│ Ctrl+K Ctrl+K   → Clear chat                │
│ Ctrl+Shift+P    → Command Palette           │
│ Alt+S           → Switch Session            │
│ Ctrl+N          → New Session               │
│                                             │
│ In Chat:                                    │
│ Enter           → Send Prompt               │
│ Shift+Enter     → New line                  │
│ ↑/↓             → History                   │
│ Ctrl+U          → Clear line                │
│                                             │
│ [Press ESC to close]                        │
└─────────────────────────────────────────────┘
```

**Технические детали**

Добавить HelpViewModel и HelpModal:

```python
# presentation/help_view_model.py
class HelpViewModel(BaseViewModel):
    """ViewModel for help system"""
    
    help_content: Observable[str] = Observable("")
    show_help: Observable[bool] = Observable(False)
    context: Observable[str] = Observable("global")
    
    def show_help_for_context(self, ctx: str) -> None:
        self.context.set(ctx)
        content = self._get_help_content(ctx)
        self.help_content.set(content)
        self.show_help.set(True)
```

**Пример UI в TUI**

```
┌─ Help: Prompts ────────────────────────────┐
│                                            │
│ How to send a prompt:                      │
│                                            │
│ 1. Click in the input field (bottom)       │
│ 2. Type your message or question           │
│ 3. Optionally add file context:            │
│    • Select files in file tree             │
│    • Press Space to toggle selection       │
│ 4. Press Enter to send                     │
│                                            │
│ Tips:                                      │
│ • Use Shift+Enter for new lines            │
│ • Use ↑/↓ for history                      │
│ • Selected files are shown in prompt       │
│                                            │
│ [ESC to close]                             │
└────────────────────────────────────────────┘
```

**Метрики успеха**

1. Первый сеанс занимает < 5 минут вместо 15
2. Пользователи находят горячие клавиши сами
3. Меньше вопросов в issues о базовых операциях

---

#### 1.3 Контекстное меню

**Проблема**

Сложно запомнить все горячие клавиши. Контекстное меню (Ctrl+/) помогает.

**Предложенное решение**

Ctrl+/ = command palette для текущего контекста:

```
┌─ Available Commands ──────────────────────┐
│ > Create new session                      │
│   Load existing session                   │
│   Delete current session                  │
│   Pin session                             │
│   Clear history                           │
│   Export session                          │
│                                           │
│ Search: [_______________]                 │
│ [↑/↓ to navigate, Enter to execute]       │
└───────────────────────────────────────────┘
```

Контекстное меню для files (Ctrl+K):

```
┌─ File Operations ──────────────────────┐
│ > Open                (Enter)           │
│   Copy path          (Ctrl+C)           │
│   Delete             (Delete)           │
│   Rename             (F2)               │
│   Create new file    (Ctrl+N)           │
│   Create folder      (Ctrl+Shift+N)     │
│   Refresh            (F5)               │
└────────────────────────────────────────┘
```

**Технические детали**

```python
# tui/commands/command_palette.py
class CommandPalette:
    """Context-aware command palette"""
    
    def get_commands_for_context(self, ctx: str) -> list[Command]:
        if ctx == "chat":
            return [
                Command("Send Prompt", self.send_prompt),
                Command("Clear Chat", self.clear_chat),
                Command("Export Chat", self.export_chat),
            ]
        elif ctx == "files":
            return [
                Command("Open File", self.open_file),
                Command("Delete", self.delete_file),
                Command("Copy Path", self.copy_path),
            ]
        return []
```

**Пример UI в TUI**

```
Chat View with right-click menu:

┌────────────────────────────┐
│ > Send Prompt              │
│   Copy message (Ctrl+C)    │
│   Regenerate response      │
│   Edit prompt              │
│   Clear chat (Ctrl+K Ctrl+ │
│   Export session           │
└────────────────────────────┘
```

**Метрики успеха**

1. Пользователи быстрее находят команды
2. Меньше опечаток в вводе (не нужно запоминать синтаксис)
3. Увеличивается discoverability функций

---

#### 1.4 Улучшение состояний UI

**Проблема**

Пользователь не всегда видит что происходит:
- Когда подключается к серверу (spinning indicator)
- Когда обрабатывается промпт (progress)
- Когда ошибка (why it failed)
- Когда успешно (confirmation)

**Предложенное решение**

Явные состояния для каждого компонента:

```python
# presentation/ui_state.py
class UIState:
    connection_state: Literal["disconnected", "connecting", "connected", "error"]
    loading_states: dict[str, bool]  # chat, files, permissions etc
    error_messages: dict[str, str]
    success_messages: list[str]
```

Визуальные индикаторы:

```
┌─ Connection Status ────────────────┐
│ ⟳ Connecting to localhost:8000... │  (spinning)
└────────────────────────────────────┘

┌─ After connection ─────────────────┐
│ ✓ Connected to localhost:8000      │  (green)
└────────────────────────────────────┘

┌─ On error ─────────────────────────┐
│ ✗ Connection failed: Timeout       │  (red)
│   [Retry] [Configure]              │
└────────────────────────────────────┘

┌─ Loading indicator ────────────────┐
│ Processing prompt... [████░░░░░░]  │  (progress)
│                                    │
│ [Cancel]                           │
└────────────────────────────────────┘
```

**Технические детали**

```python
# presentation/status_view_model.py
class StatusViewModel(BaseViewModel):
    connection_status: Observable[str] = Observable("disconnected")
    loading_progress: Observable[int] = Observable(0)
    error_message: Observable[str] = Observable("")
    success_message: Observable[str] = Observable("")
    
    def set_loading(self, is_loading: bool, message: str = ""):
        if is_loading:
            self.loading_progress.set(0)
        else:
            self.loading_progress.set(100)
    
    def set_error(self, message: str):
        self.error_message.set(message)
        # Auto-clear after 5 seconds
        asyncio.create_task(self._clear_error_after_delay())
```

Использование в ViewModels:

```python
# presentation/chat_view_model.py
async def send_prompt(self, text: str):
    self.status_vm.set_loading(True, "Sending prompt...")
    try:
        response = await self.send_prompt_use_case.execute(text)
        self.messages.append(response)
        self.status_vm.set_success("Prompt sent successfully")
    except Exception as e:
        self.status_vm.set_error(f"Failed to send: {e}")
    finally:
        self.status_vm.set_loading(False)
```

**Пример UI в TUI**

```
Footer with status:

┌─ Status: Processing... ████░░░░░░ 40% ────────────┐
│ [Cancel]                    [F1: Help] [?: Hotkeys] │
└────────────────────────────────────────────────────┘

After completion:

┌─ Status: ✓ Prompt sent successfully  [Clear] ──────┐
│ [F1: Help] [?: Hotkeys] [Ctrl+K Ctrl+K: Clear Chat]│
└────────────────────────────────────────────────────┘
```

**Метрики успеха**

1. Пользователи реже "застревают" в непонятном состоянии
2. Увеличивается вера в UI (clear feedback)
3. Меньше зависаний (явно показан progress)

---

### Фаза 2: Важные улучшения (2-3 недели)

#### 2.1 Undo/Redo система

**Проблема**

Если пользователь случайно удалил сессию или очистил чат, нет способа вернуться.

**Предложенное решение**

Ctrl+Z = undo, Ctrl+Y = redo для:
- Удаление сессии
- Очистка чата
- Удаление файлов (в future)

```python
# application/undo_redo.py
class UndoRedoManager:
    def __init__(self):
        self.undo_stack: list[Action] = []
        self.redo_stack: list[Action] = []
    
    def execute(self, action: Action) -> None:
        action.execute()
        self.undo_stack.append(action)
        self.redo_stack.clear()
    
    def undo(self) -> None:
        if self.undo_stack:
            action = self.undo_stack.pop()
            action.undo()
            self.redo_stack.append(action)
    
    def redo(self) -> None:
        if self.redo_stack:
            action = self.redo_stack.pop()
            action.execute()
            self.undo_stack.append(action)
```

#### 2.2 Inline валидация и suggestions

**Проблема**

При вводе промпта нет подсказок синтаксиса или валидации.

**Предложенное решение**

- Автозавершение для known commands
- Валидация при вводе (подчёркивание ошибок)
- Suggestions на основе истории

#### 2.3 Поиск и фильтрация

**Проблема**

Если много сессий (100+), сложно найти нужную.

**Предложенное решение**

Ctrl+F = поиск:
- По названию сессии
- По дате создания
- По количеству промптов
- По меткам (если добавим)

#### 2.4 Улучшение TerminalOutput

**Проблема**

Длинный вывод терминала может замедлить TUI.

**Предложенное решение**

- Lazy loading вывода
- Поиск по выводу (Ctrl+F)
- Экспорт в файл

---

### Фаза 3: Продвинутые функции (3-4 недели)

#### 3.1 Plugin система

Возможность добавлять custom компоненты и команды.

#### 3.2 Расширенная кастомизация

- Создание собственных тем
- Переразмещение панелей
- Custom горячие клавиши

#### 3.3 Integration с внешними tools

- Export в различные форматы
- Import из других инструментов
- Sync с облаком

---

### Фаза 4: Полировка (1-2 недели)

#### 4.1 Микроанимации и переходы

Плавные переходы при переключении вкладок, открытии модалей.

#### 4.2 Performance оптимизация

- Виртуализация для больших списков
- Кэширование rendered компонентов
- Асинхронный рендеринг

#### 4.3 Accessibility улучшения

- Screen reader поддержка
- Высокий контраст режим
- Клавиатурная навигация (полная)

---

## Реализация фаз

### Зависимости

Фазы имеют следующие зависимости:

```
Фаза 1 (базовая):
├─ 1.1 Информационная архитектура
├─ 1.2 Help система
├─ 1.4 Состояния UI
└─ 1.3 Контекстное меню (опционально после MVP)

Фаза 2 (build on 1):
├─ 2.1 Undo/Redo
├─ 2.2 Валидация
├─ 2.3 Поиск
└─ 2.4 Terminal improvements

Фаза 3 (independent):
├─ 3.1 Plugin система
├─ 3.2 Кастомизация
└─ 3.3 Интеграции

Фаза 4 (independent):
├─ 4.1 Анимации
├─ 4.2 Performance
└─ 4.3 Accessibility
```

### Фаза 1: Критичные улучшения

1. Создать `UIStateViewModel` и `UIStateObservable` как единый источник правды для UI-состояний.
2. Рефакторить `Sidebar` для вкладок и упрощённой информационной иерархии.
3. Добавить `HelpSystem` и `HelpViewModel` (`F1`, `?`, базовые подсказки первого запуска).
4. Добавить статусные индикаторы для `connecting/loading/error/success` в footer.
5. Обновить критичные ViewModel под новые состояния без тотального рефакторинга всего слоя.
6. Протестировать MVP на реальных терминалах (минимум: iTerm2, Terminal.app, Linux terminal).
7. После релиза MVP реализовать `CommandPalette` как отдельный шаг v1.1.

**Definition of Done для фазы 1**:
- Пройдены unit/integration тесты для новых компонентов.
- Ручные smoke-сценарии подтверждают отсутствие регрессий базовых hotkeys.
- Собраны метрики первой недели после релиза и принято решение по объёму фазы 2.

### Фаза 2: Важные улучшения

1. Реализовать UndoRedoManager
2. Добавить InlineValidator
3. Реализовать SearchEngine для сессий
4. Оптимизировать TerminalOutput

### Фаза 3 & 4: Продвинутые & Полировка

1. Разработать Plugin API
2. Настроить performance
3. Добавить animations (если поддерживает терминал)

---

## Метрики успеха и измерение

### Пользовательские метрики

#### Опросы пользователей

- Насколько интуитивен интерфейс (1-5)?
- Сколько времени на первое использование?
- Какие функции используются больше всего?
- Что раздражает больше всего?

#### Поведенческие метрики

- Time to first prompt (целевое: < 2 минуты)
- Commands per session (целевое: > 3)
- Error rate (целевое: < 5%)
- Session duration (целевое: > 10 минут)

#### Как измеряем

- Логируем события в клиенте: `app_started`, `session_created`, `prompt_sent`, `help_opened`, `command_palette_opened`, `error_shown`.
- Для каждого события фиксируем timestamp, тип терминала/OS и текущий экран.
- Метрики считаются еженедельно по rolling окну 7 дней, baseline собирается до релиза фазы 1.
- Минимальный критерий успешности релиза: улучшение минимум 2 из 4 поведенческих метрик без роста error rate.

---

## Риски и смягчение

### 1. Риск: Complexity Overload

**Описание**: Добавление слишком много функций сразу усложнит код и запутает пользователей.

**Вероятность**: HIGH | **Влияние**: CRITICAL

**Смягчение**:
- Разделить на 4 фазы (не всё сразу)
- MVP Фаза 1 только (2-3 недели)
- Получить feedback перед Фазой 2
- Каждая фаза имеет clear acceptance criteria

---

### 2. Риск: Performance Degradation

**Описание**: Новые компоненты (CommandPalette, Help, Status) могут замедлить TUI.

**Вероятность**: MEDIUM | **Влияние**: HIGH

**Смягчение**:
- Профилировать каждый новый компонент
- Использовать lazy loading где возможно
- Виртуализация для больших списков
- Асинхронный рендеринг в фоне

---

### 3. Риск: Breaking Changes

**Описание**: Реорганизация UI может сломать привычки пользователей.

**Вероятность**: MEDIUM | **Влияние**: MEDIUM

**Смягчение**:
- Сохранить все существующие горячие клавиши
- Добавить "Classic Mode" если нужно
- Хорошая документация изменений
- Migration guide для пользователей

---

### 4. Риск: Insufficient Testing

**Описание**: Новая UI может иметь баги на реальных терминалах.

**Вероятность**: MEDIUM | **Влияние**: MEDIUM

**Смягчение**:
- Unit тесты для всех новых компонентов
- MVVM тесты для ViewModels
- Integration тесты для сценариев
- Ручное тестирование на разных терминалах

---

### 5. Риск: Keyboard Shortcut Conflicts

**Описание**: Новые горячие клавиши могут конфликтовать с существующими.

**Вероятность**: HIGH | **Влияние**: LOW

**Смягчение**:
- Провести audit всех существующих bindings
- Использовать двухклавишные комбинации (Ctrl+K)
- Позволить пользователю переконфигурировать
- Документировать все bindings

---

### 6. Риск: Scope Creep

**Описание**: Проект может разрастись и никогда не завершиться.

**Вероятность**: MEDIUM | **Влияние**: CRITICAL

**Смягчение**:
- Строгая дисциплина по фазам
- Freeze требований для каждой фазы
- Code review для любых off-scope изменений
- Регулярные meetings на alignment

---

## Приоритизация

### Резюме

| Фаза | Приоритет | Сложность | Время | MVP? |
|------|-----------|-----------|-------|------|
| 1    | HIGH      | MEDIUM    | 2-4w | ✓    |
| 2    | MEDIUM    | MEDIUM    | 3w   | ✗    |
| 3    | LOW       | HIGH      | 4w   | ✗    |
| 4    | LOW       | MEDIUM    | 2w   | ✗    |

### Следующие шаги

1. **Неделя 1**: Утвердить требования MVP фазы 1 и матрицу hotkeys
2. **Неделя 2-3**: Реализовать MVP фазы 1 (1.1, 1.2, 1.4)
3. **Неделя 4**: Выпустить MVP, собрать baseline/feedback
4. **После**: Принять решение о `v1.1` (1.3 Command Palette) и объёме фазы 2

---

## Приложения

### A. Матрица горячих клавиш и конфликты

**Global (по умолчанию)**:
- `F1` — Help (context-aware)
- `?` — Список горячих клавиш
- `Ctrl+Shift+P` — Command Palette
- `Ctrl+/` — Context menu
- `Alt+S` — Switch Session
- `Ctrl+N` — New Session
- `Ctrl+K Ctrl+K` — Clear chat
- `Ctrl+H` — Tutorial (v1)

**Планируемые для v2**:
- `Ctrl+Z` — Undo
- `Ctrl+Y` — Redo
- `Ctrl+F` — Search

**Контекстные**:
- Chat: `Enter`, `Shift+Enter`, `↑/↓`, `Ctrl+U`
- Files: `Space`, `Enter`, `Delete`, `F2`
- Terminal: `Ctrl+C`, `Ctrl+D`, `↑/↓`

**Принцип разрешения конфликтов**:
1. `Global`-команда не должна перехватывать `Terminal`-контекст без явного opt-in.
2. Для конфликтующих сочетаний задаётся fallback (пример: `Ctrl+/` и `Ctrl+Shift+P` для открытия списка команд).
3. Все новые сочетания проходят проверку на macOS/Linux и документируются до релиза.

---

### B. Глоссарий терминов

| Термин | Значение |
|--------|----------|
| **Command Palette** | Интерактивное меню всех доступных команд |
| **Context Menu** | Меню операций для текущего элемента |
| **Undo/Redo** | Отмена и повтор последних действий |
| **Inline Validation** | Проверка корректности при вводе |
| **Lazy Loading** | Загрузка данных только при необходимости |
| **MVP** | Minimum Viable Product (базовая версия) |
| **MVVM** | Model-View-ViewModel архитектурный паттерн |
| **Observable** | Объект, который уведомляет об изменениях |
| **ViewModel** | Бизнес-логика и состояние для UI |
| **TUI** | Terminal User Interface |

---

### C. Ссылки на документацию

- [ARCHITECTURE.md](../developer-guide/ARCHITECTURE.md) — Архитектура Clean Architecture
- [DEVELOPING.md](../developer-guide/DEVELOPING.md) — Руководство разработки
- [TESTING.md](../developer-guide/TESTING.md) — Стратегия тестирования
- [TUI_CLIENT_SPECIFICATION.md](../archive/TUI_CLIENT_SPECIFICATION.md) — Техническое задание
- [MIGRATION-FROM-OLD-API.md](../archive/MIGRATION-FROM-OLD-API.md) — Миграция с legacy API
