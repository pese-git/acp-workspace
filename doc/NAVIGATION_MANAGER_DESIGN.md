# NavigationManager: Архитектурный дизайн

## 1. Описание проблемы

### 1.1 Текущие проблемы

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

#### Неправильное использование ModalScreen
```python
# Текущая открытие в app.py:
self.push_screen(
    FileViewerModal(file_viewer_vm=self._file_viewer_vm, ...)
)
# Это корректно - ModalScreen может быть push-нут

# Но компоненты ожидают, что это child widgets, что неправильно
# ModalScreen наследуется от Screen, не от Widget
```

**Проблема:** Архитектурное смешивание:
- ModalScreen - это полноценный Screen, не просто Widget
- Невозможно использовать как child widget в Vertical/Horizontal контейнеры
- Попытки вызова `widget.remove()` на ModalScreen некорректны

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

#### ViewModels и Screens рассинхронизированы
```python
# ViewModel знает, что окно "visible", но оно уже закрыто
# или наоборот - окно открыто, но ViewModel говорит "invisible"

# Нет гарантии, что:
# 1. push_screen завершился до того, как UI рендерит
# 2. dismiss завершился до того, как ViewModel проверяет is_visible
# 3. ни одна операция не дублируется
```

---

## 2. Архитектурное решение

### 2.1 Общая архитектура

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

### 2.2 Компоненты системы

#### 2.2.1 NavigationManager (основной координатор)

**Ответственность:**
- Единая точка входа для всех операций навигации
- Управление screen stack через App API
- Отслеживание активных модальных окон
- Выполнение операций в очередь с проверками состояния
- Синхронизация с ViewModels через Observable subscriptions

**Интерфейс:**

```python
class NavigationManager:
    """Централизованный менеджер навигации для TUI приложения."""
    
    def __init__(self, app: App, logger: Any | None = None) -> None:
        """Инициализировать менеджер.
        
        Args:
            app: Главное Textual приложение
            logger: Logger для логирования операций
        """
        ...
    
    # Основной API - показать/скрыть экраны
    async def show_screen(
        self,
        screen: Screen,
        modal: bool = False,
        priority: int = 0,
        callback: Callable[[Screen], None] | None = None,
    ) -> None:
        """Показать экран (screen или modal).
        
        Args:
            screen: Экран для отображения
            modal: True если это модальное окно (ModalScreen)
            priority: Приоритет операции (выше = выполнится раньше)
            callback: Callback после успешного показа
            
        Raises:
            NavigationError: Если операция невозможна
            
        Пример:
            >>> await nav.show_screen(file_viewer_modal, modal=True)
        """
        ...
    
    async def hide_screen(
        self,
        screen_or_id: Screen | str,
        result: Any = None,
        callback: Callable[[], None] | None = None,
    ) -> Any:
        """Скрыть экран (pop или dismiss в зависимости от типа).
        
        Args:
            screen_or_id: Экран или его ID для скрытия
            result: Результат для передачи в callback (для ModalScreen)
            callback: Callback после успешного скрытия
            
        Returns:
            Результат операции (для ModalScreen - возвращаемое значение)
            
        Raises:
            NavigationError: Если операция невозможна
        """
        ...
    
    async def hide_top_screen(
        self,
        result: Any = None,
    ) -> Any:
        """Скрыть верхний экран в стеке (быстрая операция)."""
        ...
    
    # Поиск и проверка состояния
    def get_modal_by_type(self, modal_type: str) -> Screen | None:
        """Найти модальное окно по типу.
        
        Args:
            modal_type: Тип модального окна (класс имя или кастомный ID)
            
        Returns:
            Найденное модальное окно или None
        """
        ...
    
    def is_modal_visible(self, modal_type: str) -> bool:
        """Проверить видимо ли модальное окно."""
        ...
    
    def get_screen_stack_depth(self) -> int:
        """Получить глубину стека экранов (для диагностики)."""
        ...
    
    # Управление синхронизацией с ViewModels
    def subscribe_to_view_model(
        self,
        view_model: Any,
        modal_type: str,
        on_show: Callable | None = None,
        on_hide: Callable | None = None,
    ) -> Callable[[], None]:
        """Подписать ViewModel на изменения навигации.
        
        Автоматически синхронизирует is_visible в ViewModel с реальным состоянием.
        
        Args:
            view_model: ViewModel для синхронизации
            modal_type: Тип модального окна
            on_show: Callback при открытии окна
            on_hide: Callback при закрытии окна
            
        Returns:
            Функция для отписки
        """
        ...
    
    # Управление состоянием
    async def reset(self) -> None:
        """Закрыть все модальные окна и вернуться в normal state."""
        ...
    
    def dispose(self) -> None:
        """Очистить ресурсы менеджера (вызвать при завершении приложения)."""
        ...
```

