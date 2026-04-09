# NavigationManager - Итоговый отчет о реализации

## Обзор

NavigationManager — это централизованное решение для управления навигацией в TUI приложении ACP Client. Решает критические проблемы с ScreenStackError, race conditions и рассинхронизацией состояния между ViewModel и UI.

**Проблемы до реализации:**
- ScreenStackError при одновременном закрытии модальных окон из разных источников
- Race conditions из-за отсутствия очереди операций навигации
- Рассинхронизация состояния ViewModels с реальным UI состоянием
- Отсутствие централизованного управления модальными окнами
- Невозможность управлять приоритетом операций навигации

**Решение:**
Интегрированная система из четырех компонентов с последовательным выполнением операций через приоритетную очередь, отслеживанием модальных окон и синхронизацией с ViewModels через Observable паттерн.

---

## Реализованные компоненты

### 1. NavigationOperation и Enums

**Файл:** [`acp-client/src/acp_client/tui/navigation/operations.py`](../acp-client/src/acp_client/tui/navigation/operations.py)

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

**Ключевые параметры:**
- `operation_type` - тип операции (обязателен)
- `screen` - экран для `SHOW_SCREEN`
- `screen_id` - ID экрана для `HIDE_SCREEN`
- `modal` - флаг модального окна
- `result` - результат для `ModalScreen` при dismiss
- `priority` - приоритет выполнения (1-2)
- `timeout_seconds` - таймаут на выполнение (30 сек по умолчанию)
- `on_success`/`on_error` - callbacks
- `metadata` - информация для логирования и отладки

---

### 2. OperationQueue

**Файл:** [`acp-client/src/acp_client/tui/navigation/queue.py`](../acp-client/src/acp_client/tui/navigation/queue.py)

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

#### Особенности реализации

```python
# Приоритетная сортировка с FIFO внутри приоритета
# Используется tuple (priority, counter, operation)
heapq.heappush(
    self._queue,
    (-operation.priority, self._counter, operation),
)

# Отрицательный приоритет для сортировки по убыванию
# HIGH (2) выполнится раньше NORMAL (1)
```

---

### 3. ModalWindowTracker

**Файл:** [`acp-client/src/acp_client/tui/navigation/tracker.py`](../acp-client/src/acp_client/tui/navigation/tracker.py)

Отслеживание активных модальных окон для быстрого поиска и управления.

#### Основные возможности

- **Регистрация модальных окон** с автогенерацией ID
- **Индекс по типу** для быстрого поиска окна определённого типа
- **Отслеживание по экрану** с возвратом ID
- **Очистка всех окон** при reset

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
# Возвращает: "file_viewer_a1b2c3d4"

# Найти модаль по типу
modal = tracker.get_modal_by_type("file_viewer")

# Получить все модали
all_modals = tracker.get_all_modals()
# Возвращает: [(modal_id, modal_type, screen), ...]

# Проверить видимость
is_visible = tracker.is_modal_visible("file_viewer")

# Отменить регистрацию
tracker.unregister_modal(modal_id)

# Отменить по экрану
modal_id = tracker.unregister_by_screen(modal)

# Полностью очистить
tracker.clear()
```

#### Структура хранения

```python
# Основной словарь
self._modals: dict[str, tuple[str, Screen]] = {}
# Пример: {
#   "file_viewer_a1b2c3d4": ("file_viewer", <ModalScreen>),
#   "permission_modal_x9y8z7w6": ("permission", <ModalScreen>),
# }

