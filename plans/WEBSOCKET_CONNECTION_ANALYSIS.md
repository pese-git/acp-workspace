# Анализ проблемы с подключением WebSocket при создании новой сессии

## Резюме проблемы

При вызове Ctrl+N в TUI приложении (`action_new_session()`) не происходит корректного подключения к WebSocket серверу. Соединение либо не устанавливается, либо разрывается неожиданно.

---

## 1. Текущая архитектура подключения

### 1.1 Жизненный цикл приложения (on_ready)

**Файл:** `acp-client/src/acp_client/tui/app.py` (строки 138-189)

```python
def on_ready(self) -> None:
    """Запускается когда приложение готово к работе."""
    # ... инициализация NavigationManager ...
    
    # Инициализируем подключение к серверу в worker
    self.run_worker(self._initialize_connection(), exclusive=False)

async def _initialize_connection(self) -> None:
    """Инициализирует подключение к серверу."""
    coordinator = self._container.resolve(SessionCoordinator)
    
    # Вызывается initialize через coordinator
    server_info = await coordinator.initialize()
    
    # Обновляем UI статус
    self._ui_vm.set_connection_status(ConnectionStatus.CONNECTED)
```

**Что происходит:**
- При старте приложения вызывается `coordinator.initialize()`
- Это запускает `InitializeUseCase.execute()`

### 1.2 InitializeUseCase.execute() - проблемная область

**Файл:** `acp-client/src/acp_client/application/use_cases.py` (строки 60-126)

```python
async def execute(self) -> InitializeResponse:
    """Инициализирует соединение с сервером."""
    try:
        # Подключаемся к серверу
        await self._transport.connect()  # Открывает WebSocket
        self._logger.info("connected_to_server")
        
        # Отправляем initialize запрос
        init_request = ACPMessage.request("initialize", {})
        await self._transport.send(init_request.to_dict())
        
        # Получаем ответ
        response_data = await self._transport.receive()
        response = ACPMessage.from_dict(response_data)
        
        # Возвращаем информацию о сервере
        return InitializeResponse(...)
    except Exception as e:
        raise RuntimeError(error_msg) from e
```

**Проблема:** После завершения метода WebSocket соединение **закрывается**.

### 1.3 CreateSessionUseCase при Ctrl+N

**Файл:** `acp-client/src/acp_client/tui/app.py` (строка 190-196)

```python
def action_new_session(self) -> None:
    """Создает новую сессию по горячей клавише Ctrl+N."""
    self._app_logger.info("new_session_requested")
    self.run_worker(
        self._session_vm.create_session_cmd.execute(self._host, self._port),
        exclusive=False
    )
```

**Что происходит:**
- SessionViewModel вызывает `create_session_cmd.execute()`
- Это запускает `CreateSessionUseCase.execute()`

### 1.4 CreateSessionUseCase.execute() - состояние соединения

**Файл:** `acp-client/src/acp_client/application/use_cases.py` (строки 149-276)

```python
async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
    """Создает новую сессию."""
    try:
        # Проверяет состояние подключения
        if not self._transport.is_connected():  # ← ПРОБЛЕМА!
            await self._transport.connect()     # ← Переподключение
            self._logger.info("connected_to_server")
        
        # Отправляет еще один initialize запрос
        init_request = ACPMessage.request("initialize", {})
        await self._transport.send(init_request.to_dict())
        
        # ... далее обработка аутентификации и создания сессии ...
```

---

## 2. Корневая причина проблемы

### 2.1 Жизненный цикл WebSocket соединения

**Текущее поведение:**

