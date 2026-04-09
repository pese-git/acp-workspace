# Архитектурный план реализации `action_new_session()` в ACPClientApp

## Содержание

1. [Обзор задачи](#обзор-задачи)
2. [Текущее состояние](#текущее-состояние)
3. [Архитектурный анализ](#архитектурный-анализ)
4. [Дизайн решения](#дизайн-решения)
5. [Сигнатура метода](#сигнатура-метода)
6. [Последовательность операций](#последовательность-операций)
7. [Обработка ошибок](#обработка-ошибок)
8. [Взаимодействие с ViewModels](#взаимодействие-с-viewmodels)
9. [Примеры кода](#примеры-кода)
10. [Диаграмма взаимодействия](#диаграмма-взаимодействия)

---

## Обзор задачи

После удаления legacy кода необходимо добавить обработчик для создания новой сессии по горячей клавише `Ctrl+N`. Метод `action_new_session()` уже определен в `BINDINGS` класса [`ACPClientApp`](acp-client/src/acp_client/tui/app.py:50-63), но сама реализация отсутствует.

```python
BINDINGS = [
    ("ctrl+q", "quit", "Quit"),
    ("ctrl+n", "new_session", "New Session"),  # ← Привязка существует
    ...
]
```

---

## Текущее состояние

### Что уже есть в архитектуре

#### 1. SessionViewModel ([`session_view_model.py`](acp-client/src/acp_client/presentation/session_view_model.py))

**Observable команда для создания сессии:**
```python
self.create_session_cmd = ObservableCommand(self._create_session)
```

**Интерфейс использования:**
```python
await vm.create_session_cmd.execute(host: str, port: int, **kwargs)
```

**Что делает метод `_create_session()`:**
- Устанавливает флаг `is_loading_sessions = True`
- Вызывает `coordinator.create_session(host, port)`
- Добавляет новую сессию в список `sessions`
- Выбирает новую сессию (`selected_session_id = session.id`)
- Обновляет счетчик сессий
- Обрабатывает ошибки и устанавливает `error_message`
- Устанавливает флаг `is_loading_sessions = False` в `finally` блоке

#### 2. SessionCoordinator ([`session_coordinator.py`](acp-client/src/acp_client/application/session_coordinator.py))

**Метод создания сессии:**
```python
async def create_session(
    self,
    server_host: str,
    server_port: int,
    client_capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Создает новую сессию на сервере."""
```

**Возвращает:**
```python
{
    "session_id": str,
    "server_capabilities": dict,
    "is_authenticated": bool,
}
```

#### 3. ACPClientApp ([`app.py`](acp-client/src/acp_client/tui/app.py))

**Уже доступные ресурсы:**
- `self._host: str` — хост подключения (передается в `__init__`)
- `self._port: int` — порт подключения (передается в `__init__`)
- `self._session_vm: SessionViewModel` — ViewModel для управления сессиями
- `self._ui_vm: UIViewModel` — ViewModel для управления UI состоянием
- `self.run_worker(coroutine, exclusive=False)` — метод для запуска асинхронных операций
- `self._app_logger` — логгер приложения

**Паттерн для асинхронных операций:**
```python
async def _initialize_connection(self) -> None:
    """Инициализирует подключение к серверу."""
    # Асинхронная логика
    
def on_ready(self) -> None:
    """Запускается когда приложение готово."""
    self.run_worker(self._initialize_connection(), exclusive=False)
```

#### 4. UIViewModel ([`ui_view_model.py`](acp-client/src/acp_client/presentation/ui_view_model.py))

**Методы для управления UI состоянием:**
- `show_error(message: str, error_type: str | None = None)` — показать ошибку
- `show_info(message: str)` — показать инфо сообщение
- `set_loading(is_loading: bool)` — установить флаг загрузки
- `show_modal(modal_type: str, data: dict | None = None)` — показать модальное окно

---

## Архитектурный анализ

### Слои архитектуры (Clean Architecture)

```
TUI Layer (ACPClientApp)
    ↓ использует
Presentation Layer (SessionViewModel, UIViewModel)
    ↓ использует
Application Layer (SessionCoordinator)
    ↓ использует
Infrastructure Layer (Transport, Repository)
    ↓ использует
Domain Layer (Entities, Events)
```

### Поток данных при создании сессии

```
User Input (Ctrl+N)
    ↓
action_new_session() [TUI Layer]
    ↓ вызывает асинхронную операцию
SessionViewModel.create_session_cmd.execute(host, port) [Presentation]
    ↓ вызывает
SessionCoordinator.create_session(host, port) [Application]
    ↓ вызывает
TransportService.create_session() [Infrastructure]
    ↓ отправляет
ACP Protocol Request [Network]
    ↓ получает
ACP Protocol Response [Network]
    ↓ обновляет
SessionRepository [Infrastructure]
    ↓ возвращает результат
Observable свойства обновляются [Presentation]
    ↓ реактивно обновляется
UI компоненты (Sidebar) [TUI]
```

### Ключевые паттерны

#### 1. ObservableCommand Pattern
```python
create_session_cmd = ObservableCommand(self._create_session)
await create_session_cmd.execute(host, port)
```

**Преимущества:**
- Автоматическое управление состоянием загрузки (`is_executing`)
- Обработка ошибок через `error` Observable
- Асинхронное выполнение с отслеживанием статуса

#### 2. Observable Pattern для реактивных обновлений
```python
sessions.subscribe(lambda sessions: update_ui(sessions))
```

**Когда значение изменяется, все подписчики автоматически уведомляются.**

#### 3. Dependency Injection
```python
self._session_vm = self._container.resolve(SessionViewModel)
```

**SessionViewModel уже инициализирован через DI контейнер в `__init__` методе ACPClientApp.**

---

## Дизайн решения

### Выбранный подход: Через SessionViewModel

**Рекомендация:** Использовать ObservableCommand из SessionViewModel, так как:

1. ✅ **Разделение ответственности** — SessionViewModel отвечает за логику создания сессий
2. ✅ **Единственный источник истины** — вся логика обработки в одном месте
3. ✅ **Автоматическая обработка ошибок** — SessionViewModel уже имеет полную обработку
4. ✅ **Реактивные обновления** — UI автоматически обновляется через Observable
5. ✅ **Минимальный код** — нет дублирования логики

### Альтернативный подход: Через SessionCoordinator (не рекомендуется)

Если бы мы вызывали SessionCoordinator напрямую, нам бы пришлось:
- Дублировать логику обработки ошибок
- Вручную управлять флагами загрузки
- Вручную обновлять SessionViewModel

---

## Сигнатура метода

### Синхронный action метод (требуется Textual)

```python
def action_new_session(self) -> None:
    """Создает новую сессию по горячей клавише Ctrl+N.
    
    Вызывает асинхронную операцию создания сессии через SessionViewModel.
    Использует параметры подключения текущего приложения (host, port).
    
    Логирует:
    - Начало операции создания сессии
    - Ошибки при создании сессии (через SessionViewModel)
    """
```

### Переменные, используемые в методе

| Переменная | Тип | Источник | Назначение |
|-----------|-----|---------|-----------|
| `self._host` | `str` | конструктор `__init__` | хост сервера |
| `self._port` | `int` | конструктор `__init__` | порт сервера |
| `self._session_vm` | `SessionViewModel` | `__init__`, разрешено из DI | доступ к команде создания сессии |
| `self._app_logger` | `structlog.Logger` | `__init__` | логирование |

---

## Последовательность операций

### Шаг 1: Пользователь нажимает Ctrl+N

Textual вызывает `action_new_session()`

### Шаг 2: Инициация асинхронной операции

```python
def action_new_session(self) -> None:
    self._app_logger.info("new_session_requested")
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

**`run_worker()`:**
- Запускает асинхронную операцию в фоновом потоке
- `exclusive=False` позволяет запускать другие операции параллельно

### Шаг 3: SessionViewModel обрабатывает создание

```python
async def _create_session(self, host: str, port: int, **kwargs: Any) -> None:
    self.is_loading_sessions.value = True  # UI показывает загрузку
    self.error_message.value = None
    
    try:
        session = await self.coordinator.create_session(host, port, **kwargs)
        
        # Обновляем состояние
        sessions = self.sessions.value + [session]
        self.sessions.value = sessions
        self.session_count.value = len(sessions)
        self.selected_session_id.value = session.id
        
        self.logger.info("Session created successfully", session_id=session.id)
        
    except Exception as e:
        error_msg = f"Failed to create session: {str(e)}"
        self.error_message.value = error_msg
        self.logger.exception("Error creating session", error=str(e))
        
    finally:
        self.is_loading_sessions.value = False  # Загрузка завершена
```

### Шаг 4: SessionCoordinator отправляет запрос на сервер

```python
async def create_session(self, server_host: str, server_port: int, ...) -> dict:
    request = CreateSessionRequest(
        server_host=server_host,
        server_port=server_port,
        client_capabilities=client_capabilities,
    )
    
    response = await self.create_session_use_case.execute(request)
    
    return {
        "session_id": response.session_id,
        "server_capabilities": response.server_capabilities,
        "is_authenticated": response.is_authenticated,
    }
```

### Шаг 5: Observable свойства уведомляют подписчиков

```python
# Sidebar подписан на sessions и selected_session_id
session_vm.sessions.subscribe(self._on_sessions_changed)
session_vm.selected_session_id.subscribe(self._on_selected_session_changed)

# При изменении Observable значений автоматически вызываются callbacks
# которые обновляют UI
```

### Шаг 6: UI обновляется реактивно

- Sidebar показывает новую сессию в списке
- Новая сессия выбирается (выделяется)
- Chat View очищается для новой сессии

---

## Обработка ошибок

### Точки отказа и обработка

#### Точка 1: Сервер недоступен

```python
# SessionViewModel._create_session перехватывает исключение
except Exception as e:
    self.error_message.value = f"Failed to create session: {str(e)}"
    self.logger.exception("Error creating session")
```

**Результат:**
- Флаг `is_loading_sessions` устанавливается в `False`
- `error_message` обновляется
- SessionViewModel остается в консистентном состоянии
- UI может показать сообщение об ошибке (если подписан на `error_message`)

#### Точка 2: Ошибка во время запроса на сервер

```python
# SessionCoordinator.create_session обрабатывает через use case
# использующий TransportService
response = await self.create_session_use_case.execute(request)

if response.error is not None:
    raise RuntimeError(f"Server error: {response.error.message}")
```

**Результат:**
- Исключение поднимается в SessionViewModel
- Обрабатывается в `except` блоке `_create_session()`

#### Точка 3: Ошибка DI контейнера

```python
# Происходит в __init__ ACPClientApp, до action_new_session
self._session_vm = self._container.resolve(SessionViewModel)
```

**Результат:**
- Приложение не запустится, если SessionViewModel не может быть разрешен
- Это обрабатывается на уровне инициализации приложения

### Стратегия обработки ошибок в action_new_session()

**Опция 1: Пассивная обработка (РЕКОМЕНДУЕТСЯ)**

```python
def action_new_session(self) -> None:
    self._app_logger.info("new_session_requested")
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
    # Ошибки обрабатываются SessionViewModel
    # и доступны через error_message Observable
```

**Преимущества:**
- SessionViewModel отвечает за обработку ошибок
- UI может реактивно показывать ошибки
- Простой и понятный код

**Опция 2: Активная обработка (альтернатива)**

```python
def action_new_session(self) -> None:
    self._app_logger.info("new_session_requested")
    self.run_worker(self._create_new_session_impl(), exclusive=False)

async def _create_new_session_impl(self) -> None:
    try:
        await self._session_vm.create_session_cmd.execute(
            self._host, 
            self._port
        )
        # Можно добавить дополнительную логику после успеха
        self._ui_vm.show_info("Session created successfully")
    except Exception as e:
        self._app_logger.error("Failed to create session", error=str(e))
        self._ui_vm.show_error(f"Failed to create session: {str(e)}")
```

**Недостатки:**
- Дублирование обработки ошибок
- UIViewModel может быть не инициализирован правильно для всех типов ошибок

---

## Взаимодействие с ViewModels

### SessionViewModel

**Observable свойства:**
```python
sessions: Observable[list[Any]]
selected_session_id: Observable[str | None]
is_loading_sessions: Observable[bool]
error_message: Observable[str | None]
session_count: Observable[int]
```

**Команда для создания сессии:**
```python
create_session_cmd: ObservableCommand
```

**Использование в action_new_session():**
```python
await self._session_vm.create_session_cmd.execute(self._host, self._port)
```

### UIViewModel (опционально)

**Может использоваться для:**
- Отображения глобальной ошибки: `ui_vm.show_error(message)`
- Отображения информационного сообщения: `ui_vm.show_info(message)`
- Управления флагом загрузки: `ui_vm.set_loading(True/False)`

**Но в базовом случае это не требуется**, так как SessionViewModel уже управляет состоянием загрузки через `is_loading_sessions`.

### Sidebar (компонент, зависит от SessionViewModel)

**Подписан на:**
```python
session_vm.sessions.subscribe(self._on_sessions_changed)
session_vm.selected_session_id.subscribe(self._on_selected_session_changed)
```

**Автоматически обновляется когда:**
- `sessions` изменяется → Sidebar показывает новый список
- `selected_session_id` изменяется → Sidebar выделяет новую сессию

---

## Примеры кода

### Пример 1: Базовая реализация (РЕКОМЕНДУЕТСЯ)

```python
# В файле acp-client/src/acp_client/tui/app.py

def action_new_session(self) -> None:
    """Создает новую сессию по горячей клавише Ctrl+N.
    
    Инициирует асинхронную операцию создания новой сессии
    используя параметры подключения текущего приложения.
    """
    self._app_logger.info("new_session_requested")
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

**Размещение в классе:**
```python
class ACPClientApp(App[None]):
    # ... существующий код ...
    
    async def _initialize_connection(self) -> None:
        # ... существующий код ...
    
    def action_new_session(self) -> None:  # ← ДОБАВИТЬ ЗДЕСЬ
        """Создает новую сессию по горячей клавише Ctrl+N."""
        self._app_logger.info("new_session_requested")
        self.run_worker(
            self._session_vm.create_session_cmd.execute(self._host, self._port),
            exclusive=False
        )
    
    async def on_unmount(self) -> None:
        # ... существующий код ...
```

### Пример 2: С проверкой соединения

```python
def action_new_session(self) -> None:
    """Создает новую сессию, если соединение установлено."""
    from acp_client.presentation.ui_view_model import ConnectionStatus
    
    self._app_logger.info("new_session_requested")
    
    # Проверяем статус соединения
    if self._ui_vm.connection_status.value != ConnectionStatus.CONNECTED:
        self._app_logger.warning("Cannot create session: not connected")
        self._ui_vm.show_error("Cannot create session: server is not connected")
        return
    
    # Запускаем создание сессии
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

**Дополнительная логика:**
- Проверяет, подключено ли приложение к серверу
- Показывает ошибку в UI если соединения нет
- Запускает создание сессии только если соединение активно

### Пример 3: С обработкой конфликтов

```python
def action_new_session(self) -> None:
    """Создает новую сессию, если нет активной операции."""
    self._app_logger.info("new_session_requested")
    
    # Проверяем, не идет ли уже загрузка сессий
    if self._session_vm.is_loading_sessions.value:
        self._app_logger.warning("Session creation already in progress")
        self._ui_vm.show_warning("A session operation is already in progress")
        return
    
    # Запускаем создание сессии
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

**Дополнительная логика:**
- Предотвращает запуск нескольких операций создания одновременно
- Уведомляет пользователя если операция уже выполняется

---

## Диаграмма взаимодействия

### Диаграмма последовательности

```
User              ACPClientApp        SessionViewModel      SessionCoordinator   TransportService
 │                     │                     │                      │                   │
 │  Ctrl+N             │                     │                      │                   │
 ├────────────────────>│                     │                      │                   │
 │                     │ action_new_session()                        │                   │
 │                     │                     │                      │                   │
 │                     │ run_worker(cmd.execute(...))                │                   │
 │                     │                     │                      │                   │
 │                     │  async execute()    │                      │                   │
 │                     ├────────────────────>│                      │                   │
 │                     │                     │ is_loading=True      │                   │
 │                     │                     │                      │                   │
 │                     │                     │ create_session()     │                   │
 │                     │                     ├─────────────────────>│                   │
 │                     │                     │                      │ create_session()  │
 │                     │                     │                      ├──────────────────>│
 │                     │                     │                      │                   │
 │                     │                     │                      │ ACP Request ──────┤
 │                     │                     │                      │                   │
 │                     │                     │                      │ ◄── ACP Response  │
 │                     │                     │                      │                   │
 │                     │                     │                      │<─ session_data ──│
 │                     │                     │<─────────────────────┤                   │
 │                     │                     │                      │                   │
 │                     │                     │ sessions.value +=    │                   │
 │                     │                     │ selected_session_id =│                   │
 │                     │                     │ is_loading=False     │                   │
 │                     │                     │                      │                   │
 │                     │◄────────────────────┤                      │                   │
 │                     │                     │                      │                   │
 │  UI обновляется    │                     │                      │                   │
 │◄─────────────────────────────────────────┤                      │                   │
 │ (Sidebar показывает│                     │                      │                   │
 │  новую сессию)     │                     │                      │                   │
 │                    │                     │                      │                   │
```

### Диаграмма компонентов

```
┌─────────────────────────────────────────────────────────┐
│                    TUI Layer                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │        ACPClientApp                              │   │
│  │  - action_new_session()                          │   │
│  │  - _session_vm, _ui_vm                           │   │
│  │  - run_worker()                                  │   │
│  └────────────┬─────────────────────────────────────┘   │
└───────────────┼─────────────────────────────────────────┘
                │ использует
┌───────────────▼─────────────────────────────────────────┐
│              Presentation Layer                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │     SessionViewModel                             │   │
│  │  - create_session_cmd: ObservableCommand         │   │
│  │  - _create_session(host, port)                   │   │
│  │  - sessions, selected_session_id Observable      │   │
│  │  - is_loading_sessions, error_message Observable │   │
│  └────────────┬─────────────────────────────────────┘   │
└───────────────┼─────────────────────────────────────────┘
                │ использует
┌───────────────▼─────────────────────────────────────────┐
│               Application Layer                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │      SessionCoordinator                          │   │
│  │  - create_session(host, port)                    │   │
│  │  - использует CreateSessionUseCase               │   │
│  └────────────┬─────────────────────────────────────┘   │
└───────────────┼─────────────────────────────────────────┘
                │ использует
┌───────────────▼─────────────────────────────────────────┐
│             Infrastructure Layer                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │      TransportService                            │   │
│  │  - connect()                                     │   │
│  │  - send(), receive()                             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Диаграмма состояний

```
                    ┌─────────────────────┐
                    │  INITIAL_STATE      │
                    │ is_loading=False    │
                    │ error=None          │
                    └──────────┬──────────┘
                               │
                    Ctrl+N нажата
                    action_new_session()
                               │
                               ▼
                    ┌─────────────────────┐
                    │  LOADING_STATE      │
                    │ is_loading=True     │
                    │ error=None          │
                    └────────┬──────┬─────┘
                             │      │
                    Успех    │      │    Ошибка
                             │      │
         ┌───────────────────▼─┐  ┌─▼──────────────────┐
         │   SUCCESS_STATE     │  │   ERROR_STATE      │
         │ is_loading=False    │  │ is_loading=False   │
         │ sessions += new     │  │ error="msg"        │
         │ selected=new_id     │  │                    │
         │ error=None          │  │                    │
         └─────────────────────┘  └────────────────────┘
                    │                      │
                    └──────────┬───────────┘
                               │
                   Пользователь нажимает Ctrl+N снова
                               │
                               ▼
                    ┌─────────────────────┐
                    │  LOADING_STATE      │
                    │ is_loading=True     │
                    │ error=None (очищено)│
                    └─────────────────────┘
```

---

## Резюме

### Решение

Реализовать `action_new_session()` как синхронный метод в [`ACPClientApp`](acp-client/src/acp_client/tui/app.py:43-189), который:

1. Логирует начало операции
2. Запускает асинхронную операцию через `self.run_worker()`
3. Вызывает `self._session_vm.create_session_cmd.execute(self._host, self._port)`

### Основная реализация

```python
def action_new_session(self) -> None:
    """Создает новую сессию по горячей клавише Ctrl+N."""
    self._app_logger.info("new_session_requested")
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

### Размещение

Добавить метод в класс [`ACPClientApp`](acp-client/src/acp_client/tui/app.py:43-189) после метода `on_ready()` или перед `on_unmount()`.

### Преимущества этого подхода

✅ **Архитектурная чистота** — используется существующий SessionViewModel  
✅ **Разделение ответственности** — SessionViewModel обрабатывает ошибки  
✅ **Реактивные обновления** — UI автоматически обновляется через Observable  
✅ **Минимальный код** — всего 5 строк кода  
✅ **Совместимость** — соответствует паттернам проекта  
✅ **Тестируемость** — компоненты легко тестировать отдельно  

### Обработка ошибок

- Ошибки сетевых запросов обрабатываются в SessionViewModel
- UI компоненты могут подписаться на `error_message` Observable
- Приложение остается в консистентном состоянии при любых ошибках
