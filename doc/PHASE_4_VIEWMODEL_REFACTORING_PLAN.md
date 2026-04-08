# Phase 4: ViewModel Refactoring и TUI Enhancement 🎨

**Статус:** Детальное планирование  
**Дата:** 8 апреля 2026  
**Язык:** Русский  
**Фокус:** Завершение Phase 3 + Рефакторинг TUI на MVVM паттерн  

---

## 📋 Обзор Phase 4

### Цели
1. ✅ Завершить задачу **3.3 из Phase 3** — ViewModel Pattern для TUI
2. ✅ Переписать TUI компоненты с использованием ViewModels
3. ✅ Реализовать реактивные обновления через EventBus
4. ✅ Отделить UI logic от presentation слоя (MVVM паттерн)
5. ✅ Улучшить тестируемость и maintainability TUI

### Почему это важно?

**Текущее состояние TUI:**
- Компоненты напрямую работают с ACPClient
- Callback hell и сложные зависимости
- Сложно тестировать UI logic отдельно от Textual
- Трудно переиспользовать logic в других интерфейсах (CLI, REST API)

**После Phase 4:**
- ✅ Clear separation of concerns (ViewModel отвечает за logic, Component за UI)
- ✅ Реактивные обновления (UI автоматически обновляется при изменении state)
- ✅ Тестируемые ViewModels без Textual зависимостей
- ✅ Переиспользуемые ViewModels для разных интерфейсов
- ✅ Полная интеграция с Event-Driven архитектурой (Phase 3)

### Связь с Phase 3
- 🔗 Используем **EventBus** для публикации изменений
- 🔗 Используем **PluginSystem** для расширения ViewModels
- 🔗 Используем **DIContainer** для инъекции зависимостей
- 🔗 Применяем **DomainEvents** для отслеживания изменений

---

## 🏗️ Архитектура MVVM

```
┌──────────────────────────────────────────────────────────────┐
│                    Presentation Layer (View)                  │
│           TUI Components (ChatView, Sidebar, etc.)           │
│  - Только отвечают за отображение                           │
│  - Подписываются на ViewModel events                        │
│  - Никакой бизнес-логики!                                   │
└──────────────────────────────────┬───────────────────────────┘
                                   │
                    ┌──────────────▼────────────────┐
                    │   ViewModel Binding           │
                    │ (Observer pattern + EventBus) │
                    └──────────────┬────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────┐
│              ViewModel Layer (State + Logic)                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ SessionViewModel                                     │   │
│  │ ├─ session_state: Observable<SessionState>         │   │
│  │ ├─ selected_session_id: Observable<str>            │   │
│  │ ├─ sessions: Observable<list[Session]>             │   │
│  │ └─ load_sessions(), create_session(), switch()     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ChatViewModel                                        │   │
│  │ ├─ messages: Observable<list[Message]>              │   │
│  │ ├─ tool_calls: Observable<list[ToolCall]>           │   │
│  │ ├─ is_streaming: Observable<bool>                   │   │
│  │ └─ send_prompt(), process_updates()                 │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ UIViewModel                                          │   │
│  │ ├─ connection_status: Observable<ConnectionStatus>  │   │
│  │ ├─ is_loading: Observable<bool>                     │   │
│  │ ├─ error_message: Observable<str | None>            │   │
│  │ └─ show_notification(), handle_error()              │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬───────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
    ┌────▼─────┐          ┌────────▼────┐         ┌─────────▼──┐
    │ EventBus  │          │ DIContainer │         │ Plugins    │
    │ (events)  │          │ (deps)      │         │ (extend VM)│
    └───────────┘          └─────────────┘         └────────────┘
         │
    ┌────▼──────────────────────────────────────┐
    │   Application Layer (Use Cases)           │
    │  - SessionCoordinator                     │
    │  - ACPClient + Transport                  │
    │  - Handlers (permissions, fs, terminal)   │
    └─────────────────────────────────────────┘
```

---

## 📦 Task 4.1: ViewModel Base Architecture

### 4.1.1 Observable Properties System

**Файл:** `acp-client/src/acp_client/presentation/observable.py`

