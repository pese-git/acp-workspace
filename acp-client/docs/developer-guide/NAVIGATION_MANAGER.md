# NavigationManager: Управление навигацией в TUI

## Обзор

NavigationManager — это централизованное решение для управления навигацией в TUI приложении ACP Client. Решает критические проблемы с `ScreenStackError`, race conditions и рассинхронизацией состояния между ViewModel и UI.

**Проблемы до реализации:**
- `ScreenStackError` при одновременном закрытии модальных окон из разных источников
- Race conditions из-за отсутствия очереди операций навигации
- Рассинхронизация состояния ViewModels с реальным UI состоянием
- Отсутствие централизованного управления модальными окнами
- Невозможность управлять приоритетом операций навигации

**Решение:**
Интегрированная система из четырех компонентов с последовательным выполнением операций через приоритетную очередь, отслеживанием модальных окон и синхронизацией с ViewModels через Observable паттерн.

---

## Описание проблемы

### Текущие проблемы

#### ScreenStackError при закрытии модальных окон

```python
# Текущий код в FileViewerModal:
def _on_visibility_changed(self, is_visible: bool) -> None:
    if not is_visible:
        self.dismiss(None)  # ScreenStackError: попытка dismiss() модального окна,
                            # которого нет в стеке (race condition)
```

**Проблема:** Несколько потоков/task-ов могут одновременно вызывать `dismiss()`:
- Подписка на `ViewModel.is_visible` вызывает `dismiss()` асинхронно
- Пользователь нажимает Escape, что тоже вызывает `dismiss()`
- `app.pop_screen()` вызывается из app.py одновременно

#### Отсутствие централизованного управления

```python
# Навигация разбросана по коду:
# 1. app.py: self.push_screen(FileViewerModal(...))
# 2. file_viewer.py: self.dismiss(None) через Observable callback
# 3. app.py: self.push_screen_wait(...) для permission modal
# 4. permission_modal.py: self.dismiss(option_id) после выбора
```

**Проблема:** Гонки и двойные вызовы:
- Нет единой очереди операций
- Невозможно управлять приоритетами
- Сложно отследить состояние навигации
- Нет синхронизации между ViewModel и реальным UI

---

## Архитектурное решение

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    ACPClientApp (Textual)                   │
│  (главное приложение, управляет screen stack и mount)       │
└──────────────────────┬──────────────────────────────────────┘
                       │ использует
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    NavigationManager                         │
│  - Централизованное управление навигацией                   │
│  - Очередь операций для последовательного выполнения        │
│  - Синхронизация с ViewModels                               │
│  - Отслеживание модальных окон                              │
└──────────┬──────────────┬──────────────┬────────────────────┘
           │              │              │
           ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
    │OperationQ   │  │Modal        │  │Navigation    │
    │ueue         │  │WindowTracker│  │StateSync     │
    │             │  │             │  │              │
    │- FIFO       │  │- Registry   │  │- Subscriptions
    │- Prioritize │  │- Lookup     │  │- Transforms
    │- Sequential │  │- Cleanup    │  │- Prevents    │
    │- Error      │  │             │  │  cycles      │
    │  handling   │  │             │  │              │
    └─────────────┘  └─────────────┘  └──────────────┘
           ▲              ▲              ▲
           └──────────────┴──────────────┘
                 Используют
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
    ┌─────────────┐          ┌─────────────┐
    │ ViewModels  │          │Components   │
    │             │          │             │
    │- Notify of  │  ◄───┐   │- Render     │
    │  state      │      │   │- Handle     │
    │  changes    │      │   │  events     │
    │- Observable │      │   │- Push/Pop   │
    │  properties │      └───┤  screens    │
    └─────────────┘          └─────────────┘