#### 2.2.2 OperationQueue (очередь операций)

**Ответственность:**
- Хранение операций навигации
- Последовательное выполнение (одна за раз)
- Поддержка приоритетов
- Обработка ошибок и timeout-ов

**Структура:**

```python
@dataclass(frozen=True)
class NavigationOperation:
    """Описание операции навигации."""
    
    # Тип операции
    operation_type: Literal["show_screen", "hide_screen", "reset"]
    
    # Параметры операции
    screen: Screen | None = None  # Для show_screen
    screen_id: str | None = None  # Для hide_screen
    modal: bool = False  # Это ли модальное окно
    result: Any = None  # Результат для ModalScreen
    
    # Контроль выполнения
    priority: int = 0  # Выше = выполнится раньше
    timeout_seconds: float = 30.0  # Таймаут операции
    
    # Callbacks
    on_success: Callable[..., None] | None = None
    on_error: Callable[[Exception], None] | None = None


class OperationQueue:
    """Очередь операций навигации с последовательным выполнением."""
    
    def __init__(self, logger: Any | None = None) -> None:
        ...
    
    async def enqueue(self, operation: NavigationOperation) -> Any:
        """Добавить операцию в очередь и ждать выполнения.
        
        Операции выполняются последовательно в порядке приоритета.
        Более приоритетные (priority выше) выполняются раньше.
        
        Args:
            operation: Операция для выполнения
            
        Returns:
            Результат операции
            
        Raises:
            NavigationError: Если операция не удалась
            asyncio.TimeoutError: Если превышено время ожидания
        """
        ...
    
    def clear(self) -> None:
        """Очистить очередь (отменить все ожидающие операции)."""
        ...
    
    def size(self) -> int:
        """Количество ожидающих операций."""
        ...
    
    def set_executor(
        self,
        executor: Callable[[NavigationOperation], Awaitable[Any]],
    ) -> None:
        """Установить функцию выполнения операций.
        
        Args:
            executor: Async функция, которая выполняет операцию
        """
        ...
```

#### 2.2.3 ModalWindowTracker (отслеживание модалей)

**Ответственность:**
- Регистрация открытых модальных окон
- Поиск модального окна по типу или ID
- Проверка видимости
- Очистка при закрытии

**Структура:**

```python
class ModalWindowTracker:
    """Отслеживает активные модальные окна."""
    
    def __init__(self, logger: Any | None = None) -> None:
        ...
    
    def register_modal(
        self,
        screen: Screen,
        modal_type: str,
        modal_id: str | None = None,
    ) -> str:
        """Зарегистрировать открытое модальное окно.
        
        Args:
            screen: Экран модального окна
            modal_type: Тип модального окна (например, "file_viewer")
            modal_id: Уникальный ID окна (если None, генерируется автоматически)
            
        Returns:
            ID зарегистрированного модального окна
        """
        ...
    
    def unregister_modal(self, screen: Screen) -> None:
        """Отменить регистрацию модального окна при закрытии."""
        ...
    
    def get_modal_by_type(self, modal_type: str) -> Screen | None:
        """Найти первое (верхнее) модальное окно по типу."""
        ...
    
    def get_all_modals_by_type(self, modal_type: str) -> list[Screen]:
        """Получить все модальные окна указанного типа."""
        ...
    
    def is_modal_visible(self, modal_type: str) -> bool:
        """Проверить видимо ли модальное окно указанного типа."""
        ...
    
    def get_all_modals(self) -> list[tuple[str, Screen]]:
        """Получить все открытые модальные окна (тип, экран)."""
        ...
    
    def clear(self) -> None:
        """Очистить все регистрации (обычно вызывается при reset)."""
        ...
```