```python
from typing import TypeVar, Callable, Any
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class Observable:
    """Простое reactive свойство для ViewModel."""
    
    def __init__(self, initial_value: T):
        self._value = initial_value
        self._observers: list[Callable[[T], None]] = []
    
    @property
    def value(self) -> T:
        """Get текущее значение."""
        return self._value
    
    @value.setter
    def value(self, new_value: T) -> None:
        """Set новое значение и уведомить observers."""
        if self._value != new_value:
            self._value = new_value
            self._notify_observers()
    
    def subscribe(self, observer: Callable[[T], None]) -> Callable[[], None]:
        """Subscribe на изменения. Возвращает функцию для unsubscribe."""
        self._observers.append(observer)
        return lambda: self._observers.remove(observer)
    
    def _notify_observers(self) -> None:
        """Уведомить всех observers об изменении."""
        for observer in self._observers:
            observer(self._value)

class ObservableCommand:
    """Команда, которая может выполняться и уведомлять об состоянии."""
    
    def __init__(self, handler: Callable[..., Any]):
        self.handler = handler
        self.is_executing = Observable(False)
        self.error = Observable(None)
    
    async def execute(self, *args, **kwargs) -> Any:
        """Выполнить команду с обработкой ошибок."""
        self.is_executing.value = True
        self.error.value = None
        try:
            return await self.handler(*args, **kwargs)
        except Exception as e:
            self.error.value = str(e)
            raise
        finally:
            self.is_executing.value = False
```

### 4.1.2 ViewModel Base Class

**Файл:** `acp-client/src/acp_client/presentation/base_view_model.py`

```python
from abc import ABC
from typing import Any
import structlog

class BaseViewModel(ABC):
    """Базовый класс для всех ViewModels."""
    
    def __init__(self, event_bus=None, logger=None):
        self.event_bus = event_bus
        self.logger = logger or structlog.get_logger()
        self._subscriptions: dict[str, Callable] = {}
    
    def on_event(self, event_type: type, handler: Callable) -> None:
        """Подписаться на доменное событие."""
        if self.event_bus:
            self.event_bus.subscribe(event_type, handler)
    
    def publish_event(self, event) -> None:
        """Опубликовать событие."""
        if self.event_bus:
            self.event_bus.publish(event)
    
    def cleanup(self) -> None:
        """Очистить subscriptions при уничтожении."""
        for unsubscribe in self._subscriptions.values():
            unsubscribe()
        self._subscriptions.clear()

# Импортируется из Phase 3
from acp_client.domain.events import (
    SessionCreatedEvent,
    SessionInitializedEvent,
    PromptStartedEvent,
    PromptCompletedEvent,
    PermissionRequestedEvent,
    ErrorOccurredEvent,
)
```

---

## 📦 Task 4.2: SessionViewModel

**Файл:** `acp-client/src/acp_client/presentation/session_view_model.py`

```python
from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable, ObservableCommand
from acp_client.domain.entities import Session
from acp_client.application.session_coordinator import SessionCoordinator

class SessionViewModel(BaseViewModel):
    """ViewModel для управления сессиями."""
    
    def __init__(self, coordinator: SessionCoordinator, event_bus=None):
        super().__init__(event_bus)
        self.coordinator = coordinator
        
        # Observable properties
        self.sessions = Observable([])
        self.selected_session_id = Observable(None)
        self.is_loading_sessions = Observable(False)
        self.error_message = Observable(None)
        
        # Commands
        self.load_sessions_cmd = ObservableCommand(self._load_sessions)
        self.create_session_cmd = ObservableCommand(self._create_session)
        self.switch_session_cmd = ObservableCommand(self._switch_session)
        
        # Subscribe на события
        self.on_event(SessionCreatedEvent, self._handle_session_created)
        self.on_event(SessionInitializedEvent, self._handle_session_initialized)
    
    async def _load_sessions(self) -> None:
        """Загрузить список сессий."""
        sessions = await self.coordinator.load_sessions()
        self.sessions.value = sessions
    
    async def _create_session(self, host: str, port: int) -> None:
        """Создать новую сессию."""
        session = await self.coordinator.create_session(host, port)
        self.selected_session_id.value = session.id
    
    async def _switch_session(self, session_id: str) -> None:
        """Переключиться на другую сессию."""
        self.selected_session_id.value = session_id
    
    def _handle_session_created(self, event: SessionCreatedEvent) -> None:
        """Обработать событие создания сессии."""
        self.logger.info("Session created", session_id=event.session_id)
    
    def _handle_session_initialized(self, event: SessionInitializedEvent) -> None:
        """Обработать событие инициализации сессии."""
        self.logger.info("Session initialized", session_id=event.session_id)
```