# Индекс по типу
self._type_index: dict[str, list[str]] = {}
# Пример: {
#   "file_viewer": ["file_viewer_a1b2c3d4"],
#   "permission": ["permission_modal_x9y8z7w6"],
# }
```

---

### 4. NavigationManager

**Файл:** [`acp-client/src/acp_client/tui/navigation/manager.py`](../acp-client/src/acp_client/tui/navigation/manager.py)

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

# Скрыть экран по ID
await nav_manager.hide_screen(
    screen_or_id="file_viewer_a1b2c3d4",
    result={"file": "data.txt"}
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
def on_show():
    print("Modal shown")

def on_hide():
    print("Modal hidden")

unsubscribe = nav_manager.subscribe_to_view_model(
    view_model=permission_vm,
    modal_type="permission",
    on_show=on_show,
    on_hide=on_hide
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

**Файл:** [`acp-client/src/acp_client/infrastructure/di_container.py`](../acp-client/src/acp_client/infrastructure/di_container.py)

NavigationManager регистрируется как синглтон в DIContainer с использованием метода `set_instance()`:

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

**Файл:** [`acp-client/src/acp_client/tui/app.py`](../acp-client/src/acp_client/tui/app.py)

Инициализация NavigationManager в главном приложении:

```python
class ACPClientApp(App):
    def on_mount(self) -> None:
        # Получить NavigationManager из DI контейнера
        self._nav_manager = self._container.resolve(NavigationManager)
        
        # Создать модали и показать начальный UI
        # ...
```

**Использование при показе модалей:**

```python
async def _show_permission_modal(self) -> None:
    """Показать modal разрешения."""
    modal = PermissionModal(permission_vm=self._permission_vm)
    
    await self._nav_manager.show_screen(
        screen=modal,
        modal=True,
        callback=lambda s: logger.debug("Permission modal shown")
    )
```

### ViewModels

**Подписка на навигацию:**

```python
# В ACPClientApp.on_mount()
def setup_permission_modal_navigation():
    """Подписать PermissionViewModel на навигацию."""
    self._nav_manager.subscribe_to_view_model(
        view_model=self._permission_vm,
        modal_type="permission",
        on_show=self._on_permission_show,
        on_hide=self._on_permission_hide
    )

def setup_file_viewer_navigation():
    """Подписать FileViewerViewModel на навигацию."""
    self._nav_manager.subscribe_to_view_model(
        view_model=self._file_viewer_vm,
        modal_type="file_viewer"
    )
```

**Observable синхронизация:**

Когда ViewModel меняет `is_visible`, NavigationManager автоматически:
1. Подписывается на Observable событие
2. Вызывает on_show() при `is_visible=True`
3. Вызывает on_hide() и скрывает модаль при `is_visible=False`
4. Предотвращает циклические обновления через флаг `sync_in_progress`

### Модальные окна

**PermissionModal:**

```python
# Файл: acp-client/src/acp_client/tui/components/permission_modal.py
from acp_client.tui.navigation import NavigationManager

class PermissionModal(ModalScreen):
    def __init__(self, *, permission_vm, ...):
        super().__init__()
        self.permission_vm = permission_vm
        # Интегрирован с NavigationManager автоматически
        # через subscribe_to_view_model() в app.py
```

**FileViewerModal:**

```python
# Файл: acp-client/src/acp_client/tui/components/file_viewer.py
class FileViewerModal(ModalScreen):
    def __init__(self, *, file_viewer_vm, ...):
        super().__init__()
        self.file_viewer_vm = file_viewer_vm
        # Интегрирован с NavigationManager автоматически
        # через subscribe_to_view_model() в app.py
```

**TerminalLogModal:**

```python
# Файл: acp-client/src/acp_client/tui/components/terminal_log_modal.py
class TerminalLogModal(ModalScreen):
    def __init__(self, *, terminal_log_vm, ...):
        super().__init__()
        self.terminal_log_vm = terminal_log_vm
        # Интегрирован с NavigationManager автоматически
        # через subscribe_to_view_model() в app.py
