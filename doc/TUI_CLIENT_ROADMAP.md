# План разработки: ACP-Client TUI

**Версия:** 1.0  
**Дата:** 2026-04-08  
**Язык:** Русский

---

## Обзор

Детальный план разработки TUI-клиента для ACP-протокола, основанного на существующем acp-client и фреймворке Textual. План структурирован по этапам разработки с описанием задач, зависимостей и критериев готовности.

Принцип реализации: TUI внедряется как расширение текущего `acp-client`, без выделения в отдельный пакет или отдельный продукт.

## Статус реализации (факт)

Обновлено по текущему состоянию ветки разработки TUI.

### Уже реализовано

- [x] Базовый TUI-каркас (`Textual` app, layout, запуск через `--tui` и `acp-client-tui`)
- [x] Компоненты MVP: `HeaderBar`, `Sidebar`, `ChatView`, `PromptInput`, `FooterBar`, `ToolPanel`, `PermissionModal`
- [x] Интеграция с ACP для основного цикла: `initialize`, `session/list`, `session/new`, `session/load`, `session/prompt`, `session/cancel`
- [x] Session management в UI: создание, выбор и переключение сессий, replay при загрузке
- [x] Streaming отображение текста и `tool_call` / `tool_call_update` в правой панели
- [x] Permission-flow: модальное окно, выбор опции, отправка решения, hotkeys в модале
- [x] Reliability-блок: reconnect callbacks, offline/degraded статусы, retry queue, `Ctrl+R` retry операций
- [x] Персистентность UI-состояния: последняя активная сессия и черновик prompt
- [x] Hotkeys/navigation (актуальный набор): `Ctrl+S/B`, `Tab`, `Ctrl+N`, `Ctrl+J/K`, `Ctrl+L`, `Ctrl+H`, `Ctrl+C`, `Ctrl+Q`, `Ctrl+Enter`, `Ctrl+Up/Down`
- [x] Расширенное покрытие unit-тестами для TUI-слоя

### Остается по roadmap

- [ ] `PlanPanel` и визуализация `plan`-апдейтов
- [ ] Интеграция файловой системы (`FileTree`, `filesystem` manager, file viewer)
- [ ] Интеграция терминала (`terminal` manager, streaming output panel, lifecycle)
- [ ] `PermissionManager` с persistent policy (`allow always` / auto-apply / reset)
- [ ] Полная `UIStateMachine` + history cache + config manager
- [ ] Отдельные TUI integration/e2e/performance тесты
- [ ] Полный пакет пользовательской и developer-документации (`TUI.md`, `HOTKEYS.md`, `TROUBLESHOOTING.md`, `docs/TUI_API.md`)

---

## Этап 1: Подготовка и инфраструктура (Foundational)

**Цель:** Подготовить проект к разработке TUI компонентов

**Зависимости:** Нет (стартовый этап)

**Критерий готовности:**
- [x] Структура проекта создана и согласована
- [x] Зависимости добавлены (textual, rich)
- [x] Базовое приложение Textual запускается
- [ ] CI/CD настроена
- [x] Документация README обновлена

### Задача 1.1: Подготовка структуры проекта

**Описание:** Создать директорию `acp_client/tui/` и файловую структуру для компонентов

**Файлы для создания:**
```
acp-client/src/acp_client/tui/
├── __init__.py
├── app.py              # Main Textual application
├── components/
│   ├── __init__.py
│   ├── header.py       # HeaderBar компонент
│   ├── sidebar.py      # Sidebar с сессиями и файлами
│   ├── chat_view.py    # ChatView - главная область
│   ├── prompt_input.py # PromptInput field
│   ├── footer.py       # FooterBar
│   ├── tool_panel.py   # ToolCallPanel
│   └── permission_modal.py
├── managers/
│   ├── __init__.py
│   ├── session.py      # SessionManager
│   ├── connection.py   # ACPConnectionManager
│   ├── ui_state.py     # UI State machine
│   └── handlers.py     # Message handlers
├── styles/
│   └── app.tcss        # Textual CSS
└── utils.py            # Утилиты
```

**Технические работы:**
- [x] Создать структуру директорий
- [x] Инициализировать `__init__.py` файлы
- [x] Добавить тип-хинты и docstrings
- [ ] Добавить `.gitignore` для TUI модуля

**Оценка сложности:** Низкая

---

### Задача 1.2: Зависимости и конфигурация

**Описание:** Добавить Textual и Rich в зависимости, обновить pyproject.toml

**Файлы для изменения:**
- `acp-client/pyproject.toml`

**Технические работы:**
- [x] Добавить `textual>=0.30.0`
- [x] Добавить `rich>=13.0.0` (если еще не добавлена)
- [ ] Добавить `pydantic>=2.0.0` (для валидации)
- [x] Обновить `uv.lock`
- [ ] Проверить совместимость версий