---

## 📦 Task 4.3: ChatViewModel

**Файл:** `acp-client/src/acp_client/presentation/chat_view_model.py`

```python
from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable, ObservableCommand
from acp_client.application.session_coordinator import SessionCoordinator
from acp_client.domain.entities import Message, ToolCall

class ChatViewModel(BaseViewModel):
    """ViewModel для управления чатом и prompt-turn."""
    
    def __init__(self, coordinator: SessionCoordinator, event_bus=None):
        super().__init__(event_bus)
        self.coordinator = coordinator
        
        # Observable properties
        self.messages = Observable([])
        self.tool_calls = Observable([])
        self.is_streaming = Observable(False)
        self.pending_permissions = Observable([])
        
        # Commands
        self.send_prompt_cmd = ObservableCommand(self._send_prompt)
        self.cancel_prompt_cmd = ObservableCommand(self._cancel_prompt)
        self.approve_permission_cmd = ObservableCommand(self._approve_permission)
        
        # Subscribe на события
        self.on_event(PromptStartedEvent, self._handle_prompt_started)
        self.on_event(PromptCompletedEvent, self._handle_prompt_completed)
        self.on_event(PermissionRequestedEvent, self._handle_permission_requested)
    
    async def _send_prompt(self, session_id: str, prompt_text: str) -> None:
        """Отправить prompt в активную сессию."""
        self.is_streaming.value = True
        try:
            # SessionCoordinator handle updates и публикует события
            await self.coordinator.send_prompt(session_id, prompt_text)
        finally:
            self.is_streaming.value = False
    
    async def _cancel_prompt(self, session_id: str) -> None:
        """Отменить текущий prompt."""
        await self.coordinator.cancel_prompt(session_id)
    
    async def _approve_permission(self, session_id: str, permission_id: str, approved: bool) -> None:
        """Утвердить/отклонить разрешение."""
        await self.coordinator.handle_permission(session_id, permission_id, approved)
    
    def _handle_prompt_started(self, event: PromptStartedEvent) -> None:
        """Обработать начало prompt-turn."""
        self.is_streaming.value = True
    
    def _handle_prompt_completed(self, event: PromptCompletedEvent) -> None:
        """Обработать завершение prompt-turn."""
        self.is_streaming.value = False
    
    def _handle_permission_requested(self, event: PermissionRequestedEvent) -> None:
        """Обработать запрос разрешения."""
        self.pending_permissions.value.append({
            'session_id': event.session_id,
            'action': event.action,
            'resource': event.resource,
        })
```

---

## 📦 Task 4.4: UIViewModel

**Файл:** `acp-client/src/acp_client/presentation/ui_view_model.py`

```python
from enum import Enum
from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable

class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

class UIViewModel(BaseViewModel):
    """ViewModel для управления общим UI состоянием."""
    
    def __init__(self, event_bus=None):
        super().__init__(event_bus)
        
        # Observable properties
        self.connection_status = Observable(ConnectionStatus.DISCONNECTED)
        self.is_loading = Observable(False)
        self.error_message = Observable(None)
        self.info_message = Observable(None)
        self.active_modal = Observable(None)  # None, 'permission', 'settings', etc.
        
        # Subscribe на события
        self.on_event(ErrorOccurredEvent, self._handle_error)
    
    def show_error(self, message: str) -> None:
        """Показать сообщение об ошибке."""
        self.error_message.value = message
        self.logger.error("UI Error", message=message)
    
    def show_info(self, message: str) -> None:
        """Показать информационное сообщение."""
        self.info_message.value = message
        self.logger.info("UI Info", message=message)
    
    def set_connection_status(self, status: ConnectionStatus) -> None:
        """Установить статус соединения."""
        self.connection_status.value = status
    
    def show_modal(self, modal_type: str) -> None:
        """Показать модальное окно."""
        self.active_modal.value = modal_type
    
    def hide_modal(self) -> None:
        """Скрыть модальное окно."""
        self.active_modal.value = None
    
    def _handle_error(self, event: ErrorOccurredEvent) -> None:
        """Обработать ошибку."""
        self.show_error(event.error_message)
```