```
┌─────────────────────────────────────────────────────────────┐
│ ACPClientApp запускается                                    │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ on_ready() → _initialize_connection()                       │
│ ├─ coordinator.initialize()                                 │
│ │  ├─ transport.connect()           ◄─ Соединение открыто  │
│ │  ├─ send("initialize")                                    │
│ │  └─ receive()                                             │
│ └─ transport._transport = None       ◄─ Соединение ЗАКРЫТО  │
└─────────────────────────────────────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
    Пользователь нажимает     Время течет...
    Ctrl+N (Создать сессию)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ action_new_session()                                        │
│ ├─ create_session_cmd.execute()                             │
│ │  ├─ if not is_connected():  ◄─ TRUE (соединение закрыто) │
│ │  │  └─ transport.connect()  ◄─ ПЕРЕПОДКЛЮЧЕНИЕ           │
│ │  ├─ send("initialize")                                    │
│ │  └─ receive()                                             │
│ │  ├─ send("authenticate")  (если требуется)               │
│ │  ├─ send("session/new")                                   │
│ │  └─ receive()                                             │
│ └─ ...                                                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Где закрывается соединение?

**Файл:** `acp-client/src/acp_client/infrastructure/services/acp_transport_service.py` (строки 53-76)

```python
async def connect(self) -> None:
    """Устанавливает соединение с сервером."""
    if self.is_connected():
        return
    
    try:
        self._transport = WebSocketTransport(host=self.host, port=self.port)
        # ⚠️ ПРОБЛЕМА: Используется __aenter__ для открытия
        self._transport = await self._transport.__aenter__()
        self._logger.info("connected_to_server")
    except Exception as e:
        self._transport = None
        raise RuntimeError(msg) from e
```

**Файл:** `acp-client/src/acp_client/infrastructure/transport.py` (строки 110-133)

```python
async def __aenter__(self) -> WebSocketTransport:
    """Открывает WebSocket соединение."""
    url = f"ws://{self.host}:{self.port}{self.path}"
    try:
        self._http_session = ClientSession()
        self._ws = await self._http_session.ws_connect(url)
        return self
    except Exception as e:
        if self._http_session is not None:
            await self._http_session.close()
        raise RuntimeError(msg) from e
```

**Где закрывается:**

`InitializeUseCase.execute()` не использует context manager, поэтому соединение остается открытым после `execute()`. Но проблема в том, что **соединение не persists между вызовами**.

---

## 3. Диагностика

### 3.1 Проверка метода is_connected()

**Файл:** `acp-client/src/acp_client/infrastructure/services/acp_transport_service.py` (строки 152-162)

```python
def is_connected(self) -> bool:
    """Проверяет, подключен ли транспорт к серверу."""
    return self._transport is not None
```

**Проблема:** Просто проверяет, не None ли `_transport`, но не проверяет реальное состояние WebSocket соединения.

### 3.2 Последовательность событий

| Время | События |
|-------|---------|
| T1 | `on_ready()` вызывает `coordinator.initialize()` |
| T2 | `InitializeUseCase.execute()` открывает соединение |
| T3 | Отправляет `initialize` запрос и получает ответ |
| T4 | Метод завершается, но соединение остается в `_transport` |
| T5 | Пользователь нажимает Ctrl+N |
| T6 | `action_new_session()` вызывает `create_session_cmd.execute()` |
| T7 | `CreateSessionUseCase` проверяет `is_connected()` |
| T8 | Если соединение каким-то образом закрыто → переподключение |

---

## 4. Рекомендуемое решение

### Вариант 1: РЕКОМЕНДУЕТСЯ - Долгоживущее соединение

**Идея:** Открыть WebSocket в начале приложения и держать его открытым до завершения.

**Преимущества:**
- ✅ Минимальные изменения в коде
- ✅ Производительность (нет переподключений)
- ✅ Простотой для отладки
- ✅ Соответствует паттерну долгоживущих соединений

**Недостатки:**
- ❌ Соединение может разорваться по timeout'у
- ❌ Требует heartbeat/ping-pong для keep-alive

**Реализация:**

#### Шаг 1: Модифицировать InitializeUseCase

```python
async def execute(self) -> InitializeResponse:
    """Инициализирует соединение и получает информацию о сервере.
    
    Подключение остается открытым для дальнейшего использования.
    """
    try:
        # Подключаемся к серверу
        await self._transport.connect()
        self._logger.info("connected_to_server")
        
        # Отправляем initialize запрос
        from acp_client.messages import ACPMessage
        
        init_request = ACPMessage.request("initialize", {})
        await self._transport.send(init_request.to_dict())
        self._logger.debug("initialize_request_sent", request_id=init_request.id)
        
        # Получаем ответ с информацией о сервере
        response_data = await self._transport.receive()
        response = ACPMessage.from_dict(response_data)
        
        # Обработка ошибок от сервера
        if response.error is not None:
            error_msg = f"Initialize failed: {response.error.message}"
            self._logger.error("initialize_error", error_code=response.error.code)
            raise RuntimeError(error_msg)
        
        # ✅ Соединение остается открытым - не закрываем его!
        # Информация о подключении сохраняется в self._transport
        
        result = response.result or {}
        server_capabilities = result.get("serverCapabilities", {})
        available_auth_methods = result.get("authMethods", [])
        protocol_version = result.get("protocolVersion", "1.0")
        
        self._logger.info(
            "initialize_success",
            protocol_version=protocol_version,
            auth_methods_count=len(available_auth_methods),
        )
        
        return InitializeResponse(
            server_capabilities=server_capabilities,
            available_auth_methods=available_auth_methods,
            protocol_version=str(protocol_version),
        )
    
    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"Failed to initialize: {e}"
        self._logger.error("initialize_unexpected_error", error=str(e))
        raise RuntimeError(error_msg) from e