**Оценка сложности:** Низкая

---

### Задача 1.3: Базовое приложение Textual

**Описание:** Создать минимальное рабочее Textual приложение с корректной структурой

**Файл:** `acp_client/tui/app.py`

**Код:**
```python
from textual.app import ComposeResult, App
from textual.containers import Container

class ACPClientApp(App):
    """Main TUI application для ACP-Client."""
    
    TITLE = "ACP-Client"
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
    ]
    
    def compose(self) -> ComposeResult:
        """Compose layout components."""
        yield Container()  # Placeholder
```

**Технические работы:**
- [x] Создать базовый класс ACPClientApp
- [x] Определить BINDINGS
- [x] Реализовать базовый compose()
- [x] Добавить логирование
- [x] Создать entry point в `__main__.py`

**Оценка сложности:** Низкая

---

### Задача 1.4: Настройка CI/CD и тестирования

**Описание:** Обновить CI/CD для запуска тестов TUI модуля

**Файлы для изменения:**
- `Makefile`
- `.github/workflows/` (если используется)

**Технические работы:**
- [ ] Добавить правило `make check-tui` для lint/tests
- [ ] Настроить pytest для TUI тестов
- [ ] Добавить `ty check` для TUI модулей
- [ ] Проверить ruff конфигурацию

**Оценка сложности:** Низкая

---

## Этап 2: Основной UI каркас (Core UI Skeleton)

**Цель:** Создать базовый макет и структуру UI без функционала

**Зависимости:** Этап 1

**Критерий готовности:**
- [x] Трехзонный макет работает (sidebar, main, footer)
- [x] Компоненты загружаются без ошибок
- [x] Горячие клавиши обрабатываются базово
- [x] Темы применяются корректно

### Задача 2.1: Стили и темы (CSS для Textual)

**Описание:** Определить Textual CSS (TCSS) для всех компонентов

**Файл:** `acp_client/tui/styles/app.tcss`

**Содержание:**
```tcss
Screen {
    layout: grid;
    grid-size: 3 3;
    background: $surface;
    color: $text;
}

#header {
    column-span: 3;
    height: 1;
    background: $boost;
    border: solid $accent;
}

#sidebar {
    width: 30;
    row-span: 2;
    background: $panel;
    border: solid $accent;
}

#main-area {
    column-span: 2;
    row-span: 2;
    background: $surface;
}

#footer {
    column-span: 3;
    height: 3;
    background: $boost;
    border: solid $accent;
}

#chat-view {
    overflow: auto;
    background: $surface;
}

#prompt-input {
    height: 3;
    border: solid $accent;
}
```

**Технические работы:**
- [ ] Определить цветовую схему (light/dark)
- [ ] Стилизировать основные компоненты
- [ ] Определить размеры панелей
- [ ] Добавить граница и отступы

**Оценка сложности:** Средняя

---

### Задача 2.2: HeaderBar компонент

**Описание:** Верхняя панель с информацией о приложении

**Файл:** `acp_client/tui/components/header.py`

**Функциональность:**
- Название приложения "ACP-Client"
- Версия
- Статус соединения (позже)

**Технические работы:**
- [x] Создать HeaderBar класс
- [x] Реализовать базовый рендер
- [x] Добавить версию из `__version__`
- [x] Стилизировать с CSS

**Оценка сложности:** Низкая

---

### Задача 2.3: Sidebar компонент (структура)

**Описание:** Левая панель с сессиями и файловым деревом (без функционала)

**Файл:** `acp_client/tui/components/sidebar.py`

**Компоненты:**
- SessionList (виджет Textual)
- FileTreeWidget (DirectoryTree или custom)

**Технические работы:**
- [x] Создать Sidebar контейнер
- [x] Добавить SessionList placeholder
- [ ] Добавить FileTree placeholder
- [ ] Реализовать переключение между разделами
- [x] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 2.4: ChatView компонент (структура)

**Описание:** Основная область для отображения сообщений (без streaming)

**Файл:** `acp_client/tui/components/chat_view.py`

**Функциональность:**
- ScrollableContainer с историей сообщений
- Placeholder для сообщений

**Технические работы:**
- [x] Создать ChatView класс
- [x] Реализовать ScrollableContainer
- [x] Добавить метод `add_message()`
- [x] Стилизировать область сообщений

**Оценка сложности:** Средняя

---

### Задача 2.5: PromptInput компонент

**Описание:** Поле ввода промпта в footer

**Файл:** `acp_client/tui/components/prompt_input.py`

**Функциональность:**
- Многострочный TextArea
- Ctrl+Enter для отправки
- Базовая история (↑/↓)

**Технические работы:**
- [x] Создать PromptInput класс
- [x] Использовать TextArea виджет
- [x] Реализовать submit обработку
- [x] Добавить history navigation
- [x] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 2.6: FooterBar компонент

**Описание:** Нижняя панель со статусом и подсказками