---

## 📦 Task 4.5: TUI Component Refactoring

### Структура компонентов (обновленная)

```
acp-client/src/acp_client/tui/
├── components/
│   ├── __init__.py
│   ├── chat_view.py          # ChatView (с SessionViewModel)
│   ├── sidebar.py            # Sidebar (с SessionViewModel)
│   ├── prompt_input.py       # PromptInput (с ChatViewModel)
│   ├── tool_panel.py         # ToolPanel (с ChatViewModel)
│   ├── permission_modal.py   # PermissionModal (с UIViewModel + ChatViewModel)
│   ├── header.py             # HeaderBar (с UIViewModel)
│   └── footer.py             # FooterBar (с UIViewModel)
├── bindings/
│   ├── __init__.py
│   └── view_model_binding.py # Утилиты для привязки ViewModel к компонентам
├── managers/
│   ├── __init__.py
│   ├── session.py            # SessionManager (удалить, logic в SessionViewModel)
│   ├── connection.py         # ConnectionManager (обновить)
│   └── handlers.py           # MessageHandlers (обновить)
└── app.py                    # ACPClientApp (интеграция всех ViewModels)
```

### Пример: ChatView с ViewModel

```python
# acp-client/src/acp_client/tui/components/chat_view.py

from textual.widget import Widget
from textual.containers import Container
from acp_client.presentation.chat_view_model import ChatViewModel

class ChatView(Container):
    """View для отображения сообщений и tool calls."""
    
    def __init__(self, chat_view_model: ChatViewModel):
        super().__init__()
        self.view_model = chat_view_model
        
        # Подписываемся на изменения в ViewModel
        self.view_model.messages.subscribe(self._on_messages_changed)
        self.view_model.tool_calls.subscribe(self._on_tool_calls_changed)
        self.view_model.is_streaming.subscribe(self._on_streaming_changed)
    
    def _on_messages_changed(self, messages: list) -> None:
        """Вызывается когда messages изменился в ViewModel."""
        self._render_messages(messages)
    
    def _on_tool_calls_changed(self, tool_calls: list) -> None:
        """Вызывается когда tool_calls изменился в ViewModel."""
        self._render_tool_calls(tool_calls)
    
    def _on_streaming_changed(self, is_streaming: bool) -> None:
        """Вызывается когда is_streaming изменился в ViewModel."""
        self._update_spinner(is_streaming)
    
    def _render_messages(self, messages: list) -> None:
        """Отобразить сообщения (только UI логика)."""
        # Здесь только отображение, никакой бизнес логики!
        pass
```

---

## 📦 Task 4.6: DI Container Integration

**Обновление:** `acp-client/src/acp_client/infrastructure/di_container.py`

```python
from acp_client.infrastructure.di_container import ContainerBuilder
from acp_client.presentation.session_view_model import SessionViewModel
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.ui_view_model import UIViewModel

# Обновить container setup
container_builder = (
    ContainerBuilder()
    # EventBus и PluginManager (уже есть из Phase 3)
    .register_singleton(EventBus, lambda: EventBus())
    .register_singleton(PluginManager, lambda di: PluginManager(...))
    
    # Новое: ViewModels
    .register_singleton(SessionViewModel, lambda di: SessionViewModel(
        coordinator=di.resolve(SessionCoordinator),
        event_bus=di.resolve(EventBus),
    ))
    .register_singleton(ChatViewModel, lambda di: ChatViewModel(
        coordinator=di.resolve(SessionCoordinator),
        event_bus=di.resolve(EventBus),
    ))
    .register_singleton(UIViewModel, lambda di: UIViewModel(
        event_bus=di.resolve(EventBus),
    ))
    
    # TUI компоненты (обновленные)
    .register_singleton(ChatView, lambda di: ChatView(
        chat_view_model=di.resolve(ChatViewModel),
    ))
    .register_singleton(Sidebar, lambda di: Sidebar(
        session_view_model=di.resolve(SessionViewModel),
    ))
    # ... остальные компоненты
    
    .build()
)
```