```

#### Шаг 2: Убедиться, что CreateSessionUseCase работает с открытым соединением

```python
async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
    """Создает новую сессию.
    
    Предполагает, что соединение уже открыто через initialize().
    """
    self._logger.info(
        "creating_session",
        host=request.server_host,
        port=request.server_port,
    )
    
    try:
        from acp_client.messages import ACPMessage
        
        # ✅ Проверяем подключение и переподключаемся если нужно
        if not self._transport.is_connected():
            self._logger.warning("connection_was_lost_reconnecting")
            await self._transport.connect()
            
            # Отправляем initialize снова при переподключении
            init_request = ACPMessage.request("initialize", {})
            await self._transport.send(init_request.to_dict())
            init_response_data = await self._transport.receive()
            init_response = ACPMessage.from_dict(init_response_data)
            
            if init_response.error is not None:
                error_msg = f"Initialize failed: {init_response.error.message}"
                self._logger.error("initialize_failed_during_session_create")
                raise RuntimeError(error_msg)
        
        # ... остальной код создания сессии без изменений ...
```

#### Шаг 3: Добавить graceful shutdown в on_unmount

```python
async def on_unmount(self) -> None:
    """Завершает приложение и закрывает соединение."""
    self._app_logger.info("app_unmounting")
    
    try:
        # Закрываем соединение с сервером
        coordinator = self._container.resolve(SessionCoordinator)
        if coordinator.transport.is_connected():
            await coordinator.transport.disconnect()
            self._app_logger.info("server_connection_closed")
    except Exception as e:
        self._app_logger.error("error_closing_connection", error=str(e))
```

---

### Вариант 2: Явный контроль соединения через SessionCoordinator

**Идея:** Добавить методы для управления жизненным циклом соединения.

```python
class SessionCoordinator:
    def __init__(self, transport: TransportService, session_repo: SessionRepository):
        self.transport = transport
        self.session_repo = session_repo
        self._logger = get_logger("session_coordinator")
        self._connection_active = False
    
    async def connect(self) -> None:
        """Открывает соединение и инициализирует его."""
        if self._connection_active:
            return
        
        await self.initialize()
        self._connection_active = True
    
    async def disconnect(self) -> None:
        """Закрывает соединение."""
        if not self._connection_active:
            return
        
        await self.transport.disconnect()
        self._connection_active = False
```

---

### Вариант 3: Использовать Context Manager в Application

**Идея:** Оборачивать весь жизненный цикл приложения в context manager.

```python
class ACPClientApp(App[None]):
    async def on_mount(self) -> None:
        """Монтирует приложение и открывает соединение."""
        # Открываем соединение при запуске
        self._transport = await self._initialize_connection().__aenter__()
    
    async def on_unmount(self) -> None:
        """Завершает приложение и закрывает соединение."""
        # Закрываем соединение при выходе
        await self._transport.__aexit__(None, None, None)