```

---

## Реализованные компоненты

### 1. NavigationOperation и Enums

**Файл:** [`acp-client/src/acp_client/tui/navigation/operations.py`](../../src/acp_client/tui/navigation/operations.py)

Описание операций навигации и их параметров.

#### OperationType

Три типа операций:
- `SHOW_SCREEN` - показать экран или модальное окно
- `HIDE_SCREEN` - скрыть экран или модальное окно
- `RESET` - закрыть все модальные окна и вернуться в normal state

#### OperationPriority

Приоритеты операций (выше значение = выполнится раньше):
- `LOW = 0` - низкий приоритет
- `NORMAL = 1` - нормальный приоритет (по умолчанию)
- `HIGH = 2` - высокий приоритет

#### NavigationOperation

Frozen dataclass описывающий операцию навигации:

```python
from acp_client.tui.navigation import NavigationOperation, OperationType

# Пример создания операции показа экрана
operation = NavigationOperation(
    operation_type=OperationType.SHOW_SCREEN,
    screen=my_screen,
    modal=False,
    priority=1,
    on_success=lambda: print("Screen shown"),
    metadata={"screen_class": "MyScreen"}
)
```

---

### 2. OperationQueue

**Файл:** [`acp-client/src/acp_client/tui/navigation/queue.py`](../../src/acp_client/tui/navigation/queue.py)

Приоритетная очередь для последовательного выполнения операций навигации.

#### Основные возможности

- **Приоритетная очередь** на базе heapq
- **Последовательное выполнение** одной операции за раз (FIFO внутри приоритета)
- **Thread-safe** благодаря threading.Lock
- **Async-safe** благодаря asyncio.Lock
- **Управление лайфциклом** операций

#### API

```python
from acp_client.tui.navigation import OperationQueue, NavigationOperation

queue = OperationQueue()

# Установить функцию для выполнения операций
async def execute_op(operation):
    print(f"Executing {operation.operation_type}")

queue.set_executor(execute_op)

# Добавить операцию (асинхронно)
operation = NavigationOperation(...)
await queue.enqueue(operation)

# Очистить очередь (синхронно)
queue.clear()

# Проверить размер
size = queue.size()
is_empty = queue.is_empty()
```

---

### 3. ModalWindowTracker

**Файл:** [`acp-client/src/acp_client/tui/navigation/tracker.py`](../../src/acp_client/tui/navigation/tracker.py)

Отслеживание активных модальных окон для быстрого поиска и управления.

#### API

```python
from acp_client.tui.navigation import ModalWindowTracker
from textual.screen import Screen, ModalScreen

tracker = ModalWindowTracker()

# Зарегистрировать модальное окно
modal = ModalScreen()
modal_id = tracker.register_modal(
    screen=modal,
    modal_type="file_viewer",
    modal_id=None  # автогенерируется если None
)

# Найти модаль по типу
modal = tracker.get_modal_by_type("file_viewer")

# Получить все модали
all_modals = tracker.get_all_modals()

# Проверить видимость
is_visible = tracker.is_modal_visible("file_viewer")

# Отменить регистрацию
tracker.unregister_modal(modal_id)

# Полностью очистить
tracker.clear()
```

---

### 4. NavigationManager

**Файл:** [`acp-client/src/acp_client/tui/navigation/manager.py`](../../src/acp_client/tui/navigation/manager.py)

Главный менеджер навигации. Координирует работу очереди и трекера, синхронизирует с ViewModels.

#### Инициализация

```python
from acp_client.tui.navigation import NavigationManager
from textual.app import App

app = App()  # Textual приложение
nav_manager = NavigationManager(app)
```

#### Основной API

**Показ экран/модали:**

```python
# Показать обычный экран
await nav_manager.show_screen(
    screen=my_screen,
    modal=False,
    priority=1,
    callback=lambda screen: print(f"Shown: {screen}")
)

# Показать модальное окно (ModalScreen)
await nav_manager.show_screen(
    screen=my_modal,
    modal=True,  # Флаг модали
    priority=1
)
```

**Скрытие экран/модали:**

```python
# Скрыть экран по объекту
await nav_manager.hide_screen(
    screen_or_id=my_screen,
    result=None,
    callback=lambda: print("Hidden")
)

# Скрыть верхний экран в стеке
await nav_manager.hide_top_screen(result=None)
```

**Работа с модалями:**

```python
# Найти модаль по типу
modal = nav_manager.get_modal_by_type("file_viewer")