**Файл:** `acp_client/tui/components/footer.py`

**Функциональность:**
- Статус соединения
- Текущая сессия
- Подсказки по клавишам

**Технические работы:**
- [x] Создать FooterBar класс
- [x] Добавить статус-виджеты
- [x] Реализовать обновление статуса
- [x] Добавить hints для горячих клавиш
- [x] Стилизировать

**Оценка сложности:** Низкая

---

### Задача 2.7: Интеграция компонентов в App

**Описание:** Собрать все компоненты в главном приложении

**Файл:** `acp_client/tui/app.py`

**Технические работы:**
- [x] Импортировать все компоненты
- [x] Реализовать compose() с полной структурой
- [x] Настроить grid layout
- [x] Добавить горячие клавиши (action_* методы)
- [x] Тестировать структуру (без функционала)

**Оценка сложности:** Средняя

---

## Этап 3: Интеграция ACP протокола (ACP Integration)

**Цель:** Подключить WebSocket, инициализацию и обработку сообщений

**Зависимости:** Этап 1, Этап 2

**Критерий готовности:**
- [x] ACPConnectionManager работает
- [x] Initialize handshake успешен
- [x] Session/list работает
- [x] Сообщения логируются корректно

### Задача 3.1: ConnectionManager

**Описание:** Менеджер для WebSocket соединения с сервером

**Файл:** `acp_client/tui/managers/connection.py`

**Функциональность:**
```python
class ACPConnectionManager:
    async def connect(host: str, port: int) -> None:
        """Подключиться к серверу."""
    
    async def initialize() -> InitializeResult:
        """Выполнить initialize."""
    
    async def send_request(method: str, params: dict) -> dict:
        """Отправить request и ждать response."""

    async def enqueue_request(method: str, params: dict) -> None:
        """Поставить request в очередь при разрыве соединения."""
    
    async def on_update(callback) -> None:
        """Получать session/update уведомления."""
```

**Технические работы:**
- [x] Использовать существующий `ACPClient` из acp-client
- [x] Обернуть в менеджер для TUI
- [x] Реализовать автопереподключение
- [ ] Добавить очередь запросов на время reconnect
- [x] Добавить логирование
- [x] Обработать ошибки

**Оценка сложности:** Средняя

---

### Задача 3.2: SessionManager

**Описание:** Менеджер для работы с сессиями

**Файл:** `acp_client/tui/managers/session.py`

**Функциональность:**
```python
class SessionManager:
    async def list_sessions() -> list[SessionListItem]:
        """Получить список сессий."""
    
    async def create_session(cwd: str) -> str:
        """Создать новую сессию."""
    
    async def load_session(session_id: str) -> None:
        """Загрузить существующую сессию."""
    
    def get_active_session() -> SessionState:
        """Получить активную сессию."""
```

**Технические работы:**
- [x] Использовать helpers из acp-client
- [x] Кэшировать список сессий
- [x] Синхронизировать с UI
- [x] Обработать ошибки

**Оценка сложности:** Средняя

---

### Задача 3.3: Message Handlers

**Описание:** Обработчики для различных типов ACP сообщений

**Файл:** `acp_client/tui/managers/handlers.py`

**Функциональность:**
```python
class UpdateMessageHandler:
    """Обработка session/update уведомлений."""
    
    async def handle_agent_message_chunk(chunk: dict) -> None:
        """Текст от агента."""
    
    async def handle_tool_call(tool_call: dict) -> None:
        """Tool call начался."""
    
    async def handle_tool_call_update(update: dict) -> None:
        """Обновление tool call."""
    
    async def handle_plan(plan: dict) -> None:
        """План выполнения."""
```

**Технические работы:**
- [x] Использовать обработчики из acp-client/handlers
- [x] Добавить callback-методы для UI обновления
- [x] Логировать события
- [x] Обработать ошибки и edge cases

**Оценка сложности:** Средняя

---

### Задача 3.4: Тестирование инициализации

**Описание:** Убедиться, что клиент успешно инициализируется с сервером

**Файл:** `acp-client/tests/test_tui_connection.py`

**Технические работы:**
- [x] Создать тесты для ConnectionManager
- [x] Тестировать initialize
- [x] Тестировать session/list
- [x] Тестировать обработку ошибок

**Оценка сложности:** Средняя

---

## Этап 4: Управление сессиями в UI (Session Management UI)

**Цель:** Реализовать создание, загрузку и переключение сессий в интерфейсе

**Зависимости:** Этап 2, Этап 3

**Критерий готовности:**
- [x] Список сессий отображается
- [x] Новую сессию можно создать
- [x] Сессии можно переключать
- [x] Изменения синхронизируются с сервером

### Задача 4.1: SessionListWidget

**Описание:** Виджет для отображения списка сессий в sidebar

**Файл:** `acp_client/tui/components/session_list.py`