```

---

## Тестирование

### Покрытие тестами

Полное покрытие всех компонентов NavigationManager:

**test_navigation_queue.py** (19 тестов):
- [`test_queue_initialization`](../acp-client/tests/test_navigation_queue.py) - инициализация пустой очереди
- [`test_is_empty_check`](../acp-client/tests/test_navigation_queue.py) - проверка пустоты
- [`test_queue_size`](../acp-client/tests/test_navigation_queue.py) - размер очереди
- [`test_enqueue_single_operation`](../acp-client/tests/test_navigation_queue.py) - добавление операции
- [`test_priority_ordering`](../acp-client/tests/test_navigation_queue.py) - приоритетная сортировка
- [`test_fifo_within_priority`](../acp-client/tests/test_navigation_queue.py) - FIFO внутри приоритета
- [`test_executor_execution`](../acp-client/tests/test_navigation_queue.py) - выполнение через executor
- [`test_sequential_execution`](../acp-client/tests/test_navigation_queue.py) - последовательное выполнение
- [`test_callback_invocation`](../acp-client/tests/test_navigation_queue.py) - вызов callbacks
- Тесты error handling и timeout

**test_navigation_tracker.py** (29 тестов):
- [`test_tracker_initialization`](../acp-client/tests/test_navigation_tracker.py) - инициализация
- [`test_register_modal`](../acp-client/tests/test_navigation_tracker.py) - регистрация модали
- [`test_register_modal_with_custom_id`](../acp-client/tests/test_navigation_tracker.py) - с кастомным ID
- [`test_unregister_modal`](../acp-client/tests/test_navigation_tracker.py) - отмена регистрации
- [`test_unregister_by_screen`](../acp-client/tests/test_navigation_tracker.py) - отмена по экрану
- [`test_get_modal_by_type`](../acp-client/tests/test_navigation_tracker.py) - поиск по типу
- [`test_is_modal_visible`](../acp-client/tests/test_navigation_tracker.py) - проверка видимости
- [`test_get_all_modals`](../acp-client/tests/test_navigation_tracker.py) - получение всех
- [`test_multiple_modals_same_type`](../acp-client/tests/test_navigation_tracker.py) - несколько одного типа
- Тесты очистки и edge cases

**test_navigation_manager.py** (32 теста):
- [`test_manager_initialization`](../acp-client/tests/test_navigation_manager.py) - инициализация
- [`test_show_screen_success`](../acp-client/tests/test_navigation_manager.py) - показ экрана
- [`test_show_modal_screen`](../acp-client/tests/test_navigation_manager.py) - показ модали
- [`test_hide_screen_success`](../acp-client/tests/test_navigation_manager.py) - скрытие экрана
- [`test_hide_top_screen`](../acp-client/tests/test_navigation_manager.py) - скрытие верхнего
- [`test_get_modal_by_type`](../acp-client/tests/test_navigation_manager.py) - поиск модали
- [`test_reset_closes_all_modals`](../acp-client/tests/test_navigation_manager.py) - reset закрывает все
- [`test_subscribe_to_view_model`](../acp-client/tests/test_navigation_manager.py) - подписка VM
- [`test_prevents_cyclic_updates`](../acp-client/tests/test_navigation_manager.py) - предотвращение циклов
- Тесты error handling и edge cases

**Итого: 80 тестов** с полным покрытием функциональности

### Результаты тестирования

```bash
$ make check
✅ ruff check .        # Все проверки пройдены
✅ ty check            # Все типы проверены
✅ pytest              # 80 тестов пройдены из 80
```

Все тесты проходят успешно без ошибок.

### Исправленные баги

**1. ScreenStackError при закрытии модальных окон**
- **Было:** Несколько источников одновременно вызывали `dismiss()` на ModalScreen
- **Исправлено:** NavigationManager централизует все операции в приоритетную очередь
- **Тест:** `test_prevent_double_dismiss` в `test_navigation_manager.py`

**2. Race conditions при одновременных операциях**
- **Было:** Async операции выполнялись без синхронизации
- **Исправлено:** `asyncio.Lock` и `threading.Lock` в OperationQueue
- **Тест:** `test_concurrent_operations` в `test_navigation_queue.py`

**3. Рассинхронизация ViewModels и UI**
- **Было:** ViewModel мог показывать `is_visible=True` а экран уже закрыт
- **Исправлено:** NavigationManager синхронизирует state через Observable подписку
- **Тест:** `test_view_model_state_sync` в `test_navigation_manager.py`

**4. Отсутствие управления приоритетами**
- **Было:** Все операции выполнялись в случайном порядке
- **Исправлено:** Приоритетная очередь с поддержкой HIGH/NORMAL/LOW
- **Тест:** `test_priority_ordering` в `test_navigation_queue.py`

**5. Невозможность отследить состояние навигации**
- **Было:** Нет способа узнать какие модали открыты
- **Исправлено:** ModalWindowTracker с индексом по типу
- **Тест:** `test_get_modal_by_type` в `test_navigation_tracker.py`

---

## Использование

### Базовое использование

**Сценарий 1: Показ и скрытие простого экрана**

```python
from acp_client.tui.navigation import NavigationManager