```

---

## 5. Сравнение вариантов

| Критерий | Вариант 1 | Вариант 2 | Вариант 3 |
|----------|-----------|----------|----------|
| Сложность | ⭐ Низкая | ⭐⭐ Средняя | ⭐⭐⭐ Высокая |
| Производительность | ⭐⭐⭐ Отличная | ⭐⭐ Хорошая | ⭐⭐⭐ Отличная |
| Поддерживаемость | ⭐⭐⭐ Хорошая | ⭐⭐⭐ Хорошая | ⭐ Сложная |
| Graceful Shutdown | ✅ Да | ✅ Да | ✅ Да |
| Keep-Alive требуется | ✅ Да | ✅ Да | ✅ Да |
| Обработка разрыва | ✅ Автоматическая | ✅ Явная | ⚠️ Сложная |

---

## 6. Шаги реализации (Вариант 1)

### 6.1 Модифицировать InitializeUseCase

**Файл:** `acp-client/src/acp_client/application/use_cases.py`

- Удалить комментарий о том, что соединение остается открытым
- Явно не закрывать соединение после execute()

### 6.2 Добавить keep-alive механизм (опционально)

**Файл:** `acp-client/src/acp_client/infrastructure/services/acp_transport_service.py`

```python
async def keep_alive(self) -> None:
    """Отправляет периодические ping запросы для сохранения соединения."""
    import asyncio
    from acp_client.messages import ACPMessage
    
    while self.is_connected():
        try:
            await asyncio.sleep(30)  # Каждые 30 секунд
            
            # Отправляем ping запрос
            ping_request = ACPMessage.request("ping", {})
            await self.send(ping_request.to_dict())
            
            # Получаем pong ответ
            response_data = await self.receive()
            self._logger.debug("keep_alive_ping_received")
        except Exception as e:
            self._logger.warning("keep_alive_ping_failed", error=str(e))
            break
```

### 6.3 Добавить graceful shutdown в ACPClientApp

**Файл:** `acp-client/src/acp_client/tui/app.py`

```python
async def on_unmount(self) -> None:
    """Завершает приложение и закрывает соединение."""
    self._app_logger.info("app_unmounting")
    
    try:
        coordinator = self._container.resolve(SessionCoordinator)
        if coordinator.transport.is_connected():
            await coordinator.transport.disconnect()
            self._app_logger.info("server_connection_closed")
    except Exception as e:
        self._app_logger.error("error_closing_connection", error=str(e))
```

### 6.4 Обновить тесты

- `test_initialize_use_case.py` - убедиться, что соединение остается открытым
- `test_create_session_use_case.py` - проверить повторное использование соединения

---

## 7. Проверочный список после реализации

- [ ] Приложение стартует и подключается к серверу в on_ready()
- [ ] Соединение остается открытым после initialize()
- [ ] Ctrl+N создает новую сессию без переподключения
- [ ] Соединение закрывается при завершении приложения
- [ ] При разрыве соединения происходит автоматическое переподключение
- [ ] Сессии корректно создаются и переключаются
- [ ] Нет утечек сокетов в логах
- [ ] Все тесты проходят: `make check`

---

## 8. Альтернативные причины (если проблема не в соединении)

Если проблема не связана с жизненным циклом соединения, проверьте:

1. **Неправильные параметры подключения:**
   - Хост и порт передаются корректно через `self._host` и `self._port`?
   - Совпадают ли они с параметрами сервера?

2. **Проблемы в SessionViewModel:**
   - Проверить `_create_session()` в `session_view_model.py` (строка 108)
   - Убедиться, что она вызывает `coordinator.create_session()` корректно

3. **Ошибки в messages:**
   - Проверить формат JSON-RPC сообщений
   - Убедиться, что ответ от сервера парсится корректно

4. **Проблемы в транспорте:**
   - Проверить логи WebSocket подключения
   - Убедиться, что порт на сервере открыт и слушает

---

## Заключение

**Корневая причина:** WebSocket соединение, открытое в `on_ready()` через `InitializeUseCase`, работает корректно, но **соединение должно persists между вызовами create_session**. 

**Решение:** Убедиться, что `ACPTransportService` сохраняет открытое соединение между вызовами `initialize()` и `create_session()`, а при разрыве - автоматически переподключается.

**Рекомендуемый подход:** Вариант 1 - долгоживущее соединение с graceful shutdown при завершении приложения.