**Функциональность:**
- Список сессий с ID и title
- Выделение активной сессии
- Двойной клик для переключения
- Кнопка "+ New"

**Технические работы:**
- [ ] Создать SessionListWidget (на основе Textual DataTable или ListView)
- [ ] Реализовать метод `populate_sessions()`
- [ ] Добавить event handlers
- [ ] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 4.2: SessionManager обновления

**Описание:** Расширить SessionManager для синхронизации с UI

**Файл:** `acp_client/tui/managers/session.py`

**Функциональность:**
- Callback для обновления списка
- Callback для переключения сессии
- Callback для создания сессии

**Технические работы:**
- [ ] Добавить callback регистрацию
- [ ] Реализовать синхронизацию
- [ ] Обработить ошибки

**Оценка сложности:** Низкая

---

### Задача 4.3: Интеграция SessionListWidget с UI

**Описание:** Вставить SessionListWidget в Sidebar и подключить обработчики

**Файл:** `acp_client/tui/components/sidebar.py`

**Технические работы:**
- [ ] Заменить placeholder на SessionListWidget
- [x] Подключить SessionManager callbacks
- [x] Обновлять UI при изменении сессий
- [x] Обработать ошибки

**Оценка сложности:** Средняя

---

### Задача 4.4: Действия создания и загрузки сессии

**Описание:** Реализовать диалоги для создания новой сессии

**Файл:** `acp_client/tui/components/dialogs.py` (новый файл в составе `acp-client`)

**Функциональность:**
- Dialog для выбора рабочей директории
- Dialog для выбора сессии (при load)

**Технические работы:**
- [ ] Создать NewSessionDialog
- [ ] Создать LoadSessionDialog
- [ ] Интегрировать в приложение
- [ ] Тестировать

**Оценка сложности:** Средняя

---

### Задача 4.5: Удаление сессии

**Описание:** Реализовать удаление сессии с подтверждением, если операция поддерживается сервером

**Файлы для изменения:**
- `acp_client/tui/managers/session.py`
- `acp_client/tui/components/dialogs.py`

**Технические работы:**
- [ ] Проверить capability удаления сессии
- [ ] Добавить действие удаления в SessionListWidget
- [ ] Показать confirm-dialog перед удалением
- [ ] Обновить список сессий после успешного удаления

**Оценка сложности:** Средняя

---

## Этап 5: Вывод сообщений и streaming (Message Display & Streaming)

**Цель:** Реализовать отображение сообщений от агента с поддержкой streaming

**Зависимости:** Этап 2, Этап 3, Этап 4

**Критерий готовности:**
- [x] Сообщения отображаются в ChatView
- [x] Streaming текст выводится посимвольно
- [ ] Markdown рендеризуется
- [ ] Синтаксис-подсветка работает

### Задача 5.1: Message Block компоненты

**Описание:** Компоненты для отображения user и agent сообщений

**Файл:** `acp_client/tui/components/message_blocks.py` (новый файл в составе `acp-client`)

**Функциональность:**
```python
class UserMessageBlock(Static):
    """Блок для пользовательского сообщения."""

class AgentMessageBlock(Static):
    """Блок для сообщения агента с streaming."""
```

**Технические работы:**
- [ ] Создать UserMessageBlock
- [ ] Создать AgentMessageBlock
- [ ] Реализовать markdown рендеринг (Rich)
- [ ] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 5.2: Streaming текста в ChatView

**Описание:** Реализовать посимвольный вывод текста от агента

**Файл:** `acp_client/tui/components/chat_view.py`

**Функциональность:**
```python
async def stream_message(text: str) -> None:
    """Потоковый вывод текста."""
```

**Технические работы:**
- [x] Реализовать stream логику
- [x] Обновлять UI без блокировки
- [x] Обработать отмену (Ctrl+C)
- [x] Оптимизировать для производительности

**Оценка сложности:** Средняя

---

### Задача 5.3: Отправка промпта

**Описание:** Реализовать отправку prompt на сервер из UI

**Файл:** `acp_client/tui/components/prompt_input.py`

**Функциональность:**
- Отправка текста как session/prompt
- Вложение файла как контекста (ContentBlock::Resource)
- Поддержка вложений изображений при наличии capability сервера
- Очистка поля после отправки
- Добавление в историю

**Технические работы:**
- [x] Подключить SessionManager.send_prompt()
- [x] Реализовать обработку response
- [x] Добавить индикатор отправки
- [ ] Добавить валидацию вложений и graceful fallback
- [x] Обработать ошибки

**Оценка сложности:** Средняя

---

### Задача 5.4: Обработка session/update notifications

**Описание:** Подключить UpdateMessageHandler к ChatView

**Файл:** `acp_client/tui/managers/handlers.py`