# Проверить видимость
is_visible = nav_manager.is_modal_visible("permission")

# Получить глубину стека (для диагностики)
depth = nav_manager.get_screen_stack_depth()

# Закрыть все модали
await nav_manager.reset()
```

**Подписка ViewModels:**

```python
# Подписать ViewModel на изменения навигации
unsubscribe = nav_manager.subscribe_to_view_model(
    view_model=permission_vm,
    modal_type="permission",
    on_show=lambda: print("Modal shown"),
    on_hide=lambda: print("Modal hidden")
)

# Когда надо отписать
unsubscribe()
```

#### Управление лайфциклом

```python
# Очистить все ресурсы (вызвать при завершении приложения)
nav_manager.dispose()
```

#### Исключения

```python
from acp_client.tui.navigation import (
    NavigationError,          # Базовое исключение
    ScreenStackError,         # Ошибка со стеком экранов
    ModalNotFoundError,       # Модаль не найдена
    OperationTimeoutError,    # Таймаут операции
)

try:
    await nav_manager.show_screen(screen)
except ScreenStackError as e:
    print(f"Stack error: {e}")
except NavigationError as e:
    print(f"Nav error: {e}")
```

---

## Интеграция

### DI Container

**Файл:** [`acp-client/src/acp_client/infrastructure/di_bootstrapper.py`](../../src/acp_client/infrastructure/di_bootstrapper.py)

NavigationManager регистрируется как синглтон в DIContainer:

```python
from acp_client.infrastructure.di_container import ContainerBuilder
from acp_client.tui.navigation import NavigationManager

builder = ContainerBuilder()

# Создаём менеджер с приложением
nav_manager = NavigationManager(app)

# Регистрируем как готовый синглтон
builder.set_instance(NavigationManager, nav_manager)

container = builder.build()
```

### ACPClientApp

**Файл:** [`acp-client/src/acp_client/tui/app.py`](../../src/acp_client/tui/app.py)

Инициализация NavigationManager в главном приложении:

```python
class ACPClientApp(App):
    def on_mount(self) -> None:
        # Получить NavigationManager из DI контейнера
        self._nav_manager = self._container.resolve(NavigationManager)
        
        # Подписать все ViewModels на навигацию
        await self._setup_navigation_sync()
```

---

## Примеры использования

### Базовое использование

**Сценарий 1: Показ и скрытие модального окна**

```python
from acp_client.tui.navigation import NavigationManager

# Получить менеджер из DI контейнера
nav_manager = container.resolve(NavigationManager)

# Создать модальное окно
modal = FileViewerModal(file_viewer_vm=file_viewer_vm)

# Показать модаль (регистрируется автоматически)
await nav_manager.show_screen(
    screen=modal,
    modal=True,
    priority=1
)

# Позже: скрыть с результатом
result = {"file_path": "/path/to/file"}
await nav_manager.hide_screen(modal, result=result)
```

**Сценарий 2: Операции с высоким приоритетом**

```python
# Показать critical modal с высоким приоритетом
await nav_manager.show_screen(
    screen=critical_modal,
    modal=True,
    priority=2  # HIGH приоритет
)

# Закроет все другие операции перед выполнением
```

### Подписка ViewModels

**В ACPClientApp:**

```python
def _setup_navigation_subscriptions(self) -> None:
    """Подписать все ViewModels на навигацию."""
    
    # Permission modal
    self._nav_manager.subscribe_to_view_model(
        view_model=self._permission_vm,
        modal_type="permission",
        on_show=self._on_permission_show,
        on_hide=self._on_permission_hide
    )
    
    # File viewer modal
    self._nav_manager.subscribe_to_view_model(
        view_model=self._file_viewer_vm,
        modal_type="file_viewer"
    )
```

**В ViewModel:**

```python
from acp_client.presentation.observable import Observable

