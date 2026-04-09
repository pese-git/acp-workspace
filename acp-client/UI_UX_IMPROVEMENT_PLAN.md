# План улучшения UI/UX в acp-client

**Версия:** 1.0  
**Дата создания:** 2026-04-09  
**Статус:** Рекомендации к внедрению  
**Целевая аудитория:** Разработчики, UI/UX специалисты

---

## Содержание

1. [Executive Summary](#executive-summary)
2. [Текущее состояние UI](#текущее-состояние-ui)
3. [Лучшие практики индустрии](#лучшие-практики-индустрии)
4. [Приоритизированный план улучшений](#приоритизированный-план-улучшений)
5. [Детальные спецификации Фазы 1](#детальные-спецификации-фазы-1)
6. [Детальные спецификации Фазы 2](#детальные-спецификации-фазы-2)
7. [Технические рекомендации](#технические-рекомендации)
8. [Метрики успеха](#метрики-успеха)
9. [Риски и митигация](#риски-и-митигация)

---

## Executive Summary

### Краткое резюме текущего состояния

**acp-client** — это TUI приложение на базе Textual с современной Clean Architecture (5 слоев, MVVM паттерн, DI контейнер). Текущая реализация имеет:

- ✅ **Сильная архитектура**: Clean Architecture с четкими границами слоев
- ✅ **MVVM + Observable**: Реактивные обновления UI без прямых взаимозависимостей
- ✅ **13 компонентов TUI**: Хорошо разделенные на функциональные блоки
- ✅ **13 ViewModels**: Полное разделение логики UI от бизнес-логики
- ✅ **DI контейнер**: Централизованное управление зависимостями
- ✅ **Типизация**: Python 3.12+ с type hints

### Ключевые проблемы

1. **Дефрагментация информации** — пользователь видит разрозненные панели без четкой иерархии значимости
2. **Перегруженность клавиатурой** — более 20 горячих клавиш, сложно запомнить все
3. **Отсутствие интерактивного help/tutorial** — встроенная подсказка минималистична
4. **Недостаточная визуальная иерархия** — все элементы имеют примерно одинаковый визуальный вес
5. **Нет контекстного меню** — пользователь должен помнить горячие клавиши
6. **Отсутствие inline валидации** — ошибки показываются только в footer
7. **Слабое состояние loading/empty** — нет явных состояний загрузки данных
8. **Отсутствие undo/redo** — нельзя отменить случайное действие
9. **Нет встроенной поддержки плагинов** — архитектура готова, но интерфейс нет
10. **Минимальная настройка темы** — только несколько встроенных тем

### Главные рекомендации

**Фаза 1 (Критичные)**: Улучшить информационную архитектуру и базовую навигацию
- Переработать лайаут с учетом иерархии важности
- Добавить интерактивный tutorial и улучшенный help
- Реализовать контекстные меню (Ctrl+Click, Right Click)

**Фаза 2 (Важные)**: Расширить функциональность и feedback
- Добавить undo/redo с визуальным отображением
- Реализовать состояния loading, empty, error с правильной UI
- Добавить inline валидацию и suggestion

**Фаза 3 (Продвинутые)**: Новые возможности расширяемости
- Plugin система для пользовательских компонентов
- Расширенная настройка тем и раскладки
- Интеграция с внешними tools

**Фаза 4 (Полировка)**: Детали и оптимизация
- Микроанимации и переходы
- Performance оптимизация
- Accessibility улучшения

---

## Текущее состояние UI

### Архитектура

```
┌─────────────────────────────────────────────┐
│            ACPClientApp (Textual)           │
│  ├── Header                                  │
│  ├── Sidebar (Sessions)                     │
│  ├── MainContent                            │
│  │   ├── ChatView                           │
│  │   ├── FileTree & FileViewer              │
│  │   ├── TerminalOutput & TerminalLogModal  │
│  │   ├── PlanPanel                          │
│  │   └── ToolPanel                          │
│  ├── PromptInput                            │
│  ├── PermissionModal (overlay)              │
│  ├── Footer                                  │
│  └── Navigation Manager                     │
│
Presentation Layer
├── SessionViewModel (сессии и их состояние)
├── ChatViewModel (сообщения и история)
├── FileSystemViewModel (файловое дерево)
├── FileViewerViewModel (просмотр файлов)
├── TerminalViewModel (терминал и логи)
├── PlanViewModel (план выполнения)
├── PermissionViewModel (разрешения)
├── UIViewModel (глобальное состояние UI)
└── 5 других ViewModels
```

### Компоненты (13 шт)

| № | Компонент | Ответственность | Состояние |
|----|-----------|-----------------|----------|
| 1 | Header | Статус подключения, название сессии | ✅ Хорошо |
| 2 | Footer | Горячие клавиши, статус, hints | ✅ Хорошо |
| 3 | Sidebar | Список сессий | ⚠️ Перегружен |
| 4 | ChatView | История сообщений | ✅ Хорошо |
| 5 | FileTree | Навигация по файлам | ✅ Хорошо |
| 6 | FileViewer | Просмотр содержимого | ⚠️ Без preview |
| 7 | PromptInput | Ввод prompt | ✅ Хорошо |
| 8 | PermissionModal | Запрос разрешений | ✅ Хорошо |
| 9 | ToolPanel | Показ tool calls | ⚠️ Без фильтрации |
| 10 | PlanPanel | План выполнения | ⚠️ Без expand/collapse |
| 11 | TerminalOutput | Вывод терминала | ⚠️ Нет search |
| 12 | TerminalLogModal | Полный лог | ⚠️ Нет фильтрации |
| 13 | NavigationManager | Навигация между фокусом | ✅ Хорошо |

### Текущие возможности

**Горячие клавиши** (20+):
- Управление сессиями: `Ctrl+N`, `Ctrl+J`, `Ctrl+K`, `Ctrl+S`, `Ctrl+B`
- Навигация: `Tab`, `Ctrl+Up/Down`
- Операции: `Ctrl+Enter`, `Ctrl+L`, `Ctrl+H`, `Ctrl+T`, `Ctrl+C`, `Ctrl+Q`
- Файлы: `Ctrl+F` (поиск)
- История: `Up/Down`

**Состояния UI**:
- Connected / Reconnecting / Degraded / Offline
- Loading / Ready / Error (частичная)
- Message types: User, Assistant, System, ToolCall

### Сильные стороны

1. **Clean Architecture** — четкое разделение слоев, легко расширять
2. **MVVM паттерн** — полное разделение логики UI от бизнес-логики
3. **Observable pattern** — реактивные обновления без explicit refresh
4. **Type hints** — полная типизация Python 3.12+
5. **Тестируемость** — MVVM тесты, Unit тесты, Integration тесты
6. **DI контейнер** — нет hardcoded зависимостей
7. **Модульность** — компоненты хорошо разделены

### Выявленные проблемы

#### 1. Информационная архитектура
- Нет четкой иерархии между элементами
- Sidebar, MainContent и RightPanel имеют примерно одинаковый вес
- Пользователь не видит, где искать нужную информацию

**Пример**: Tool calls показываются в ToolPanel, но их можно пропустить если фокус в ChatView

#### 2. Навигация и управление
- Более 20 горячих клавиш — когнитивная перегрузка
- Нет визуальной подсказки о доступных действиях в текущем контексте
- Отсутствует контекстное меню (right-click)
- Нет фокус-индикатора где он нужен

**Пример**: Трудно вспомнить, что `Ctrl+T` открывает полный логи если пользователь не в session view

#### 3. Состояния UI
- Loading состояние не всегда явно показывается
- Empty состояние (нет сессий, нет сообщений) слабо визуализируется
- Error состояние отображается только в footer без контекста

**Пример**: Когда загружается новая сессия, непонятно идет ли загрузка или просто пусто

#### 4. Feedback пользователю
- Отсутствует inline валидация (при вводе prompt, редактировании)
- Нет suggestion/autocomplete для команд
- Отсутствует undo/redo
- Нет явного feedback при длительных операциях

**Пример**: Пользователь не видит, что prompt слишком длинный пока не попытается отправить

#### 5. Содержимое файлов
- FileViewer показывает весь файл без preview
- Нет встроенного поиска без открытия модального окна
- Нет быстрого переключения между файлами

**Пример**: Пользователь должен помнить, какой файл уже открывал

#### 6. Расширяемость
- Нет встроенного механизма для пользовательских компонентов
- Архитектура готова для плагинов, но интерфейс отсутствует
- Нет встроенной темизации без изменения кода

---

## Лучшие практики индустрии

### Что работает в других TUI/CLI инструментах

#### 1. Информационная иерархия (из RooCode, Cursor)
- **Основная область внимания**: Центральный контент занимает максимум места
- **Вторичная информация**: На боку, но быстро доступна
- **Tertiary**: В модальных окнах или через команды
- **Применение**: Увеличить размер ChatView, сделать ToolPanel колапсируемым

#### 2. Контекстное меню (из Cline, Continue)
- **Right-click или Ctrl+Click**: Показывает действия для элемента
- **Контекстно-чувствительное**: Меню меняется в зависимости от текущей позиции
- **Быстрый доступ**: Не нужно помнить горячие клавиши
- **Применение**: Добавить контекстные меню для файлов, сообщений, tool calls

#### 3. Встроенный help и tutorial (из Aider, OpenCode)
- **Interactive tutorial**: Показывается при первом запуске
- **Tooltips**: На горячие клавиши при наведении
- **In-app documentation**: Встроенная справка без выхода из приложения
- **Применение**: Создать интерактивный guide для новых пользователей

#### 4. Состояния UI (из Windsurf, Copilot Chat)
- **Loading**: Спиннер + подсказка что происходит
- **Empty**: Дружелюбное сообщение с действиями
- **Error**: Понятное сообщение об ошибке с решениями
- **Success**: Краткое уведомление об успехе
- **Применение**: Внедрить стандартные состояния для всех компонентов

#### 5. История операций (из RooCode, Cursor)
- **Undo/Redo**: Отмена последних действий
- **История команд**: Быстрый доступ к последним операциям
- **Состояние**: Видно текущее состояние и что можно отменить
- **Применение**: Добавить undo/redo для создания сессии, отправки prompt

#### 6. Визуальная обратная связь (из Cline, Continue)
- **Inline validation**: Ошибки показываются прямо в поле ввода
- **Suggestion**: Подсказки при вводе
- **Progress**: Видимый прогресс при длительных операциях
- **Применение**: Добавить валидацию prompt, suggestion для команд

#### 7. Поиск и фильтрация (из RooCode, Windsurf)
- **Global search**: Поиск везде (файлы, сообщения, tool calls)
- **Inline search**: Поиск в текущем контенте
- **Фильтрация**: Фильтр по типам (успешные/неудачные tool calls)
- **Применение**: Добавить улучшенный поиск в TerminalOutput, ToolPanel

#### 8. Команды и палитра (из Cursor, VS Code)
- **Command palette**: `Ctrl+Shift+P` для быстрого доступа ко всем командам
- **Поиск команд**: Нечеткий поиск по названию
- **Группировка**: Команды организованы по категориям
- **Применение**: Создать палитру команд как альтернативу горячим клавишам

#### 9. Кастомизация (из Continue, RooCode)
- **Пользовательские темы**: Не только встроенные, но и возможность создать свою
- **Настройка раскладки**: Пользователь может выбрать что показывать
- **Настройка горячих клавиш**: Переопределить горячие клавиши
- **Применение**: Добавить конфигурацию раскладки, горячих клавиш

#### 10. Микроанимации (из Copilot Chat, Windsurf)
- **Плавные переходы**: Появление/исчезновение элементов
- **Loading animation**: Спиннеры вместо статичных загрузок
- **Feedback**: Визуальная обратная связь при нажатии кнопки
- **Применение**: Добавить анимации для лучшей обратной связи

### Что НЕ подходит для TUI

❌ **Drag-and-drop** — сложно реализовать в терминале, используйте keyboard shortcuts
❌ **Сложные графики** — используйте текстовые представления (ASCII art)
❌ **Множество мышиных операций** — фокусируйтесь на клавиатуре
❌ **Красивые картинки** — в TUI главное функциональность и читаемость
❌ **Сложная анимация** — отвлекает от работы
❌ **Маленькие элементы** — в терминале должно быть достаточно места
❌ **Множество hover состояний** — в терминале нет hover для non-mouse

---

## Приоритизированный план улучшений

### Фаза 1: Критичные улучшения (1-2 недели)

Максимальная польза для UX при минимальных усилиях.

#### 1.1 Переработка информационной архитектуры
- **Цель**: Пользователь видит контекст и может легко найти нужную информацию
- **Действия**:
  - Увеличить ChatView на 60% (сейчас ~50%)
  - Сделать ToolPanel/PlanPanel колапсируемыми (Ctrl+T для toggle)
  - Добавить индикатор непрочитанных tool calls
  - Улучшить визуальный контраст между компонентами

#### 1.2 Интерактивный help и tutorial
- **Цель**: Новые пользователи понимают как использовать приложение
- **Действия**:
  - Создать интерактивный tutorial при первом запуске
  - Добавить встроенный command palette (Ctrl+K)
  - Улучшить встроенную подсказку (Ctrl+H) с категориями
  - Добавить tooltips на горячие клавиши

#### 1.3 Контекстное меню
- **Цель**: Пользователь видит доступные действия без запоминания горячих клавиш
- **Действия**:
  - Добавить контекстное меню для файлов в FileTree
  - Контекстное меню для сессий в Sidebar
  - Контекстное меню для сообщений в ChatView
  - Контекстное меню для tool calls в ToolPanel

#### 1.4 Улучшение состояний UI
- **Цель**: Пользователь понимает что происходит в каждый момент
- **Действия**:
  - Добавить loading state с спиннером для долгих операций
  - Empty state с подсказками для пустых компонентов
  - Error state с понятным сообщением и решением
  - Success state с кратким уведомлением

### Фаза 2: Важные улучшения (2-3 недели)

Расширение функциональности для опытных пользователей.

#### 2.1 Undo/Redo система
- **Цель**: Пользователь может отменить случайное действие
- **Действия**:
  - Реализовать undo/redo для критичных операций
  - Добавить визуальное отображение (Ctrl+Z/Ctrl+Y)
  - Сохранить историю между сессиями
  - Ограничить историю до 50 действий

#### 2.2 Inline валидация и suggestions
- **Цель**: Пользователь получает feedback при вводе
- **Действия**:
  - Добавить валидацию при вводе prompt
  - Показывать length warning для длинных prompt
  - Добавить suggestion для известных команд
  - Реализовать autocomplete для часто используемых команд

#### 2.3 Поиск и фильтрация
- **Цель**: Пользователь находит нужную информацию быстро
- **Действия**:
  - Добавить поиск по сообщениям в ChatView
  - Фильтрация tool calls (успешные/ошибки/по типу)
  - Поиск в TerminalOutput (Ctrl+F)
  - Global search (Ctrl+Shift+F) по всему контенту

#### 2.4 Улучшение TerminalOutput
- **Цель**: Пользователь легче ориентируется в логах
- **Действия**:
  - Добавить встроенный поиск (Ctrl+F)
  - Синхронизация с TerminalLogModal
  - Фильтрация по уровню (INFO, ERROR, WARNING)
  - Автоскролл на новые сообщения

### Фаза 3: Продвинутые функции (3-4 недели)

Новые возможности для опытных пользователей.

#### 3.1 Plugin система
- **Цель**: Пользователь может расширять функциональность
- **Действия**:
  - Реализовать базовую plugin архитектуру
  - API для создания пользовательских компонентов
  - Загрузка плагинов из конфига
  - Примеры плагинов в документации

#### 3.2 Расширенная кастомизация
- **Цель**: Пользователь настраивает интерфейс под себя
- **Действия**:
  - Конфигурация раскладки (какие панели показывать)
  - Переопределение горячих клавиш
  - Создание пользовательских тем
  - Импорт/экспорт конфигурации

#### 3.3 Integration с внешними tools
- **Цель**: Пользователь интегрирует свои инструменты
- **Действия**:
  - Webhook для external events
  - Интеграция с git (показ дифф)
  - Интеграция с package managers
  - Экспорт истории сессий

### Фаза 4: Полировка (1-2 недели)

Финальные улучшения для качества.

#### 4.1 Микроанимации и переходы
- **Цель**: UI более приятен в использовании
- **Действия**:
  - Плавные переходы при открытии/закрытии модальных окон
  - Спиннеры для loading состояний
  - Fade in/out для новых элементов
  - Highlight для обновленных элементов

#### 4.2 Performance оптимизация
- **Цель**: Приложение быстро реагирует на действия
- **Действия**:
  - Оптимизация переренdering больших списков
  - Ленивая загрузка для большых файлов
  - Кэширование часто используемых данных
  - Профилирование и устранение bottlenecks

#### 4.3 Accessibility улучшения
- **Цель**: Приложение доступно для всех пользователей
- **Действия**:
  - Поддержка screen readers
  - Хорошая контрастность цветов
  - Размер шрифта должен быть настраиваемым
  - Режим высокого контраста

---

## Детальные спецификации Фазы 1

### 1.1 Переработка информационной архитектуры

#### Проблема
Текущий лайаут имеет примерно равный вес для всех панелей:
```
┌─────────────┬──────────────────┬─────────────┐
│             │                  │             │
│  Sidebar    │  Chat (50%)      │  Tools (20%)│
│  (20%)      │                  │             │
├─────────────┤──────────────────┼─────────────┤
│  Prompt Input                  │             │
├─────────────┴──────────────────┴─────────────┤
│  Footer                                      │
└────────────────────────────────────────────────┘
```

Пользователь может пропустить важные tool calls если фокус в ChatView.

#### Предложенное решение
Переделать лайаут с четкой иерархией:
```
┌─────────────┬────────────────────────────────┐
│             │                                │
│  Sidebar    │  Chat (70%)                    │
│  (20%)      │  + Plan below (collapsible)    │
│             │                                │
├─────────────┼────────────────────────────────┤
│  Files (15%)│  Chat continued...            │
│  Tree       │                                │
├─────────────┼────────────────────────────────┤
│  Prompt Input (all width)                   │
├─────────────┴────────────────────────────────┤
│  Footer + Tools indicator                   │
└──────────────────────────────────────────────┘
```

#### Технические детали

**Изменения в [`acp-client/src/acp_client/tui/app.py`](acp-client/src/acp_client/tui/app.py:line)**:

```python
# Новая структура компонирования
def compose(self) -> ComposeResult:
    with Screen():
        yield Header()
        
        with Horizontal():
            # Левая панель: Sidebar + Files
            with Vertical(id="left-panel"):
                yield Sidebar()
                yield FileTree()
            
            # Центр: Chat + Plan (collapsible)
            with Vertical(id="center-panel"):
                yield ChatView()
                yield PlanPanel(collapsed=False)  # NEW: collapsible
            
            # Справа: Tools (NEW layout)
            with Vertical(id="right-panel"):
                yield ToolPanel()
                yield TerminalOutput()
        
        yield PromptInput()
        yield Footer()

# Добавить обработку collapse/expand
def action_toggle_plan_panel(self) -> None:
    """Toggle plan panel visibility"""
    plan = self.query_one(PlanPanel)
    plan.collapsed = not plan.collapsed
    self.refresh()
```

**Размеры в [`acp-client/src/acp_client/tui/styles/app.tcss`](acp-client/src/acp_client/tui/styles/app.tcss:line)**:

```tcss
#left-panel {
    width: 20;
    border: solid $primary;
}

#center-panel {
    width: 1fr;  /* 70% */
    border: solid $primary;
}

#right-panel {
    width: 25;
    border: solid $primary;
    height: 50%;  /* collapsible */
}

/* Collapsed state */
.collapsed {
    display: none;
}
```

#### Пример UI в TUI

```
┌──────────────┬─────────────────────────────┬──────────────┐
│ [New]        │ chat > Session 1             │ [+] Tools    │
│ [✓] Session1 │ ┌──────────────────────────┐ │ ✓ tool_0     │
│ [+] Session2 │ │ User: Analyze code       │ │   read_file  │
│              │ │                          │ │ ✓ tool_1     │
│ Files        │ │ Assistant: I'll analyze  │ │   write_file │
│ ├─ src/      │ │ the structure...         │ │ ⏳ tool_2     │
│ ├─ tests/    │ │ [Plan: 3/5 completed]  │ │   execute    │
│ └─ README.md │ └──────────────────────────┘ │              │
│              │                               │              │
│              │                               │──────────────│
│              │                               │ $ output     │
│              │                               │ exit code: 0 │
├──────────────┼─────────────────────────────┼──────────────┤
│ > prompt: ___________________________________ (Ctrl+Enter)|
├──────────────┴─────────────────────────────┴──────────────┤
│ Ctrl+N:new | Ctrl+T:toggle tools [3↓] | Ctrl+Q:quit     │
└───────────────────────────────────────────────────────────┘
```

#### Метрики успеха
- ✅ Чат занимает 70% (вместо 50%)
- ✅ Tool calls имеют визуальный индикатор в footer
- ✅ PlanPanel можно toggle через Ctrl+T
- ✅ Все панели имеют четкие границы

---

### 1.2 Интерактивный help и tutorial

#### Проблема
- Более 20 горячих клавиш, пользователь не запоминает
- Встроенная подсказка (Ctrl+H) минималистична
- Нет tutorial при первом запуске
- Новые пользователи теряются в функциональности

#### Предложенное решение
Создать многоуровневую систему помощи:

1. **Interactive Tutorial** — первый запуск
2. **Command Palette** (Ctrl+K) — быстрый доступ ко всем командам
3. **Context Help** (Ctrl+H) — улучшенная справка с категориями
4. **Tooltips** — подсказки при наведении на элементы

#### Технические детали

**Новый модуль: [`acp-client/src/acp_client/tui/help_system.py`](acp-client/src/acp_client/tui/help_system.py:line)**

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class HelpItem:
    """Описание команды или действия"""
    name: str
    description: str
    shortcut: str | None = None
    category: str = "General"
    example: str | None = None
    relatedTopics: list[str] | None = None

class CommandPalette:
    """Модальное окно с поиском команд (Ctrl+K)"""
    
    def __init__(self):
        self.commands: list[HelpItem] = [
            HelpItem(
                name="New Session",
                description="Create a new session",
                shortcut="Ctrl+N",
                category="Session"
            ),
            HelpItem(
                name="Toggle Tools Panel",
                description="Show/hide tools and terminal output",
                shortcut="Ctrl+T",
                category="View"
            ),
            # ... 20+ команд
        ]
    
    def filter_commands(self, query: str) -> list[HelpItem]:
        """Нечеткий поиск по командам"""
        # Реализация fuzzy search
        pass
    
    def execute_command(self, item: HelpItem) -> None:
        """Выполнить команду"""
        pass

class InteractiveTutorial:
    """Первый запуск приложения"""
    
    def show_tutorial(self) -> None:
        """Показать интерактивный tutorial"""
        steps = [
            ("Welcome", "Welcome to acp-client! Let's learn the basics."),
            ("Create Session", "Press Ctrl+N to create your first session"),
            ("Send Prompt", "Type your prompt and press Ctrl+Enter"),
            ("View Tools", "Press Ctrl+T to see tool calls"),
            ("Done", "You're ready to go! Press Ctrl+K for command palette"),
        ]
        # Показать modal с пошаговым guide
        pass
```

**Интеграция в [`acp-client/src/acp_client/tui/app.py`](acp-client/src/acp_client/tui/app.py:line)**:

```python
class ACPClientApp(App):
    
    def on_mount(self) -> None:
        """Инициализация приложения"""
        # Показать tutorial если первый запуск
        if not self._config.tutorial_completed:
            self.show_tutorial()
    
    def action_command_palette(self) -> None:
        """Ctrl+K: Открыть Command Palette"""
        palette = CommandPalette()
        self.push_screen(palette)
    
    def action_show_help(self) -> None:
        """Ctrl+H: Показать справку (улучшенную)"""
        # Заменить на улучшенную справку с категориями
        pass
```

#### Пример UI в TUI

**Command Palette (Ctrl+K)**:
```
┌──────────────────────────────────────────────┐
│ Command Palette: ________________            │
├──────────────────────────────────────────────┤
│ ▶ New Session          (Ctrl+N)  [Session]   │
│   Create a new session and connect...       │
│                                              │
│ ▶ Toggle Tools Panel   (Ctrl+T)  [View]     │
│   Show/hide tools and terminal output        │
│                                              │
│ ▶ Send Prompt          (Ctrl+Enter) [Chat]  │
│   Send your prompt to the agent              │
│                                              │
│ ▶ Previous Session     (Ctrl+J)  [Session]   │
│   Switch to previous session                 │
└──────────────────────────────────────────────┘
```

**Interactive Tutorial**:
```
┌──────────────────────────────────────────────┐
│ 🎓 Welcome to acp-client!                   │
│                                              │
│ Step 1/5: Create Your First Session         │
│                                              │
│ Let's start by creating a session. Press:   │
│                                              │
│   Ctrl+N                                     │
│                                              │
│ [Next] [Skip]                               │
└──────────────────────────────────────────────┘
```

#### Метрики успеха
- ✅ Command Palette содержит все 20+ команд
- ✅ Поиск в палитре находит команду за <100ms
- ✅ Tutorial показывается при первом запуске
- ✅ Все команды имеют description и category

---

### 1.3 Контекстное меню

#### Проблема
Пользователь должен помнить горячие клавиши для выполнения действий.
Нет визуального указания доступных действий.

#### Предложенное решение
Добавить контекстное меню (Ctrl+Click или Right Click) для основных элементов:
- Сессии в Sidebar
- Файлы в FileTree
- Сообщения в ChatView
- Tool calls в ToolPanel

#### Технические детали

**Новый компонент: [`acp-client/src/acp_client/tui/components/context_menu.py`](acp-client/src/acp_client/tui/components/context_menu.py:line)**

```python
from typing import Callable
from textual.widgets import Modal, Button, Static
from textual.containers import Vertical

class ContextMenu(Modal):
    """Контекстное меню для быстрого доступа к действиям"""
    
    def __init__(self, items: list[tuple[str, Callable]]) -> None:
        """
        Args:
            items: List of (label, callback) tuples
        """
        super().__init__()
        self.items = items
    
    def compose(self) -> ComposeResult:
        with Vertical():
            for label, _ in self.items:
                yield Button(label, id=label.lower().replace(" ", "_"))

# Примеры использования для разных компонентов

class EnhancedSidebar(Sidebar):
    """Sidebar с контекстным меню для сессий"""
    
    def action_show_session_context_menu(self, session_id: str) -> None:
        """Ctrl+Click на сессию"""
        context_items = [
            ("Load", lambda: self._load_session(session_id)),
            ("Duplicate", lambda: self._duplicate_session(session_id)),
            ("Rename", lambda: self._rename_session(session_id)),
            ("Delete", lambda: self._delete_session(session_id)),
        ]
        menu = ContextMenu(context_items)
        self.app.push_screen(menu)

class EnhancedFileTree(FileTree):
    """FileTree с контекстным меню"""
    
    def action_show_file_context_menu(self, file_path: str) -> None:
        context_items = [
            ("View", lambda: self._view_file(file_path)),
            ("Edit", lambda: self._edit_file(file_path)),
            ("Copy Path", lambda: self._copy_path(file_path)),
            ("Reveal in System", lambda: self._open_in_system(file_path)),
        ]
        menu = ContextMenu(context_items)
        self.app.push_screen(menu)
```

**Интеграция в [`acp-client/src/acp_client/tui/app.py`](acp-client/src/acp_client/tui/app.py:line)**:

```python
def on_key(self, event: events.Key) -> None:
    """Обработка горячих клавиш"""
    if event.key == "ctrl+delete":  # Ctrl+Click simulation
        # Определить какой элемент под фокусом
        focused = self.focused
        if isinstance(focused, SessionItem):
            self.action_show_session_context_menu(focused.session_id)
        elif isinstance(focused, FileItem):
            self.action_show_file_context_menu(focused.file_path)
```

#### Пример UI в TUI

**Контекстное меню для файла**:
```
[File Tree]
├─ src/
│ ├─ main.py
│ └─ config.py  ← Ctrl+Click
│
┌──────────────────┐
│ View             │
│ Edit             │
│ Copy Path        │
│ Reveal in System │
└──────────────────┘
```

#### Метрики успеха
- ✅ Контекстное меню для Sidebar (сессии)
- ✅ Контекстное меню для FileTree
- ✅ Контекстное меню для ChatView (сообщения)
- ✅ Контекстное меню для ToolPanel (tool calls)

---

### 1.4 Улучшение состояний UI

#### Проблема
Пользователь не всегда понимает что происходит:
- Loading состояние не явно показывается
- Empty состояние слабо визуализируется
- Error состояние отображается только в footer

#### Предложенное решение
Создать стандартные состояния для всех компонентов:
- **Loading**: Спиннер + "Loading..."
- **Empty**: Дружелюбное сообщение с действиями
- **Error**: Понятное сообщение + решение
- **Success**: Краткое уведомление

#### Технические детали

**Новый модуль: [`acp-client/src/acp_client/tui/components/state_display.py`](acp-client/src/acp_client/tui/components/state_display.py:line)**

```python
from enum import Enum
from textual.widgets import Static
from textual.containers import Vertical, Center

class StateType(Enum):
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"
    SUCCESS = "success"
    NORMAL = "normal"

class StateDisplay(Static):
    """Стандартное отображение состояния"""
    
    def __init__(self, state_type: StateType, message: str = "") -> None:
        super().__init__()
        self.state_type = state_type
        self.message = message
    
    def render(self) -> str:
        match self.state_type:
            case StateType.LOADING:
                return f"⠋ Loading {self.message}..."
            case StateType.EMPTY:
                return f"📭 {self.message}\nPress Ctrl+N to get started"
            case StateType.ERROR:
                return f"❌ Error: {self.message}\nCheck logs with Ctrl+T"
            case StateType.SUCCESS:
                return f"✅ {self.message}"
            case StateType.NORMAL:
                return ""

# Использование в компонентах
class ChatViewEnhanced(ChatView):
    """ChatView с состояниями"""
    
    def _on_messages_loading(self) -> None:
        """Когда загружаются сообщения"""
        self._state_display.update(
            StateDisplay(StateType.LOADING, "messages")
        )
    
    def _on_messages_empty(self) -> None:
        """Когда нет сообщений"""
        self._state_display.update(
            StateDisplay(StateType.EMPTY, "No messages yet")
        )
    
    def _on_messages_error(self, error: str) -> None:
        """Когда ошибка загрузки"""
        self._state_display.update(
            StateDisplay(StateType.ERROR, error)
        )
```

**Стили в [`acp-client/src/acp_client/tui/styles/app.tcss`](acp-client/src/acp_client/tui/styles/app.tcss:line)**:

```tcss
StateDisplay {
    align: center middle;
    color: $accent;
}

StateDisplay.loading {
    color: $primary;
}

StateDisplay.error {
    color: $error;
    background: $error 0%;
}

StateDisplay.empty {
    color: $text-muted;
}

StateDisplay.success {
    color: $success;
}
```

#### Пример UI в TUI

**Loading состояние**:
```
┌────────────────────────────────┐
│                                │
│         ⠋ Loading messages...  │
│                                │
│     (Спиннер анимируется)      │
│                                │
└────────────────────────────────┘
```

**Empty состояние**:
```
┌────────────────────────────────┐
│                                │
│       📭 No messages yet       │
│                                │
│  Press Ctrl+Enter to send      │
│       your first prompt        │
│                                │
└────────────────────────────────┘
```

**Error состояние**:
```
┌────────────────────────────────┐
│                                │
│  ❌ Error: Failed to load file │
│                                │
│   Check logs with Ctrl+T       │
│                                │
│      [Retry]              [OK] │
│                                │
└────────────────────────────────┘
```

#### Метрики успеха
- ✅ Loading состояние для всех async операций
- ✅ Empty состояние с actions для пустых компонентов
- ✅ Error состояние с решениями для errors
- ✅ Success уведомление при успешных операциях

---

## Детальные спецификации Фазы 2

### 2.1 Undo/Redo система

#### Проблема
Пользователь не может отменить случайное действие (создание сессии, отправку prompt).

#### Предложенное решение
Реализовать undo/redo для критичных операций:
- Создание/удаление сессии
- Отправка prompt
- Редактирование файлов

#### Технические детали

**Новый модуль: [`acp-client/src/acp_client/application/undo_redo.py`](acp-client/src/acp_client/application/undo_redo.py:line)**

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Deque
from collections import deque

T = TypeVar('T')

class Command(ABC):
    """Базовая команда для undo/redo"""
    
    @abstractmethod
    async def execute(self) -> None:
        """Выполнить команду"""
        pass
    
    @abstractmethod
    async def undo(self) -> None:
        """Отменить команду"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание команды для UI"""
        pass

class CreateSessionCommand(Command):
    """Команда создания сессии"""
    
    def __init__(self, session_coordinator, config):
        self.session_coordinator = session_coordinator
        self.config = config
        self.session_id = None
    
    async def execute(self) -> None:
        """Создать сессию"""
        result = await self.session_coordinator.create_session(
            self.config
        )
        self.session_id = result.session_id
    
    async def undo(self) -> None:
        """Удалить сессию"""
        if self.session_id:
            await self.session_coordinator.delete_session(self.session_id)
    
    @property
    def description(self) -> str:
        return "Create Session"

class UndoRedoManager:
    """Менеджер undo/redo операций"""
    
    def __init__(self, max_history: int = 50):
        self.undo_stack: Deque[Command] = deque(maxlen=max_history)
        self.redo_stack: Deque[Command] = deque(maxlen=max_history)
    
    async def execute_command(self, command: Command) -> None:
        """Выполнить команду и добавить в историю"""
        await command.execute()
        self.undo_stack.append(command)
        self.redo_stack.clear()  # Очистить redo при новой команде
    
    async def undo(self) -> None:
        """Отменить последнюю команду"""
        if self.undo_stack:
            command = self.undo_stack.pop()
            await command.undo()
            self.redo_stack.append(command)
    
    async def redo(self) -> None:
        """Повторить последнюю отмененную команду"""
        if self.redo_stack:
            command = self.redo_stack.pop()
            await command.execute()
            self.undo_stack.append(command)
    
    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
    
    def get_undo_description(self) -> str | None:
        if self.undo_stack:
            return f"Undo: {self.undo_stack[-1].description}"
        return None
    
    def get_redo_description(self) -> str | None:
        if self.redo_stack:
            return f"Redo: {self.redo_stack[-1].description}"
        return None
```

**Интеграция в [`acp-client/src/acp_client/presentation/session_view_model.py`](acp-client/src/acp_client/presentation/session_view_model.py:line)**:

```python
class SessionViewModel(BaseViewModel):
    """ViewModel для управления сессиями с undo/redo"""
    
    def __init__(self, session_coordinator, undo_redo_manager):
        super().__init__()
        self.session_coordinator = session_coordinator
        self.undo_redo_manager = undo_redo_manager
        
        # Observable для undo/redo состояния
        self.can_undo = Observable(False)
        self.can_redo = Observable(False)
        self.undo_description = Observable("")
        self.redo_description = Observable("")
    
    async def create_session(self, config):
        """Создать сессию с поддержкой undo"""
        command = CreateSessionCommand(self.session_coordinator, config)
        await self.undo_redo_manager.execute_command(command)
        self._update_undo_redo_state()
    
    async def undo(self):
        """Отменить последнюю операцию"""
        await self.undo_redo_manager.undo()
        self._update_undo_redo_state()
    
    async def redo(self):
        """Повторить последнюю отмененную операцию"""
        await self.undo_redo_manager.redo()
        self._update_undo_redo_state()
    
    def _update_undo_redo_state(self):
        """Обновить состояние undo/redo для UI"""
        self.can_undo.value = self.undo_redo_manager.can_undo
        self.can_redo.value = self.undo_redo_manager.can_redo
        self.undo_description.value = (
            self.undo_redo_manager.get_undo_description() or ""
        )
        self.redo_description.value = (
            self.undo_redo_manager.get_redo_description() or ""
        )
```

**UI обновления в [`acp-client/src/acp_client/tui/components/footer.py`](acp-client/src/acp_client/tui/components/footer.py:line)**:

```python
class EnhancedFooter(Footer):
    """Footer с поддержкой undo/redo"""
    
    def __init__(self, session_view_model):
        super().__init__()
        self.session_view_model = session_view_model
        
        # Подписаться на изменения undo/redo
        session_view_model.undo_description.subscribe(
            self._on_undo_description_changed
        )
        session_view_model.redo_description.subscribe(
            self._on_redo_description_changed
        )
    
    def _on_undo_description_changed(self, desc: str) -> None:
        """Когда изменилось описание undo"""
        self._update_footer()
    
    def render_footer(self) -> str:
        """Показать undo/redo в footer"""
        undo_hint = f" | Ctrl+Z: {self.session_view_model.undo_description.value}" if self.session_view_model.can_undo.value else ""
        redo_hint = f" | Ctrl+Y: {self.session_view_model.redo_description.value}" if self.session_view_model.can_redo.value else ""
        return f"Ctrl+K:commands | Ctrl+H:help{undo_hint}{redo_hint}"
```

#### Пример UI в TUI

```
Footer: Ctrl+K:commands | Ctrl+H:help | Ctrl+Z: Undo Create Session | Ctrl+Y: Redo Create Session
```

#### Метрики успеха
- ✅ Undo/Redo работает для всех критичных операций
- ✅ Footer показывает доступные undo/redo операции
- ✅ История ограничена 50 операциями
- ✅ История сохраняется между сессиями

---

### 2.2 Inline валидация и suggestions

#### Проблема
Пользователь не получает feedback при вводе prompt.
Нет подсказок при использовании команд.

#### Предложенное решение
Добавить валидацию и suggestion при вводе prompt:
- Length warning (если prompt > 4000 chars)
- Suggestion для известных команд
- Autocomplete для последних prompts

#### Технические детали

**Новый модуль: [`acp-client/src/acp_client/presentation/prompt_validation.py`](acp-client/src/acp_client/presentation/prompt_validation.py:line)**

```python
from dataclasses import dataclass
from enum import Enum

class ValidationLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class ValidationResult:
    level: ValidationLevel
    message: str
    suggestion: str | None = None

class PromptValidator:
    """Валидация prompt при вводе"""
    
    MAX_PROMPT_LENGTH = 4000
    WARNING_THRESHOLD = 3500
    
    @classmethod
    def validate(cls, prompt: str) -> list[ValidationResult]:
        """Валидировать prompt"""
        results = []
        
        # Проверка длины
        if len(prompt) > cls.MAX_PROMPT_LENGTH:
            results.append(ValidationResult(
                level=ValidationLevel.ERROR,
                message=f"Prompt too long: {len(prompt)}/{cls.MAX_PROMPT_LENGTH}",
                suggestion="Shorten your prompt or split into multiple prompts"
            ))
        elif len(prompt) > cls.WARNING_THRESHOLD:
            results.append(ValidationResult(
                level=ValidationLevel.WARNING,
                message=f"Prompt is getting long: {len(prompt)}/{cls.MAX_PROMPT_LENGTH}",
                suggestion="Consider shortening for better responses"
            ))
        
        # Проверка пустого prompt
        if not prompt.strip():
            results.append(ValidationResult(
                level=ValidationLevel.INFO,
                message="Prompt is empty",
            ))
        
        return results

class PromptSuggestions:
    """Suggestion для prompt при вводе"""
    
    def __init__(self, history: list[str]):
        self.history = history
    
    def get_suggestions(self, prefix: str) -> list[str]:
        """Получить suggestion для введенного prefix"""
        if not prefix.strip():
            # Показать последние prompts если пусто
            return self.history[-5:]
        
        # Найти prompts которые начинаются с prefix
        suggestions = [
            p for p in self.history
            if p.lower().startswith(prefix.lower())
        ]
        return suggestions[:5]  # Максимум 5 suggestion

# Интеграция в ViewModel
class PromptInputViewModel(BaseViewModel):
    """ViewModel для input с валидацией"""
    
    def __init__(self, prompt_validator, history):
        super().__init__()
        self.validator = prompt_validator
        self.suggestions = PromptSuggestions(history)
        
        self.prompt = Observable("")
        self.validation_results = Observable[list[ValidationResult]]([])
        self.suggestions_list = Observable[list[str]]([])
    
    def on_prompt_changed(self, new_prompt: str) -> None:
        """Когда пользователь меняет prompt"""
        self.prompt.value = new_prompt
        
        # Валидировать
        self.validation_results.value = self.validator.validate(new_prompt)
        
        # Получить suggestions
        self.suggestions_list.value = self.suggestions.get_suggestions(new_prompt)
```

**UI обновления в [`acp-client/src/acp_client/tui/components/prompt_input.py`](acp-client/src/acp_client/tui/components/prompt_input.py:line)**:

```python
class EnhancedPromptInput(PromptInput):
    """PromptInput с валидацией и suggestion"""
    
    def __init__(self, view_model):
        super().__init__()
        self.view_model = view_model
        
        # Подписаться на изменения
        view_model.validation_results.subscribe(self._on_validation_changed)
        view_model.suggestions_list.subscribe(self._on_suggestions_changed)
    
    def _on_validation_changed(self, results: list[ValidationResult]) -> None:
        """Когда изменилась валидация"""
        self._render_validation()
    
    def _render_validation(self) -> None:
        """Показать результаты валидации"""
        for result in self.view_model.validation_results.value:
            match result.level:
                case ValidationLevel.ERROR:
                    # Показать красный цвет + сообщение об ошибке
                    self._show_error(result.message)
                case ValidationLevel.WARNING:
                    # Показать желтый цвет + warning
                    self._show_warning(result.message)
                case ValidationLevel.INFO:
                    # Показать информационное сообщение
                    self._show_info(result.message)
    
    def _on_suggestions_changed(self, suggestions: list[str]) -> None:
        """Показать suggestion при вводе"""
        if suggestions:
            # Показать dropdown с suggestion
            self._show_suggestions_popup(suggestions)
    
    def on_key(self, event):
        """Обработка клавиш"""
        if event.key == "tab":
            # Tab для автодополнения suggestion
            suggestions = self.view_model.suggestions_list.value
            if suggestions:
                self.input.value = suggestions[0]
                event.prevent_default()
```

#### Пример UI в TUI

**With validation error**:
```
┌─────────────────────────────────────────────┐
│ > This is a very long prompt that exceeds  │
│   the maximum length limit of 4000 charact │
│   [❌ Prompt too long: 4100/4000]           │
│                                             │
│ Suggestion: Shorten your prompt or split   │
│ into multiple prompts                      │
└─────────────────────────────────────────────┘
```

**With suggestions**:
```
┌─────────────────────────────────────────────┐
│ > analyze code                              │
│ ┌─────────────────────────────────────────┐ │
│ │ ▶ analyze code structure                │ │
│ │ ▶ analyze performance issues            │ │
│ │ ▶ analyze security vulnerabilities      │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

#### Метрики успеха
- ✅ Валидация работает при каждом вводе
- ✅ Error показывается для слишком длинного prompt
- ✅ Warning показывается за 500 chars до лимита
- ✅ Suggestion показывается из истории

---

### 2.3 Поиск и фильтрация

#### Проблема
Пользователь не может быстро найти нужную информацию в больших логах.

#### Предложенное решение
Добавить встроенный поиск в основные компоненты:
- Поиск по сообщениям в ChatView
- Фильтрация tool calls в ToolPanel
- Поиск в TerminalOutput

#### Технические детали

**Новый модуль: [`acp-client/src/acp_client/presentation/search_filter.py`](acp-client/src/acp_client/presentation/search_filter.py:line)**

```python
from dataclasses import dataclass
from typing import Generic, TypeVar
from datetime import datetime

T = TypeVar('T')

@dataclass
class SearchResult(Generic[T]):
    item: T
    match_position: int
    match_length: int
    score: float  # Релевантность (0-1)

class SearchEngine(Generic[T]):
    """Поиск по элементам с нечетким совпадением"""
    
    @staticmethod
    def fuzzy_search(query: str, items: list[str]) -> list[SearchResult[str]]:
        """Нечеткий поиск (как в VS Code)"""
        results = []
        
        for item in items:
            score = SearchEngine._calculate_score(query, item)
            if score > 0:
                pos = item.lower().find(query.lower())
                results.append(SearchResult(
                    item=item,
                    match_position=pos if pos >= 0 else 0,
                    match_length=len(query),
                    score=score
                ))
        
        # Отсортировать по релевантности
        return sorted(results, key=lambda r: r.score, reverse=True)
    
    @staticmethod
    def _calculate_score(query: str, text: str) -> float:
        """Вычислить score релевантности"""
        # Просто - совпадение по началу слова выше чем в конце
        text_lower = text.lower()
        query_lower = query.lower()
        
        if query_lower in text_lower:
            return 1.0 - (text_lower.find(query_lower) / len(text_lower)) * 0.5
        
        return 0.0

# Интеграция в ViewModels
class ChatViewModelWithSearch(ChatViewModel):
    """ChatViewModel с поиском"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.search_query = Observable("")
        self.search_results = Observable[list[Message]]([])
        self.search_index = Observable(0)
        
        # Подписаться на изменения search query
        self.search_query.subscribe(self._on_search_query_changed)
    
    def _on_search_query_changed(self, query: str) -> None:
        """Когда пользователь меняет search query"""
        if not query:
            self.search_results.value = []
            return
        
        # Найти сообщения которые содержат query
        messages_text = [m.content for m in self.messages.value]
        search_results = SearchEngine.fuzzy_search(query, messages_text)
        
        # Преобразовать обратно в сообщения
        matched_messages = [
            next(m for m in self.messages.value if m.content == sr.item)
            for sr in search_results
        ]
        self.search_results.value = matched_messages
```

#### Пример UI в TUI

**Search in ChatView (Ctrl+F)**:
```
┌──────────────────────────────────────────────┐
│ Chat                                         │
│                                              │
│ User: Analyze the code structure             │
│ [↑2/5↓] Search: analyze ________________     │
│                                              │
│ [Highlighted] Analyze the code structure    │
│                                              │
│ Assistant: I'll [Highlighted] analyze...    │
│                                              │
│ [User searching...] (2 matches found)       │
└──────────────────────────────────────────────┘
```

#### Метрики успеха
- ✅ Поиск в ChatView находит сообщения за <100ms
- ✅ Фильтрация ToolPanel по типу (успешные/ошибки)
- ✅ Поиск в TerminalOutput с highlight
- ✅ Навигация по результатам поиска (Up/Down)

---

## Технические рекомендации

### Изменения в архитектуре

#### 1. Новый слой в Presentation

```python
# presentation/ui_state.py - глобальное состояние UI
class UIState:
    """Глобальное состояние интерфейса"""
    
    current_view: Observable[ViewType]
    selected_session: Observable[Session | None]
    modal_stack: Observable[list[ModalType]]
    search_active: Observable[bool]
    undo_redo_state: Observable[UndoRedoState]
```

#### 2. Новые компоненты TUI

```
tui/components/
├── context_menu.py        # Контекстное меню
├── command_palette.py     # Command palette (Ctrl+K)
├── state_display.py       # Стандартные состояния
├── search_bar.py          # Search bar
├── suggestions_popup.py   # Suggestions dropdown
├── validation_display.py  # Inline валидация
└── undo_redo_display.py   # Undo/redo визуализация
```

#### 3. Новые ViewModels

```
presentation/
├── search_filter_view_model.py     # Search & filter
├── validation_view_model.py        # Inline validation
├── suggestions_view_model.py       # Suggestions engine
├── undo_redo_view_model.py        # Undo/redo manager
└── command_palette_view_model.py  # Command palette
```

### Новые компоненты

#### CommandPalette Component
- Показывается по Ctrl+K
- Поиск по всем командам
- Группировка по категориям
- Быстрый доступ без горячих клавиш

#### SearchBar Component
- Встроенный search в компоненты
- Highlight совпадений
- Навигация по результатам (Up/Down)
- Фильтрация результатов

#### ValidationDisplay Component
- Inline валидация при вводе
- Color coding (error/warning/info)
- Suggestion для исправления
- Real-time feedback

#### ContextMenu Component
- Right-click или Ctrl+Click для меню
- Динамический список действий
- Разные меню для разных элементов
- Keyboard navigate внутри меню

### Рефакторинг существующих компонентов

#### Footer
```python
# Добавить поддержку undo/redo индикаторов
# Показывать command palette при Ctrl+K
# Динамический tooltip для горячих клавиш
```

#### Sidebar
```python
# Добавить контекстное меню для сессий
# Поддержка drag-reorder (опционально)
# Быстрое создание/удаление через меню
```

#### ChatView
```python
# Добавить встроенный search (Ctrl+F)
# Фильтрация сообщений (user/assistant/system)
# Highlight новых сообщений
# Lazy loading для больших историй
```

#### ToolPanel
```python
# Фильтрация по типу (всё/успешные/ошибки)
# Expand/collapse отдельных tool calls
# Timeline view для видения прогресса
# Copy result кнопка
```

### Зависимости

Новых зависимостей **НЕ требуется**:
- Search engine — реализовать самостоятельно (fuzzy matching)
- Undo/Redo — Command pattern из stdlib
- Validation — dataclasses + Pydantic (уже есть)
- Command palette — встроено в Textual

---

## Метрики успеха

### Фаза 1: Критичные улучшения

| Метрика | Целевое значение | Как измерять |
|---------|-----------------|-------------|
| Информационная архитектура | ChatView 70% экрана | UI layout inspection |
| Command palette | Все 20+ команды в палитре | Открыть Ctrl+K и проверить |
| Context menus | 4+ контекстных меню | Тестирование UI |
| Loading states | 100% async операций имеют state | Code review |
| Empty states | 5+ empty состояний | UI inspection |
| Error handling | Все errors показаны пользователю | Manual testing |

### Фаза 2: Важные улучшения

| Метрика | Целевое значение | Как измерять |
|---------|-----------------|-------------|
| Undo/Redo | Работает для 5+ операций | Integration tests |
| Inline validation | <100ms на каждый ввод | Performance testing |
| Suggestions | Точность >80% | User testing |
| Search performance | <100ms для 1000 элементов | Benchmark |
| Filter operations | 3+ фильтров на компонент | Feature testing |

### Фаза 3 & 4: Продвинутые & Полировка

| Метрика | Целевое значение | Как измерять |
|---------|-----------------|-------------|
| Plugin API | 5+ hook points | API documentation |
| Customization | 10+ settings | Config inspection |
| Animation performance | 60 FPS | Performance profiling |
| Accessibility | WCAG 2.1 AA | a11y audit |

### User Experience Метрики

#### Опросы пользователей
- **Ease of use**: 1-5 (целевое 4.5+)
- **Feature discovery**: 1-5 (целевое 4.0+)
- **Performance**: 1-5 (целевое 4.5+)
- **Customization**: 1-5 (целевое 4.0+)

#### Поведенческие метрики
- **Time to first action**: <30 сек (целевое <20 сек)
- **Commands discovered**: Из 20 команд, пользователь должен узнать про 15+ (целевое 75%+)
- **Error recovery**: % успешных попыток после ошибки (целевое 80%+)
- **Feature usage**: % пользователей использующих search (целевое 60%+)

---

## Риски и митигация

### 1. Риск: Complexity Overload

**Описание**: Добавление слишком много новых функций может перегрузить пользователя.

**Вероятность**: Средняя  
**Влияние**: Высокое  

**Митигация**:
- ✅ Реализовать поэтапно (4 фазы)
- ✅ User testing после каждой фазы
- ✅ Фокусироваться на удаляемости старых горячих клавиш
- ✅ Оставить простой mode для новичков

### 2. Риск: Performance Degradation

**Описание**: Добавление search, undo/redo может замедлить приложение.

**Вероятность**: Средняя  
**Влияние**: Высокое  

**Митигация**:
- ✅ Профилировать на каждой фазе
- ✅ Ограничить историю (50 операций для undo)
- ✅ Lazy loading для больших списков
- ✅ Кэширование результатов поиска

### 3. Риск: Breaking Changes

**Описание**: Рефакторинг компонентов может сломать существующие тесты.

**Вероятность**: Высокая  
**Влияние**: Среднее  

**Митигация**:
- ✅ Все тесты должны быть обновлены вместе с компонентом
- ✅ Использовать feature flags для постепенного rollout
- ✅ Сохранить backward compatibility где возможно
- ✅ Документировать breaking changes

### 4. Риск: Insufficient Testing

**Описание**: Новые компоненты могут не быть достаточно протестированы.

**Вероятность**: Средняя  
**Влияние**: Высокое  

**Митигация**:
- ✅ Требование покрытия >80% для новых компонентов
- ✅ MVVM тесты для каждого компонента
- ✅ Integration тесты для critical workflows
- ✅ User acceptance testing перед release

### 5. Риск: Keyboard Shortcut Conflicts

**Описание**: Новые горячие клавиши могут конфликтовать с существующими.

**Вероятность**: Низкая  
**Влияние**: Среднее  

**Митигация**:
- ✅ Документировать все горячие клавиши в одном месте
- ✅ Добавить возможность переопределения горячих клавиш
- ✅ Command palette как альтернатива горячим клавишам
- ✅ Проверка конфликтов при добавлении новой команды

### 6. Риск: Scope Creep

**Описание**: План может расширяться за пределы определенных фаз.

**Вероятность**: Высокая  
**Влияние**: Среднее  

**Митигация**:
- ✅ Четкое определение scope для каждой фазы
- ✅ Regular review meetings для оценки прогресса
- ✅ Prioritization backlog для новых идей
- ✅ Time-boxing для каждой фазы

---

## Заключение

### Резюме

Этот план улучшения UI/UX acp-client направлен на:

1. **Улучшение информационной архитектуры** — четкая иерархия и легкая навигация
2. **Снижение когнитивной нагрузки** — command palette и контекстные меню вместо запоминания
3. **Лучший feedback** — явные состояния loading, empty, error
4. **Расширение функциональности** — undo/redo, search, suggestions
5. **Подготовка к расширяемости** — plugin система, кастомизация

### Приоритизация

**Фаза 1** (критичные) дает максимальную пользу при минимальных усилиях и может быть реализована за 1-2 недели.

**Фаза 2** (важные) расширяет функциональность для опытных пользователей.

**Фазы 3-4** (продвинутые и полировка) готовят приложение к долгосрочному использованию и расширению.

### Следующие шаги

1. ✅ **Обсуждение** этого плана с командой
2. ✅ **Выбор приоритета** — какие части Фазы 1 реализовать первыми
3. ✅ **Прототипирование** — создать быстрый прототип для user feedback
4. ✅ **User research** — собрать feedback от целевой аудитории
5. ✅ **Реализация** — начать с Фазы 1
6. ✅ **Testing** — MVVM и integration тесты для каждого компонента
7. ✅ **Deployment** — постепенный rollout с feature flags

---

## Приложения

### A. Горячие клавиши (Новые + Существующие)

```
СЕССИИ
├─ Ctrl+N         Новая сессия
├─ Ctrl+J/K       Переключение сессий
├─ Ctrl+S/B       Фокус на список сессий
└─ Ctrl+Del       Контекстное меню сессии

НАВИГАЦИЯ
├─ Tab            Циклическое переключение фокуса
├─ Ctrl+K         Command palette (NEW)
├─ Ctrl+H         Встроенная справка (улучшенная)
└─ Ctrl+Shift+F   Global search (NEW)

СОДЕРЖИМОЕ
├─ Ctrl+Enter     Отправить prompt
├─ Ctrl+L         Очистить чат
├─ Ctrl+F         Поиск в текущем компоненте (NEW)
├─ Ctrl+T         Toggle plan/tools (NEW)
└─ Up/Down        История prompt

ФАЙЛЫ
├─ Ctrl+Click     Контекстное меню файла (NEW)
├─ Enter          Открыть файл
└─ F3/Shift+F3    Поиск в файле

РЕДАКТИРОВАНИЕ
├─ Ctrl+Z         Undo (NEW)
├─ Ctrl+Y         Redo (NEW)
├─ Ctrl+C         Cancel
└─ Ctrl+R         Retry

ВЫХОД
└─ Ctrl+Q         Выход
```

### B. Глоссарий терминов

| Термин | Определение |
|--------|-----------|
| **MVVM** | Model-View-ViewModel паттерн для разделения логики UI |
| **Observable** | Реактивное значение которое уведомляет подписчиков об изменениях |
| **ViewState** | Состояние компонента (loading, empty, error, normal) |
| **Command Palette** | Interface для поиска и выполнения команд |
| **Fuzzy Search** | Поиск с нечетким совпадением (как в VS Code) |
| **Undo/Redo** | Возможность отменить/повторить действия |
| **Context Menu** | Меню доступных действий по контексту |
| **Plugin API** | Интерфейс для расширения функциональности |

### C. Ссылки на документацию

- [`acp-client/ARCHITECTURE-LAYERS.md`](acp-client/ARCHITECTURE-LAYERS.md) — архитектура
- [`acp-client/README.md`](acp-client/README.md) — использование
- [`acp-client/DEVELOPING.md`](acp-client/DEVELOPING.md) — разработка
- [`acp-client/TESTING-STRATEGY.md`](acp-client/TESTING-STRATEGY.md) — тестирование

---

**Конец документа**

*Документ создан: 2026-04-09*  
*Версия: 1.0*  
*Статус: Готово к обсуждению*