**Технические работы:**
- [x] Подписать ChatView на session/update
- [x] Маршрутизировать updates на правильные обработчики
- [ ] Обработать `available_commands_update` и синхронизировать slash-команды
- [x] Обновлять UI синхронно

**Оценка сложности:** Средняя

---

## Этап 6: Отслеживание инструментов (Tool Calls Tracking)

**Цель:** Реализовать визуализацию выполнения инструментов с иконками и статусами

**Зависимости:** Этап 5

**Критерий готовности:**
- [ ] Tool calls отображаются с иконками
- [x] Статусы обновляются в реальном времени
- [ ] Инструменты можно раскрывать/свертывать
- [ ] Контент инструмента отображается

### Задача 6.1: ToolCallPanel компонент

**Описание:** Компонент для отображения одного tool call

**Файл:** `acp_client/tui/components/tool_panel.py`

**Функциональность:**
```python
class ToolCallPanel(Static):
    """Панель для одного tool call."""
    
    def update_status(status: str, content: list = None) -> None:
        """Обновить статус и контент."""
```

**Технические работы:**
- [ ] Создать ToolCallPanel класс
- [ ] Реализовать иконки для разных kind (read, write, execute и т.д.)
- [ ] Реализовать раскрытие/свертывание
- [ ] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 6.2: Обработка tool_call updates

**Описание:** Получать tool_call уведомления и обновлять UI

**Файл:** `acp_client/tui/managers/handlers.py`

**Технические работы:**
- [x] Добавить callback для tool_call
- [x] Добавить callback для tool_call_update
- [x] Синхронизировать с ChatView
- [x] Обновлять статусы

**Оценка сложности:** Средняя

---

### Задача 6.3: PlanPanel компонент

**Описание:** Отображение плана выполнения

**Файл:** `acp_client/tui/components/plan_panel.py` (новый файл в составе `acp-client`)

**Функциональность:**
- Список пунктов плана
- Статусы (pending, in_progress, completed)
- Визуальный прогресс

**Технические работы:**
- [ ] Создать PlanPanel
- [ ] Реализовать обновление пунктов
- [ ] Стилизировать
- [ ] Добавить в ChatView

**Оценка сложности:** Средняя

---

## Этап 7: Интеграция файловой системы (File System Integration)