#### 2.2.4 NavigationStateSync (синхронизация состояния)

**Ответственность:**
- Подписка на Observable свойства ViewModels
- Преобразование изменений в операции навигации
- Предотвращение циклических обновлений

**Структура:**

```python
class NavigationStateSync:
    """Синхронизирует состояние ViewModels с реальной навигацией."""
    
    def __init__(
        self,
        navigation_manager: NavigationManager,
        logger: Any | None = None,
    ) -> None:
        ...
    
    def sync_view_model(
        self,
        view_model: Any,  # Должен иметь is_visible: Observable
        modal_type: str,
        modal_constructor: Callable[[], Screen],
        on_show: Callable[[], None] | None = None,
        on_hide: Callable[[], None] | None = None,
    ) -> Callable[[], None]:
        """Синхронизировать ViewModel с навигацией.
        
        При изменении ViewModel.is_visible:
        - True  -> вызывает NavigationManager.show_screen()
        - False -> вызывает NavigationManager.hide_screen()
        
        Предотвращает циклические обновления (ViewModel -> UI -> ViewModel).
        
        Args:
            view_model: ViewModel с is_visible свойством
            modal_type: Тип модального окна
            modal_constructor: Функция создания экрана
            on_show: Callback при показе
            on_hide: Callback при скрытии
            
        Returns:
            Функция для отписки от синхронизации
        """
        ...
    
    def _prevent_cycle(self, modal_type: str) -> None:
        """Предотвратить циклическое обновление (внутренний метод)."""
        ...
    
    def dispose(self) -> None:
        """Отписать все ViewModels (при завершении приложения)."""
        ...
```

---

## 3. Примеры использования

### 3.1 Базовое использование - показать файловый просмотрщик

**До (текущий код):**
```python
# В app.py:
def on_file_tree_file_open_requested(self, message: FileTree.FileOpenRequested) -> None:
    target_path = message.path
    # ... подготовка пути ...
    content = self._filesystem.read_file(str(target_path), ...)
    
    # Прямой push_screen - может вызвать ScreenStackError если одновременно
    # происходит dismiss из-за подписки ViewModel
    self.push_screen(
        FileViewerModal(
            file_viewer_vm=self._file_viewer_vm,
            file_path=str(target_path),
            content=content,
        )
    )
```

**После (с NavigationManager):**
```python
# В app.py:
async def on_file_tree_file_open_requested(
    self, message: FileTree.FileOpenRequested
) -> None:
    target_path = message.path
    # ... подготовка пути ...
    content = self._filesystem.read_file(str(target_path), ...)
    
    # Все операции навигации через менеджер - гарантированно безопасно
    try:
        await self._navigation_manager.show_screen(
            FileViewerModal(
                file_viewer_vm=self._file_viewer_vm,
                file_path=str(target_path),
                content=content,
            ),
            modal=True,
            callback=lambda screen: self._app_logger.debug("file_viewer_shown"),
        )
    except NavigationError as e:
        self.query_one(ChatView).add_system_message(f"Ошибка открытия файла: {e}")
```

### 3.2 Синхронизация ViewModel с навигацией

**До (текущий код):**
```python
# В FileViewerModal:
def _on_visibility_changed(self, is_visible: bool) -> None:
    if not is_visible:
        self.dismiss(None)  # ПРОБЛЕМА: race condition с другими dismiss()
```

**После (с NavigationManager):**
```python
# В app.py (bootstrap код):
async def _setup_navigation() -> None:
    # Синхронизировать FileViewer ViewModel с реальной навигацией
    self._navigation_manager.subscribe_to_view_model(
        view_model=self._file_viewer_vm,
        modal_type="file_viewer",
        # Конструктор для создания экрана при необходимости
        # (обычно уже существует, но используется для восстановления)
        on_show=lambda: self._app_logger.debug("file_viewer_shown"),
        on_hide=lambda: self._app_logger.debug("file_viewer_hidden"),
    )
    
    # Теперь закрытие через ViewModel.hide() работает безопасно:
    # ViewModel.is_visible = False -> NavigationManager -> pop_screen
```