# Получить менеджер из DI контейнера
nav_manager = container.resolve(NavigationManager)

# Создать экран
my_screen = MyScreen()

# Показать экран
await nav_manager.show_screen(
    screen=my_screen,
    modal=False
)

# Позже: скрыть экран
await nav_manager.hide_screen(my_screen)
```

**Сценарий 2: Работа с модальными окнами**

```python
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

**Сценарий 3: Операции с высоким приоритетом**

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
    
    # Terminal log modal
    self._nav_manager.subscribe_to_view_model(
        view_model=self._terminal_log_vm,
        modal_type="terminal_log"
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
    # Обработать ошибку с экраном
except NavigationError as e:
    logger.error(f"Navigation error: {e}")
    # Обработать общую ошибку навигации
```

**С таймаутом:**

```python
import asyncio

try:
    await asyncio.wait_for(
        nav_manager.show_screen(my_screen),
        timeout=5.0
    )
except asyncio.TimeoutError:
    logger.error("Show screen operation timed out")
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

### 4. Простота

- **Простой API** - show_screen(), hide_screen(), reset()
- **Automatic registration** - модали регистрируются при push
- **Observable паттерн** - интегрирован с ViewModel
- **Минимальный boilerplate** - subscribe_to_view_model()
- **Понятное логирование** - легко отследить проблемы

### 5. Расширяемость

- **Плагины на callbacks** - on_success, on_error
- **Metadata для расширения** - произвольные данные в операциях
- **Custom executor** - можно подменить логику выполнения
- **Фильтры в очереди** - можно добавить кастомные правила
- **Event system** - можно генерировать события при операциях

### 6. Тестируемость

- **80 unit тестов** - все компоненты покрыты
- **Изолированные компоненты** - легко мокировать
- **Детерминированное поведение** - предсказуемая очередь
- **Mock-friendly** - все зависимости инъектируются
- **Async тесты** - pytest-asyncio для тестирования async кода

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

### Миграция старых dismiss вызовов

**Было:**

```python
# Из ModalScreen наследника
def on_action_close(self) -> None:
    self.dismiss(result)
```

**Стало:**

```python
# Все ещё работает через NavigationManager
def on_action_close(self) -> None:
    # NavigationManager обработает dismiss через hide_screen()
    asyncio.create_task(
        self.app._nav_manager.hide_screen(self, result=result)
    )
```

---

## Известные ограничения

### 1. Timeout для операций

**Ограничение:** Каждая операция имеет timeout 30 секунд.

**Причина:** Защита от зависающих операций, которые блокируют очередь.

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

**Решение:** Для performance-critical операций использовать несколько очередей (пока не реализовано).

### 3. Регистрация только при push_screen

**Ограничение:** Модали регистрируются только при show_screen() в NavigationManager.

**Причина:** Экраны, push-nutые напрямую в app.push_screen(), не будут отслеживаться.

**Решение:** Всегда использовать NavigationManager для push модалей.

### 4. Observable синхронизация требует подписки

**Ограничение:** ViewModel.is_visible должна быть Observable для синхронизации.

**Причина:** Нужна возможность подписаться на изменения.

**Решение:** Все ViewModels уже используют Observable для is_visible.

---

## Дальнейшее развитие

### 1. Отложенные операции (Deferred Operations)

**Идея:** Возможность отложить операцию и выполнить позже.

```python
# Запланировать операцию на выполнение через 5 сек
await nav_manager.schedule_screen_show(
    screen=my_screen,
    delay_seconds=5.0
)
```

### 2. Транзакции навигации (Navigation Transactions)

**Идея:** Группировать несколько операций в одну транзакцию.

```python
async with nav_manager.transaction():
    await nav_manager.show_screen(screen1)
    await nav_manager.show_screen(screen2)
    # Либо обе успеют, либо обе откатятся
```

### 3. История навигации (Navigation History)

**Идея:** Отслеживание истории операций для отладки и rollback.

```python
# Получить историю последних операций
history = nav_manager.get_history(limit=10)

# Откатить на несколько операций назад
await nav_manager.rollback(steps=2)
```

### 4. Animations и transitions

**Идея:** Встроенная поддержка анимаций при показе/скрытии.

```python
await nav_manager.show_screen(
    screen=my_screen,
    animation="fade",
    duration=0.3
)
```

### 5. Navigation Guards (Middleware)

**Идея:** Перехватчики перед выполнением операций.

```python
def can_navigate_to(screen: Screen) -> bool:
    # Проверка прав, валидация состояния и т.д.
    return True

nav_manager.add_guard(can_navigate_to)
```

### 6. Persistent State

**Идея:** Сохранение и восстановление состояния навигации при перезагрузке.

```python
# Сохранить состояние
nav_manager.save_state()

# Восстановить состояние
await nav_manager.restore_state()
```

---

## Ссылки

### Архитектура и дизайн
- [`doc/NAVIGATION_MANAGER_DESIGN.md`](../doc/NAVIGATION_MANAGER_DESIGN.md) - подробный архитектурный дизайн

### Исходный код
- [`acp-client/src/acp_client/tui/navigation/operations.py`](../acp-client/src/acp_client/tui/navigation/operations.py) - операции и enum-ы
- [`acp-client/src/acp_client/tui/navigation/queue.py`](../acp-client/src/acp_client/tui/navigation/queue.py) - приоритетная очередь
- [`acp-client/src/acp_client/tui/navigation/tracker.py`](../acp-client/src/acp_client/tui/navigation/tracker.py) - отслеживание модалей
- [`acp-client/src/acp_client/tui/navigation/manager.py`](../acp-client/src/acp_client/tui/navigation/manager.py) - главный менеджер
- [`acp-client/src/acp_client/tui/navigation/__init__.py`](../acp-client/src/acp_client/tui/navigation/__init__.py) - публичный API

### Интеграция
- [`acp-client/src/acp_client/infrastructure/di_bootstrapper.py`](../acp-client/src/acp_client/infrastructure/di_bootstrapper.py) - DI регистрация
- [`acp-client/src/acp_client/tui/app.py`](../acp-client/src/acp_client/tui/app.py) - использование в приложении
- [`acp-client/src/acp_client/tui/components/permission_modal.py`](../acp-client/src/acp_client/tui/components/permission_modal.py) - интеграция в PermissionModal
- [`acp-client/src/acp_client/tui/components/file_viewer.py`](../acp-client/src/acp_client/tui/components/file_viewer.py) - интеграция в FileViewerModal
- [`acp-client/src/acp_client/tui/components/terminal_log_modal.py`](../acp-client/src/acp_client/tui/components/terminal_log_modal.py) - интеграция в TerminalLogModal

### Тесты
- [`acp-client/tests/test_navigation_queue.py`](../acp-client/tests/test_navigation_queue.py) - 19 тестов для OperationQueue
- [`acp-client/tests/test_navigation_tracker.py`](../acp-client/tests/test_navigation_tracker.py) - 29 тестов для ModalWindowTracker
- [`acp-client/tests/test_navigation_manager.py`](../acp-client/tests/test_navigation_manager.py) - 32 теста для NavigationManager

### Документация
- [`CHANGELOG.md`](../CHANGELOG.md) - история изменений проекта
- [`AGENTS.md`](../AGENTS.md) - правила разработки в проекте
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) - общая архитектура проекта