class FileViewerViewModel:
    def __init__(self):
        self.is_visible = Observable(False)
        
    def show_file(self, file_path: str) -> None:
        """Показать файл."""
        self.file_path = file_path
        self.is_visible.value = True  # Триггерит подписку в NavigationManager
        
    def close_file(self) -> None:
        """Закрыть файл."""
        self.is_visible.value = False  # Триггерит подписку в NavigationManager
```

Когда ViewModel меняет `is_visible`, NavigationManager автоматически:
1. Вызывает `on_show()` при `is_visible=True`
2. Вызывает `on_hide()` и скрывает окно при `is_visible=False`

### Обработка ошибок

**Базовая обработка:**

```python
from acp_client.tui.navigation import (
    NavigationError,
    ScreenStackError,
    ModalNotFoundError,
)

try:
    await nav_manager.show_screen(my_screen)
except ScreenStackError as e:
    logger.error(f"Screen stack error: {e}")
except NavigationError as e:
    logger.error(f"Navigation error: {e}")
```

**Проверка состояния:**

```python
# Проверить видимость модали перед операциями
if nav_manager.is_modal_visible("permission"):
    logger.warning("Permission modal already visible")
    return

# Получить глубину стека для диагностики
stack_depth = nav_manager.get_screen_stack_depth()
if stack_depth > 10:
    logger.warning(f"Deep screen stack: {stack_depth}")
    await nav_manager.reset()  # Закрыть все
```

---

## Тестирование

### Покрытие тестами

Полное покрытие всех компонентов NavigationManager:

- **test_navigation_queue.py** (19 тестов) - OperationQueue
- **test_navigation_tracker.py** (29 тестов) - ModalWindowTracker
- **test_navigation_manager.py** (32 теста) - NavigationManager

**Итого: 80 тестов** с полным покрытием функциональности

### Результаты тестирования

```bash
$ make check
✅ ruff check .        # Все проверки пройдены
✅ ty check            # Все типы проверены
✅ pytest              # 80 тестов пройдены из 80
```

Все тесты проходят успешно без ошибок.

---

## Миграция существующего кода

### Миграция с старого показа экранов

**Было (старый код):**

```python
# В app.py напрямую вызывали push_screen
self.push_screen(FileViewerModal(file_viewer_vm=self._file_viewer_vm))
```

**Стало (новый код):**

```python
# Используем NavigationManager
await self._nav_manager.show_screen(
    screen=FileViewerModal(file_viewer_vm=self._file_viewer_vm),
    modal=True
)
```

### Миграция из действия ViewModel

**Было (старый код):**

```python
# В ViewModel.py - вызов dismiss() из Observable callback
def _on_visibility_changed(self, is_visible: bool) -> None:
    if not is_visible:
        self.dismiss(None)  # ScreenStackError!
```

**Стало (новый код):**

```python
# В ViewModel.py - просто меняем Observable
def close_viewer(self) -> None:
    self.is_visible.value = False  # NavigationManager обработает