### 3.3 Работа с разрешениями (Permission Modal)

**До (текущий код):**
```python
# В app.py:
async def _on_permission_request(self, payload: dict) -> str | None:
    parsed_request = parse_request_permission_request(payload)
    # ...
    
    # Используется push_screen_wait - может зависнуть если dismiss() вызовется
    # дважды (из ViewModel callback и из обработчика кнопки)
    try:
        selected_option_id = await asyncio.wait_for(
            self.push_screen_wait(self._build_permission_modal(parsed_request)),
            timeout=PERMISSION_WAIT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        # ...
```

**После (с NavigationManager):**
```python
# В app.py:
async def _on_permission_request(self, payload: dict) -> str | None:
    parsed_request = parse_request_permission_request(payload)
    # ...
    
    # NavigationManager гарантирует безопасное выполнение
    try:
        selected_option_id = await self._navigation_manager.show_screen(
            PermissionModal(
                permission_vm=self._permission_vm,
                title=title,
                options=parsed_request.params.options,
            ),
            modal=True,
            priority=10,  # Высокий приоритет для разрешений
        )
    except NavigationError as e:
        # ...
```

### 3.4 Закрытие модального окна из ViewModels

**В FileViewerViewModel:**
```python
def hide(self) -> None:
    """Скрыть модальное окно просмотра файла."""
    self._is_visible.value = False
    self.logger.debug("file_viewer_hidden_via_view_model")
```

**Что происходит внутри:**
1. `is_visible.value = False` срабатывает
2. NavigationStateSync ловит изменение
3. NavigationStateSync вызывает `navigation_manager.hide_screen()`
4. NavigationManager помещает операцию в очередь
5. OperationQueue выполняет операцию безопасно
6. Экран pop-нется из стека

**Гарантии:**
- Никогда не будет двойного dismiss()
- Никогда не будет race condition
- Циклические обновления (ViewModel -> UI -> ViewModel) предотвращены

---

## 4. Интеграция с существующей архитектурой

### 4.1 DI Container интеграция

**В DIBootstrapper:**
```python
def build(cls, ...) -> DIContainer:
    """Строит DI контейнер с NavigationManager."""
    container = DIContainer()
    
    # ... регистрация других компонентов ...
    
    # NavigationManager требует App, поэтому регистрируется особым образом:
    # 1. NavigationManager создается после инициализации App
    # 2. Передается через конструктор ACPClientApp
    # ИЛИ
    # 1. Регистрируется как singleton после создания App
    
    return container
```

**В ACPClientApp:**
```python
def __init__(self, *, host: str, port: int) -> None:
    super().__init__()
    # ... инициализация других менеджеров ...
    
    # Инициализировать NavigationManager после завершения __init__
    self._navigation_manager = NavigationManager(self, logger=self._app_logger)
    self._navigation_state_sync = NavigationStateSync(
        self._navigation_manager,
        logger=self._app_logger,
    )

async def on_mount(self) -> None:
    """Запустить bootstrap, включая синхронизацию навигации."""
    # Настроить синхронизацию ViewModels
    await self._setup_navigation_sync()
    # ... остальной bootstrap ...

async def _setup_navigation_sync(self) -> None:
    """Подписать все ViewModels на изменения навигации."""
    
    # FileViewer
    self._navigation_state_sync.sync_view_model(
        view_model=self._file_viewer_vm,
        modal_type="file_viewer",
        modal_constructor=lambda: FileViewerModal(
            file_viewer_vm=self._file_viewer_vm,
        ),
    )
    
    # Permission
    self._navigation_state_sync.sync_view_model(
        view_model=self._permission_vm,
        modal_type="permission",
        modal_constructor=lambda: PermissionModal(
            permission_vm=self._permission_vm,
        ),
    )
    
    # Terminal Log
    self._navigation_state_sync.sync_view_model(
        view_model=self._terminal_log_vm,
        modal_type="terminal_log",
        modal_constructor=lambda: TerminalLogModal(
            terminal_log_vm=self._terminal_log_vm,
        ),
    )
```