**Цель:** Реализовать обработку fs/* запросов от сервера и навигацию по файлам

**Зависимости:** Этап 3, Этап 4

**Критерий готовности:**
- [ ] DirectoryTree отображается в sidebar
- [ ] fs/read_text_file обрабатывается
- [ ] fs/write_text_file обрабатывается
- [ ] Файлы можно просматривать

### Задача 7.1: FileTree компонент

**Описание:** Дерево файлов в sidebar

**Файл:** `acp_client/tui/components/file_tree.py` (новый файл в составе `acp-client`)

**Функциональность:**
- DirectoryTree для структуры проекта
- Фильтрация .gitignore
- Двойной клик для открытия файла

**Технические работы:**
- [ ] Использовать Textual DirectoryTree
- [ ] Реализовать обработчики eventos
- [ ] Фильтровать файлы
- [ ] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 7.2: FileSystemManager

**Описание:** Обработчик для fs/* операций (из acp-client)

**Файл:** `acp_client/tui/managers/filesystem.py` (новый файл в составе `acp-client`)

**Функциональность:**
```python
class LocalFileSystemManager:
    async def read_file(path: str, line: int = None, limit: int = None) -> str:
        """fs/read_text_file."""
    
    async def write_file(path: str, content: str) -> None:
        """fs/write_text_file."""
```

**Технические работы:**
- [ ] Использовать существующие handlers из acp-client
- [ ] Обернуть в менеджер
- [ ] Обработать ошибки
- [ ] Валидировать пути

**Оценка сложности:** Низкая

---

### Задача 7.3: File Viewer Modal

**Описание:** Модальное окно для просмотра файла

**Файл:** `acp_client/tui/components/file_viewer.py` (новый файл в составе `acp-client`)

**Функциональность:**
- Просмотр содержимого файла
- Синтаксис-подсветка
- Поиск в файле (Ctrl+F)
- Номера строк

**Технические работы:**
- [ ] Создать FileViewerModal
- [ ] Реализовать синтаксис-подсветку (Pygments)
- [ ] Добавить поиск
- [ ] Интегрировать с FileTree

**Оценка сложности:** Средняя

---

### Задача 7.4: Обновление UI при изменении файлов

**Описание:** Синхронизировать FileTree при изменениях от агента

**Файл:** `acp_client/tui/components/file_tree.py`

**Технические работы:**
- [ ] Отслеживать fs/write события
- [ ] Обновлять FileTree при создании файлов
- [ ] Добавить визуальный индикатор измененных файлов

**Оценка сложности:** Низкая

---

## Этап 8: Интеграция терминала (Terminal Integration)

**Цель:** Реализовать выполнение команд в терминале и streaming вывода

**Зависимости:** Этап 3, Этап 6

**Критерий готовности:**
- [ ] terminal/create обрабатывается
- [ ] Вывод терминала отображается в реальном времени
- [ ] terminal/kill работает
- [ ] Exit code отображается

### Задача 8.1: TerminalManager

**Описание:** Менеджер для управления терминальными процессами

**Файл:** `acp_client/tui/managers/terminal.py` (новый файл в составе `acp-client`)

**Функциональность:**
```python
class LocalTerminalManager:
    async def create_terminal(command: str, args: list, cwd: str) -> str:
        """terminal/create."""
    
    async def get_output(terminal_id: str) -> tuple[str, bool, int]:
        """terminal/output."""
    
    async def kill_terminal(terminal_id: str) -> bool:
        """terminal/kill."""

    async def wait_for_exit(terminal_id: str) -> tuple[str, bool, int]:
        """terminal/wait_for_exit."""

    async def release_terminal(terminal_id: str) -> bool:
        """terminal/release."""
```

**Технические работы:**
- [ ] Использовать handlers из acp-client
- [ ] Обернуть в менеджер
- [ ] Обработать ошибки
- [ ] Управление процессами (PTY на Linux/macOS)
- [ ] Реализовать жизненный цикл terminal: create/output/wait_for_exit/release

**Оценка сложности:** Средняя

---

### Задача 8.2: TerminalOutput компонент

**Описание:** Компонент для отображения вывода терминала в tool call

**Файл:** `acp_client/tui/components/terminal_output.py` (новый файл в составе `acp-client`)

**Функциональность:**
- Streaming вывода
- Поддержка ANSI цветов
- Прокрутка для больших выводов

**Технические работы:**
- [ ] Создать TerminalOutputPanel
- [ ] Реализовать ANSI rendering (Rich)
- [ ] Добавить прокрутку
- [ ] Стилизировать

**Оценка сложности:** Средняя

---

### Задача 8.3: Встраивание терминала в tool call

**Описание:** Отображать output терминала внутри ToolCallPanel

**Файл:** `acp_client/tui/components/tool_panel.py`

**Технические работы:**
- [ ] Добавить TerminalOutputPanel в ToolCallPanel
- [ ] Streaming обновления
- [ ] Отображение exit code

**Оценка сложности:** Низкая

---

## Этап 9: Управление разрешениями (Permissions & Human-in-the-Loop)

**Цель:** Реализовать запросы разрешений для критических операций

**Зависимости:** Этап 3, Этап 6

**Критерий готовности:**
- [x] Permission requests отображаются в модальном окне
- [x] Пользователь может выбрать вариант
- [x] Решение отправляется на сервер
- [ ] Политика разрешений работает

### Задача 9.1: PermissionModal компонент

**Описание:** Модальное окно для запроса разрешения

**Файл:** `acp_client/tui/components/permission_modal.py`

**Функциональность:**
```python
class PermissionModal(Modal):
    """Модальное окно для запроса разрешения."""
    
    async def handle_option(option_id: str) -> None:
        """Пользователь выбрал вариант."""
```

**Технические работы:**
- [x] Создать PermissionModal
- [x] Отображать опции как кнопки
- [x] Обработать выбор
- [x] Стилизировать (выделение для внимания)

**Оценка сложности:** Средняя

---

### Задача 9.2: PermissionManager

**Описание:** Менеджер для обработки permission requests

**Файл:** `acp_client/tui/managers/permission.py` (новый файл в составе `acp-client`)

**Функциональность:**
```python
class PermissionManager:
    async def request_permission(request: dict) -> dict:
        """Показать modal и вернуть результат."""
    
    def save_policy(kind: str, outcome: str) -> None:
        """Сохранить решение."""
    
    def get_policy(kind: str) -> str | None:
        """Получить сохраненное решение."""
```

**Технические работы:**
- [ ] Реализовать modal показ
- [ ] Сохранять политику в конфиг
- [ ] Применять политику автоматически
- [ ] Обработать отмену (session/cancel)

**Оценка сложности:** Средняя

---

### Задача 9.3: Интеграция с ACPClient

**Описание:** Подключить PermissionManager к обработчику permission requests

**Файл:** `acp_client/tui/managers/handlers.py`

**Технические работы:**
- [x] Обработать session/request_permission
- [x] Показать PermissionModal
- [x] Отправить результат на сервер
- [ ] Обработить timeout

**Оценка сложности:** Средняя

---

## Этап 10: Состояние и синхронизация (State Management)

**Цель:** Реализовать управление состоянием приложения и синхронизацию с сервером

**Зависимости:** Все предыдущие этапы

**Критерий готовности:**
- [ ] UI State Machine работает корректно
- [ ] История кэшируется локально
- [ ] Синхронизация работает при reconnect
- [ ] Все состояния обрабатываются

### Задача 10.1: UIStateMachine

**Описание:** State machine для управления состояниями UI

**Файл:** `acp_client/tui/managers/ui_state.py`

**Функциональность:**
```python
class UIStateMachine:
    """Управление состояниями UI."""
    
    states = {
        "initializing": ...,
        "ready": ...,
        "processing_prompt": ...,
        "waiting_permission": ...,
        "error": ...,
    }
    
    def transition(new_state: str) -> None:
        """Переход в новое состояние."""
```

**Технические работы:**
- [ ] Определить все состояния
- [ ] Реализовать transition логику
- [ ] Валидировать переходы
- [ ] Обновлять UI при переходе

**Оценка сложности:** Средняя

---

### Задача 10.2: History Caching

**Описание:** Локальное кэширование истории сообщений

**Файл:** `acp_client/tui/managers/cache.py` (новый файл в составе `acp-client`)

**Функциональность:**
```python
class HistoryCache:
    """Кэширование истории локально."""
    
    async def save_message(session_id: str, message: dict) -> None:
        """Сохранить сообщение."""
    
    async def load_history(session_id: str) -> list:
        """Загрузить историю сессии."""
```

**Технические работы:**
- [ ] Использовать JSON или SQLite для кэша
- [ ] Сохранять при каждом update
- [ ] Загружать при переключении сессии
- [ ] Обработать конфликты

**Оценка сложности:** Средняя

---

### Задача 10.3: Config Management

**Описание:** Управление конфигурацией приложения

**Файл:** `acp_client/tui/config.py` (новый файл в составе `acp-client`)

**Функциональность:**
- Хост/порт сервера
- Тема (light/dark)
- Автосохранение настроек

**Технические работы:**
- [ ] Использовать TOML для конфига
- [ ] Загружать при старте
- [ ] Сохранять изменения
- [ ] Использовать defaults

**Оценка сложности:** Низкая

---

## Этап 11: Горячие клавиши и навигация (Keybindings & Navigation)

**Цель:** Реализовать все горячие клавиши и навигацию между компонентами

**Зависимости:** Все предыдущие этапы

**Критерий готовности:**
- [ ] Все горячие клавиши из спецификации работают
- [x] Tab переключает между панелями
- [x] Focus управление работает

### Задача 11.1: Bindings в ACPClientApp

**Описание:** Определить все горячие клавиши

**Файл:** `acp_client/tui/app.py`

**Список (из спецификации):**
- Ctrl+N → new_session
- Ctrl+S → focus_session_list
- Ctrl+L → clear_chat
- Ctrl+C → cancel_prompt
- Tab → cycle_focus
- Enter → newline (в PromptInput)
- Ctrl+Enter → send_prompt (в PromptInput)
- ↑/↓ → history_navigation (в PromptInput)
- Ctrl+H → open_help
- Esc → close_modal
- Ctrl+Q → quit

**Технические работы:**
- [x] Добавить BINDINGS
- [x] Реализовать action_* методы
- [x] Тестировать все комбинации

**Оценка сложности:** Низкая

---

### Задача 11.2: Focus Management

**Описание:** Управление фокусом между компонентами

**Файл:** `acp_client/tui/app.py`

**Технические работы:**
- [x] Реализовать action_cycle_focus()
- [x] Определить порядок фокуса
- [ ] Визуализировать focus (highlight)

**Оценка сложности:** Низкая

---

## Этап 12: Тестирование и оптимизация (Testing & Optimization)

**Цель:** Убедиться в качестве и производительности

**Зависимости:** Все предыдущие этапы

**Критерий готовности:**
- [ ] Unit тесты покрывают >80% кода
- [ ] Integration тесты проходят
- [ ] Performance benchmarks в норме
- [ ] E2E тесты на реальном сервере

### Задача 12.1: Unit tests

**Описание:** Unit тесты для всех компонентов

**Файлы:** `acp-client/tests/test_tui_*.py`

**Технические работы:**
- [x] Тесты для managers
- [x] Тесты для компонентов
- [x] Тесты для handlers
- [ ] Минимум 80% coverage

**Оценка сложности:** Средняя

---

### Задача 12.2: Integration tests

**Описание:** Integration тесты с mock сервером

**Файл:** `acp-client/tests/test_tui_integration.py`

**Технические работы:**
- [ ] Создать mock ACP сервер
- [ ] Тестировать полный цикл
- [ ] Тестировать tool calls
- [ ] Тестировать permissions

**Оценка сложности:** Средняя

---

### Задача 12.3: Performance profiling

**Описание:** Профилирование и оптимизация производительности

**Файл:** `acp-client/tests/test_tui_performance.py`

**Технические работы:**
- [ ] Измерить startup time (< 500 мс на целевой машине)
- [ ] Измерить UI rendering chunk (< 50 мс)
- [ ] Измерить terminal update latency (< 100 мс/chunk)
- [ ] Измерить memory usage (в пределах лимитов спецификации)
- [ ] Оптимизировать узкие места

**Оценка сложности:** Средняя

---

### Задача 12.4: E2E tests

**Описание:** Сценарии на реальном сервере

**Файл:** `acp-client/tests/test_tui_e2e.py`

**Технические работы:**
- [ ] Tест создания сессии
- [ ] Тест отправки промпта
- [ ] Тест tool execution
- [ ] Тест permissions

**Оценка сложности:** Средняя

---

## Этап 13: Документация и полировка (Documentation & Polish)

**Цель:** Завершить разработку с полной документацией

**Зависимости:** Все предыдущие этапы

**Критерий готовности:**
- [x] README обновлен
- [ ] USAGE.md написан
- [ ] API документация полна
- [ ] Примеры работают

### Задача 13.1: User documentation

**Описание:** Руководство пользователя

**Файлы:**
- `acp-client/README.md` (обновить)
- `acp-client/TUI.md` (новый файл документации в `acp-client`)
- `acp-client/HOTKEYS.md` (новый файл документации в `acp-client`)

**Содержание:**
- Установка и требования
- Быстрый старт
- Использование компонентов
- Горячие клавиши
- Troubleshooting

**Технические работы:**
- [ ] Написать TUI.md
- [x] Обновить README
- [ ] Добавить примеры
- [ ] Добавить скриншоты (если возможно)

**Оценка сложности:** Низкая

---

### Задача 13.2: API documentation

**Описание:** Документация API для разработчиков

**Файл:** `acp-client/docs/TUI_API.md` (новый файл документации в `acp-client`)

**Содержание:**
- Architecture overview
- Component reference
- Manager reference
- Event flows

**Технические работы:**
- [ ] Написать TUI_API.md
- [ ] Добавить примеры использования
- [ ] Документировать все public API

**Оценка сложности:** Низкая

---

### Задача 13.3: Contributing guide

**Описание:** Гайд для контрибьюторов

**Файл:** `DEVELOPMENT.md` (обновить для TUI)

**Технические работы:**
- [ ] Добавить раздел о TUI разработке
- [ ] Описать архитектуру
- [ ] Объяснить как запустить в dev mode

**Оценка сложности:** Низкая

---

### Задача 13.4: Release и deployment

**Описание:** Подготовка к релизу

**Файлы:**
- `CHANGELOG.md`
- `pyproject.toml` (version bump)

**Технические работы:**
- [ ] Обновить version в pyproject.toml
- [ ] Обновить CHANGELOG
- [ ] Создать release notes
- [ ] Протестировать на всех платформах

**Оценка сложности:** Низкая

---

## Матрица зависимостей этапов

```
Этап 1: Foundational
    ↓
Этап 2: Core UI Skeleton
    ↓
├── Этап 3: ACP Integration
│   ├── Этап 4: Session Management UI
│   ├── Этап 5: Message Display
│   │   └── Этап 6: Tool Calls
│   │       └── Этап 8: Terminal
│   ├── Этап 7: File System
│   └── Этап 9: Permissions
    ├── Этап 10: State Management
    ├── Этап 11: Keybindings
    ├── Этап 12: Testing
    └── Этап 13: Documentation
```

---

## Оценка времени по этапам

| Этап | Задач | Оценка сложности | Критическая зависимость |
|------|--------|------------------|-------------------------|
| 1 | 4 | Низкая | Нет (стартовый) |
| 2 | 7 | Средняя | Этап 1 |
| 3 | 4 | Средняя | Этап 1, 2 |
| 4 | 5 | Средняя | Этап 2, 3 |
| 5 | 4 | Средняя | Этап 2, 3, 4 |
| 6 | 3 | Средняя | Этап 5 |
| 7 | 4 | Средняя | Этап 3, 4 |
| 8 | 3 | Средняя | Этап 3, 6 |
| 9 | 3 | Средняя | Этап 3, 6 |
| 10 | 3 | Средняя | Все предыдущие |
| 11 | 2 | Низкая | Все предыдущие |
| 12 | 4 | Средняя | Все предыдущие |
| 13 | 4 | Низкая | Все предыдущие |

**Итого задач:** 50

---

## Критерии готовности MVP

- [ ] Все задачи Этапов 1-9 завершены
- [ ] Тестирование Этапа 12 завершено (минимум E2E)
- [ ] Документация Этапа 13 базовая
- [ ] Приложение запускается и работает с реальным сервером
- [ ] Горячие клавиши работают (Этап 11)

---

## Критерии готовности v1.0 Release

- [ ] Все задачи всех этапов завершены
- [ ] Все тесты проходят
- [ ] Performance requirements удовлетворены
- [ ] Документация полна
- [ ] Release notes написаны
- [ ] Code review завершен
- [ ] Готово для PyPI

---

**Конец документа TUI_CLIENT_ROADMAP.md**