# В app.py - подписываемся один раз
self._nav_manager.subscribe_to_view_model(
    view_model=self._file_viewer_vm,
    modal_type="file_viewer"
)
```

---

## Преимущества решения

### 1. Безопасность

- **Защита от race conditions** через приоритетную очередь
- **Синхронизация async операций** с asyncio.Lock
- **Синхронизация sync операций** с threading.Lock
- **Атомарные операции** - каждая выполняется полностью
- **Валидация состояния** перед каждой операцией

### 2. Консистентность

- **Единый source of truth** - NavigationManager
- **Синхронизация ViewModel ↔ UI** через Observable
- **Предотвращение циклических обновлений** через флаг
- **Полная отчётность** - все операции логируются
- **Отслеживание состояния** - ModalWindowTracker индекс

### 3. Надежность

- **Error handling** с fallback логикой
- **Cleanup при ошибках** - отмена регистраций
- **Timeout protection** - защита от зависающих операций
- **Graceful degradation** - система продолжает работать после ошибок
- **Resource cleanup** - dispose() для очистки при выходе

### 4. Простота использования

- **Простой API** - show_screen(), hide_screen(), reset()
- **Automatic registration** - модали регистрируются при push
- **Observable паттерн** - интегрирован с ViewModel
- **Минимальный boilerplate** - subscribe_to_view_model()
- **Понятное логирование** - легко отследить проблемы

---

## Известные ограничения

### 1. Timeout для операций

**Ограничение:** Каждая операция имеет timeout 30 секунд.

**Решение:** Если нужен больший timeout:

```python
operation = NavigationOperation(
    operation_type=OperationType.SHOW_SCREEN,
    screen=slow_screen,
    timeout_seconds=60.0  # Увеличить на 60 сек
)
```

### 2. Только последовательное выполнение

**Ограничение:** Операции выполняются одна за другой, не параллельно.

**Причина:** Гарантирует консистентность состояния и предотвращает race conditions.

### 3. Observable синхронизация требует подписки

**Ограничение:** ViewModel.is_visible должна быть Observable для синхронизации.

**Решение:** Все ViewModels уже используют Observable для is_visible.

---

## Дальнейшее развитие

### 1. Отложенные операции (Deferred Operations)

```python
# Запланировать операцию на выполнение через 5 сек
await nav_manager.schedule_screen_show(
    screen=my_screen,
    delay_seconds=5.0
)
```

### 2. Транзакции навигации (Navigation Transactions)

```python
async with nav_manager.transaction():
    await nav_manager.show_screen(screen1)
    await nav_manager.show_screen(screen2)
    # Либо обе успеют, либо обе откатятся
```

### 3. История навигации (Navigation History)

```python
# Получить историю последних операций
history = nav_manager.get_history(limit=10)

# Откатить на несколько операций назад
await nav_manager.rollback(steps=2)
```

### 4. Navigation Guards (Middleware)

```python
def can_navigate_to(screen: Screen) -> bool:
    # Проверка прав, валидация состояния и т.д.
    return True

nav_manager.add_guard(can_navigate_to)
```

---

## Ссылки

### Файлы реализации

- [`acp-client/src/acp_client/tui/navigation/operations.py`](../../src/acp_client/tui/navigation/operations.py) - операции и enum-ы
- [`acp-client/src/acp_client/tui/navigation/queue.py`](../../src/acp_client/tui/navigation/queue.py) - приоритетная очередь
- [`acp-client/src/acp_client/tui/navigation/tracker.py`](../../src/acp_client/tui/navigation/tracker.py) - отслеживание модалей
- [`acp-client/src/acp_client/tui/navigation/manager.py`](../../src/acp_client/tui/navigation/manager.py) - главный менеджер
- [`acp-client/src/acp_client/tui/navigation/__init__.py`](../../src/acp_client/tui/navigation/__init__.py) - публичный API

### Интеграция

- [`acp-client/src/acp_client/infrastructure/di_bootstrapper.py`](../../src/acp_client/infrastructure/di_bootstrapper.py) - DI регистрация
- [`acp-client/src/acp_client/tui/app.py`](../../src/acp_client/tui/app.py) - использование в приложении
- [`acp-client/src/acp_client/tui/components/permission_modal.py`](../../src/acp_client/tui/components/permission_modal.py) - интеграция в PermissionModal
- [`acp-client/src/acp_client/tui/components/file_viewer.py`](../../src/acp_client/tui/components/file_viewer.py) - интеграция в FileViewerModal
- [`acp-client/src/acp_client/tui/components/terminal_log_modal.py`](../../src/acp_client/tui/components/terminal_log_modal.py) - интеграция в TerminalLogModal

### Тесты

- [`acp-client/tests/test_navigation_queue.py`](../../tests/test_navigation_queue.py) - 19 тестов для OperationQueue
- [`acp-client/tests/test_navigation_tracker.py`](../../tests/test_navigation_tracker.py) - 29 тестов для ModalWindowTracker
- [`acp-client/tests/test_navigation_manager.py`](../../tests/test_navigation_manager.py) - 32 теста для NavigationManager

### Документация

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — архитектура Clean Architecture
- [`DEVELOPING.md`](./DEVELOPING.md) — разработка и расширение
- [`TESTING.md`](./TESTING.md) — стратегия тестирования