### 4.2 Миграция существующих операций

**Операция: Открытие файла**

До:
```python
def on_file_tree_file_open_requested(self, message):
    self.push_screen(FileViewerModal(...))
```

После:
```python
async def on_file_tree_file_open_requested(self, message):
    await self._navigation_manager.show_screen(
        FileViewerModal(...),
        modal=True,
    )
```

**Операция: Закрытие файла из компонента**

До (в FileViewerModal):
```python
def action_close(self):
    self.dismiss(None)  # Может race condition
```

После (в FileViewerModal):
```python
def action_close(self):
    self.file_viewer_vm.hide()  # ViewModel -> NavigationManager
```

**Операция: Показать разрешение**

До:
```python
selected = await self.push_screen_wait(PermissionModal(...))
```

После:
```python
selected = await self._navigation_manager.show_screen(
    PermissionModal(...),
    modal=True,
    priority=10,
)
```

---

## 5. Обработка edge cases

### 5.1 Быстрые последовательные операции

```python
# Сценарий: пользователь быстро открывает и закрывает файл
await nav.show_screen(modal1, modal=True)  # Enqueue операция 1
await nav.show_screen(modal2, modal=True)  # Enqueue операция 2
await nav.hide_screen(modal1)               # Enqueue операция 3

# NavigationManager гарантирует:
# 1. modal1 откроется
# 2. modal2 откроется (поверх modal1)
# 3. modal1 закроется (но modal2 остается открытым)
```

### 5.2 Циклические обновления

```python
# Сценарий: ViewModel.show() вызывает open, 
# что триггерит подписку ViewModel.is_visible, 
# что снова вызывает show()

# NavigationStateSync предотвращает:
# 1. Отслеживает флаг _sync_in_progress для каждого ViewModel
# 2. При синхронизации UX -> ViewModel, игнорирует ViewModel -> UX
# 3. Таким образом избегается бесконечный loop
```

### 5.3 Ошибки и recovery

```python
# Сценарий: push_screen() выбрасывает исключение

try:
    await nav.show_screen(modal)
except NavigationError as e:
    # Состояние NavigationManager остается консистентно:
    # - Экран не зарегистрирован в tracker
    # - OperationQueue очищается
    # - ViewModel.is_visible остается False
    logger.error(f"Navigation failed: {e}")
```

---

## 6. API Reference

### NavigationError

```python
class NavigationError(Exception):
    """Базовое исключение для навигационных ошибок."""
    
    # Подклассы:
    # - ScreenStackError: Попытка операции с невалидным стеком экранов
    # - ModalNotFoundError: Модальное окно не найдено
    # - OperationTimeoutError: Операция превысила таймаут
    # - OperationQueueError: Ошибка в очереди операций
```

### Логирование

```python
# NavigationManager логирует все операции:
logger.debug("navigation_operation_enqueued", 
    operation_type="show_screen",
    modal_type="file_viewer", 
    priority=0,
    queue_depth=2)

logger.debug("navigation_operation_executed",
    operation_type="show_screen",
    duration_ms=45)

logger.warning("navigation_operation_failed",
    operation_type="show_screen",
    error="ScreenStackError",
    reason="invalid_state")
```

---

## 7. Тестирование

### 7.1 Unit тесты для OperationQueue

```python
# test_operation_queue.py

async def test_operations_execute_sequentially():
    """Проверить, что операции выполняются в порядке приоритета."""
    queue = OperationQueue()
    executed = []
    
    async def executor(op):
        executed.append(op.priority)
    
    queue.set_executor(executor)
    
    # Enqueue с разными приоритетами
    await queue.enqueue(NavigationOperation(..., priority=1))  # Выполнится 3-й
    await queue.enqueue(NavigationOperation(..., priority=10)) # Выполнится 1-й
    await queue.enqueue(NavigationOperation(..., priority=5))  # Выполнится 2-й
    
    assert executed == [10, 5, 1]
```

### 7.2 Integration тесты для NavigationManager