---

## 📦 Task 4.7: Plugin Support for ViewModels

**Файл:** `acp-client/src/acp_client/infrastructure/plugins/view_model_extensions.py`

```python
from abc import ABC, abstractmethod
from acp_client.presentation.base_view_model import BaseViewModel

class ViewModelExtension(ABC):
    """Базовый класс для расширения ViewModels через плагины."""
    
    @abstractmethod
    def extend_session_view_model(self, vm: SessionViewModel) -> None:
        """Расширить SessionViewModel."""
        pass
    
    @abstractmethod
    def extend_chat_view_model(self, vm: ChatViewModel) -> None:
        """Расширить ChatViewModel."""
        pass

# Пример использования в плагине:
class CustomHandlerPlugin(Plugin):
    """Плагин для добавления custom handler в ChatViewModel."""
    
    def initialize(self, context: PluginContext) -> None:
        chat_vm = context.di_container.resolve(ChatViewModel)
        
        # Добавить custom command
        chat_vm.my_custom_command = ObservableCommand(self._my_handler)
    
    async def _my_handler(self) -> None:
        """Custom логика."""
        pass
```

---

## 📊 Summary Table

| Task | Файлы | Строк | Тесты | Сложность |
|------|-------|-------|-------|-----------|
| 4.1: Observable & Base | observable.py, base_view_model.py | 200 | 12 | ⭐⭐ |
| 4.2: SessionViewModel | session_view_model.py | 150 | 10 | ⭐⭐⭐ |
| 4.3: ChatViewModel | chat_view_model.py | 180 | 12 | ⭐⭐⭐ |
| 4.4: UIViewModel | ui_view_model.py | 120 | 8 | ⭐⭐ |
| 4.5: Component Refactoring | components/*.py (7 files) | 600 | 20 | ⭐⭐⭐⭐ |
| 4.6: DI Integration | di_container.py (update) | 80 | 5 | ⭐⭐ |
| 4.7: Plugin Support | view_model_extensions.py | 100 | 8 | ⭐⭐⭐ |
| **ИТОГО** | **15+ files** | **1420** | **75** | **⭐⭐⭐** |

---

## 📋 Зависимости между задачами

```
┌─────────────────────────────────────────────────────────┐
│ 4.1: Observable & BaseViewModel (foundation)            │
│ ├─ Независимая, может быть реализована первой         │
└─┬───────────────────────────────────────────────────────┘
  │
  ├─→ 4.2: SessionViewModel
  │   ├─ Зависит от: 4.1, DIContainer, EventBus (Phase 3)
  │   └─ Может быть реализована сразу после 4.1
  │
  ├─→ 4.3: ChatViewModel
  │   ├─ Зависит от: 4.1, DIContainer, EventBus (Phase 3)
  │   └─ Может быть реализована параллельно с 4.2
  │
  ├─→ 4.4: UIViewModel
  │   ├─ Зависит от: 4.1, EventBus (Phase 3)
  │   └─ Может быть реализована параллельно с 4.2/4.3
  │
  ├─→ 4.5: Component Refactoring
  │   ├─ Зависит от: 4.2, 4.3, 4.4 (все ViewModels)
  │   ├─ Может начаться когда хотя бы 2-3 VM готовы
  │   └─ Может быть распараллелена (разные компоненты)
  │
  ├─→ 4.6: DI Integration
  │   ├─ Зависит от: 4.2, 4.3, 4.4
  │   └─ Нужна после завершения всех ViewModels
  │
  └─→ 4.7: Plugin Support
      ├─ Зависит от: 4.2, 4.3, 4.4, PluginSystem (Phase 3)
      └─ Можно реализовать параллельно с 4.5-4.6

Рекомендуемый порядок реализации:
1. 4.1 (2-3 дня) ← Foundation
2. 4.2, 4.3, 4.4 параллельно (2 недели)
3. 4.5 начинать когда 4.2-4.4 ~60% готовы (2 недели)
4. 4.6, 4.7 параллельно (1 неделя)

Общая длительность: 3-4 недели
```

---

## 🧪 Тестовая стратегия

### Unit тесты для ViewModels

```python
# tests/test_presentation_observable.py
async def test_observable_notify_observers():
    """Проверить что observers уведомляются об изменении."""
    obs = Observable(1)
    calls = []
    obs.subscribe(lambda x: calls.append(x))
    
    obs.value = 2
    assert calls == [2]

# tests/test_presentation_session_view_model.py
async def test_session_view_model_load_sessions():
    """Проверить загрузку сессий."""
    coordinator = Mock()
    coordinator.load_sessions.return_value = [mock_session()]
    
    vm = SessionViewModel(coordinator)
    await vm.load_sessions_cmd.execute()
    
    assert len(vm.sessions.value) == 1

# tests/test_presentation_chat_view_model.py
async def test_chat_view_model_send_prompt():
    """Проверить отправку prompt."""
    coordinator = Mock()
    vm = ChatViewModel(coordinator)
    
    await vm.send_prompt_cmd.execute("session1", "Hello")
    
    coordinator.send_prompt.assert_called_once()
```

### Integration тесты

```python
# tests/test_presentation_integration.py
async def test_view_models_with_event_bus():
    """Проверить что ViewModels корректно обрабатывают события."""
    event_bus = EventBus()
    session_vm = SessionViewModel(mock_coordinator(), event_bus)
    chat_vm = ChatViewModel(mock_coordinator(), event_bus)
    
    # Опубликовать событие
    event = SessionCreatedEvent(
        aggregate_id="1",
        occurred_at=datetime.now(),
        session_id="1",
        server_host="localhost",
        server_port=8080
    )
    event_bus.publish(event)
    
    # Проверить что обе ViewModels обработали событие
    # (например, сессия добавлена в список)
```

### E2E тесты TUI

```python
# tests/test_tui_with_view_models.py (Textual тесты)
async def test_chat_view_updates_on_messages_change():
    """Проверить что ChatView обновляется когда messages меняется в ViewModel."""
    app = ACPClientApp()
    async with app.run_test() as pilot:
        # Изменить messages в view_model
        await app.chat_vm.send_prompt_cmd.execute("session1", "Hello")
        
        # Проверить что ChatView отобразил сообщение
        chat_view = app.query_one(ChatView)
        assert "Hello" in chat_view.render()
```

---

## ✅ Критерии завершения Phase 4

### Функциональность
- ✅ Все ViewModels реализованы и протестированы
- ✅ Все TUI компоненты переписаны для использования ViewModels
- ✅ EventBus полностью интегрирован с TUI
- ✅ DI Container предоставляет все необходимые dependencies
- ✅ Plugin System поддерживает расширение ViewModels

### Качество кода
- ✅ 100% типизация (ty check --strict)
- ✅ Все тесты проходят (pytest, 75+)
- ✅ Код отформатирован (ruff format)
- ✅ Нет lint ошибок (ruff check)
- ✅ Покрытие тестами: ≥85%

### Документация
- ✅ Docstrings для всех публичных классов и методов
- ✅ Примеры использования ViewModels
- ✅ Обновленная архитектурная диаграмма
- ✅ Migration guide для компонентов
- ✅ README обновлен

### Backward Compatibility
- ✅ Старые managers работают параллельно (deprecated warnings)
- ✅ Существующие TUI работает без изменений
- ✅ API не сломана (только расширена)

---

## 📌 Следующие шаги

1. ✅ **Вы одобряете этот план** → переходим к Code режиму
2. **Обсуждение и уточнение** → если нужны изменения
3. **Реализация Phase 4** → в Code режиме по задачам 4.1-4.7

---

## ❓ Вопросы для обсуждения

1. **Observable Pattern**: Достаточно ли простой реализации, или нужна более продвинутая (RxPython)?
   
2. **Component Binding**: Какой способ привязки ViewModels к компонентам предпочитаете?
   - Через конструктор (как в примере)
   - Через property injection
   - Через service locator

3. **Timeline**: 3-4 недели приемлемо? Можем ускорить параллелизацией.

4. **Breaking Changes**: Нормально удалить старые managers (SessionManager, ConnectionManager)?

5. **Plugin Extensions**: Нужна ли поддержка расширения ViewModels через плагины (Task 4.7)?