```python
# test_navigation_manager_integration.py

async def test_show_and_hide_screen():
    """Проверить основной flow открытия и закрытия экрана."""
    app = create_test_app()
    nav = NavigationManager(app)
    
    screen = ModalScreen()
    await nav.show_screen(screen, modal=True)
    
    assert nav.get_screen_stack_depth() == 1
    
    await nav.hide_screen(screen)
    
    assert nav.get_screen_stack_depth() == 0
```

### 7.3 Тесты синхронизации ViewModels

```python
# test_navigation_state_sync.py

async def test_view_model_sync():
    """Проверить синхронизацию ViewModel.is_visible с реальной навигацией."""
    nav = NavigationManager(app)
    sync = NavigationStateSync(nav)
    vm = FileViewerViewModel()
    
    unsubscribe = sync.sync_view_model(
        vm,
        "file_viewer",
        lambda: FileViewerModal(file_viewer_vm=vm),
    )
    
    # Установить is_visible = True
    vm.show_file(Path("test.py"), "print('hello')")
    await asyncio.sleep(0.1)  # Дать время обработаться
    
    assert nav.is_modal_visible("file_viewer")
    
    # Установить is_visible = False
    vm.hide()
    await asyncio.sleep(0.1)
    
    assert not nav.is_modal_visible("file_viewer")
    
    unsubscribe()
```

---

## 8. Roadmap реализации

### Phase 1: Core NavigationManager
- [ ] Создать NavigationManager класс с базовым API
- [ ] Реализовать show_screen() и hide_screen()
- [ ] Интегрировать с App для управления screen stack
- [ ] Добавить базовое логирование

### Phase 2: OperationQueue и ModalWindowTracker
- [ ] Создать OperationQueue с последовательным выполнением
- [ ] Реализовать приоритизацию операций
- [ ] Создать ModalWindowTracker для отслеживания модалей
- [ ] Добавить тесты для обоих компонентов

### Phase 3: NavigationStateSync
- [ ] Создать NavigationStateSync для синхронизации ViewModels
- [ ] Реализовать механизм предотвращения циклических обновлений
- [ ] Добавить subscribe_to_view_model() в NavigationManager
- [ ] Интегрировать с DIContainer

### Phase 4: Миграция существующего кода
- [ ] Обновить app.py для использования NavigationManager
- [ ] Обновить компоненты (file_viewer, permission_modal, terminal_log_modal)
- [ ] Обновить bootstrap код для синхронизации ViewModels
- [ ] Запустить тесты и убедиться в отсутствии регрессий

### Phase 5: Документация и примеры
- [ ] Создать примеры использования
- [ ] Обновить README с информацией о NavigationManager
- [ ] Добавить диаграммы в документацию
- [ ] Создать troubleshooting guide для common issues

---

## 9. Критерии успеха

✅ **Функциональные:**
- Все операции навигации проходят через NavigationManager
- Нет ScreenStackError при одновременных операциях
- Состояние ViewModel синхронизировано с реальной навигацией
- Операции выполняются в правильном порядке (с учетом приоритета)

✅ **Надежность:**
- Нет race condition между push_screen() и dismiss()
- Нет двойных вызовов dismiss()
- Циклические обновления ViewModel -> UI -> ViewModel исключены
- Все ошибки обрабатываются и логируются

✅ **Производительность:**
- Операции навигации выполняются < 100ms
- Очередь не требует значительной памяти
- Подписки ViewModel синхронизируются эффективно

✅ **Поддерживаемость:**
- API интуитивен и прост в использовании
- Код хорошо покрыт тестами
- Логирование помогает диагностировать проблемы
- Документация полна и актуальна

---

## 10. Ссылки на сопутствующие документы

- [`acp-client/src/acp_client/tui/app.py`](../../acp-client/src/acp_client/tui/app.py) - главное приложение
- [`acp-client/src/acp_client/tui/components/file_viewer.py`](../../acp-client/src/acp_client/tui/components/file_viewer.py) - компонент файлового просмотрщика
- [`acp-client/src/acp_client/presentation/ui_view_model.py`](../../acp-client/src/acp_client/presentation/ui_view_model.py) - ViewModel для UI
- [`acp-client/src/acp_client/presentation/base_view_model.py`](../../acp-client/src/acp_client/presentation/base_view_model.py) - базовый класс для ViewModels
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - общая архитектура проекта
