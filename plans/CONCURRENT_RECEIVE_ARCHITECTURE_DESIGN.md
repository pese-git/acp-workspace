# Архитектурное решение: Message Routing для Concurrent Receive()

## Проблема (Проблема со Race Condition)

```
Текущая архитектура:
┌─────────────────────────────────────────┐
│  request_with_callbacks(session/prompt) │
│  - send(request)                        │
│  - while True:                          │
│      receive()  ◄─── БЛОКИРУЕТ ВЫЗЫВАЮЩУЮ ЗАДАЧУ
│      if response.id == request.id:      │
│          return response                │
└─────────────────────────────────────────┘

Проблема: Вторая сессия не может вызвать receive() одновременно!
- Сеанс 1: request_with_callbacks("session/prompt") получает updates
- Сеанс 2: попытка отправить request → нужен receive() → RuntimeError
```

**Требования ACP протокола, которые усложняют проблему:**

1. **Множественные сессии на одном WebSocket** — каждая с `sessionId`
2. **Асинхронные уведомления** — `session/update` (без `response_id`, по методу)
3. **Синхронные ответы** — `session/request_permission` (требует ответа)
4. **Одно WebSocket соединение** — нельзя разрывать при смене сессии
5. **Один receive() одновременно** — ограничение aiohttp, не проблема клиента

---

## Решение: Message Routing System

### 1. Архитектурная Диаграмма

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ACPTransportService                             │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │        Background Receive Loop (фоновая задача)             │  │
│  │  - Единственный вызов receive() на WebSocket              │  │
│  │  - Диспетчеризирует сообщения по routing queues           │  │
│  │  - Обрабатывает lifecycle (reconnect, shutdown)           │  │
│  └─────────────────────────────────────────────────────────────┘  │
│              │                                                      │
│              ▼ (распределение по очередям)                        │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │            Message Router / Dispatcher                      │  │
│  │  - Анализирует message.id, message.method                 │  │
│  │  - Определяет маршрут: какую очередь использовать        │  │
│  │  - Кэширует обработчики callbacks                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│         │                      │                      │            │
│         ▼                      ▼                      ▼            │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐      │
│  │ RPC Responses │   │ Notifications │   │ Permission Reqs   │      │
│  │ (by id)      │   │ (by method)    │   │ (by method)       │      │
│  │              │   │                │   │                   │      │
│  │ Queue[id: 1] │   │ Queue: updates │   │ Queue: perms      │      │
│  │ Queue[id: 2] │   │ Queue: cancels │   │                   │      │
│  │ ...          │   │                │   │                   │      │
│  └──────────────┘   └──────────────┘   └──────────────────┘      │
│         │                      │                      │            │
│         └──────────┬───────────┴──────────┬───────────┘            │
│                    │                      │                        │
│         ┌──────────▼──┐        ┌──────────▼──────────┐           │
│         │ receive()   │        │ receive_async()     │           │
│         │ (blocking)  │        │ (non-blocking)      │           │
│         └─────────────┘        └─────────────────────┘           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
        │                                          │
        ▼                                          ▼
┌──────────────────────────────────┐    ┌──────────────────────────┐
│  request_with_callbacks()        │    │  request()               │
│  - send(request)                 │    │  - send(request)         │
│  - receive()  ◄── из очереди по id  │  - receive()  ◄── из очереди
│  - обработка updates ◄──────────────▼──────────────────────────┐  │
│    (из очереди notifications)  │    │                      │  │
└──────────────────────────────────┘    └──────────────────────────┘
```

### 2. Компоненты

#### 2.1 MessageRouter (Маршрутизатор Сообщений)

**Класс: `MessageRouter`**

```python
class MessageRouter:
    """Анализирует сообщение и определяет его маршрут."""
    
    def route(message: dict) -> RoutingKey:
        """
        Определяет маршрут сообщения на основе:
        1. message.id (если есть) → RPC Response Queue[id]
        2. message.method (если нет id):
           - "session/update" → Notifications Queue
           - "session/request_permission" → Permission Queue
           - "session/cancel" → Cancellation Queue (особый случай)
           - другое → Unknown Queue (ошибка логирования)
        """
    
    def is_response(message: dict) -> bool:
        """Проверяет, это ответ на запрос (есть id)."""
    
    def is_notification(message: dict) -> bool:
        """Проверяет, это уведомление (нет id, есть method)."""
    
    def is_permission_request(message: dict) -> bool:
        """Проверяет, это запрос разрешения."""
```

**Маршруты:**

| Сообщение | id есть? | method | Маршрут | Описание |
|-----------|---------|--------|---------|----------|
| JSON-RPC ответ | Да | - | `response_queue[id]` | Ответ на конкретный request |
| session/update | Нет | session/update | `notification_queue` | Асинхронное уведомление о статусе |
| session/request_permission | Нет | session/request_permission | `permission_queue` | Запрос разрешения (требует ответа) |
| session/cancel | Нет | session/cancel | `notification_queue` | Отмена запроса |

#### 2.2 Message Queues (Очереди Сообщений)

**Структура хранения:**

```python
class RoutingQueues:
    """Хранилище всех очередей маршрутизации."""
    
    # Очередь для RPC ответов: {id → asyncio.Queue}
    response_queues: dict[int, asyncio.Queue[dict]]
    
    # Общая очередь для уведомлений
    notification_queue: asyncio.Queue[dict]
    
    # Общая очередь для запросов разрешения
    permission_queue: asyncio.Queue[dict]
    
    async def get_or_create_response_queue(self, request_id: int) -> asyncio.Queue:
        """Получает или создает очередь для конкретного request_id."""
    
    async def put_response(self, request_id: int, message: dict) -> None:
        """Кладет ответ в очередь по id."""
    
    async def put_notification(self, message: dict) -> None:
        """Кладет уведомление в общую очередь."""
    
    async def put_permission_request(self, message: dict) -> None:
        """Кладет запрос разрешения в общую очередь."""
    
    async def cleanup_response_queue(self, request_id: int) -> None:
        """Очищает очередь после использования."""
```

#### 2.3 Background Receive Loop (Фоновый цикл приёма)

**Класс: `BackgroundReceiveLoop`**

```python
class BackgroundReceiveLoop:
    """Фоновая задача для единственного вызова receive()."""
    
    def __init__(self, transport, router, queues, logger):
        self._transport = transport
        self._router = router
        self._queues = queues
        self._logger = logger
        self._task: asyncio.Task | None = None
        self._should_stop = False
    
    async def start(self) -> None:
        """Запускает фоновый loop приёма сообщений."""
        self._should_stop = False
        self._task = asyncio.create_task(self._receive_loop())
        self._logger.info("background_receive_loop_started")
    
    async def stop(self) -> None:
        """Останавливает фоновый loop и дожидается его завершения."""
        self._should_stop = True
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
        self._logger.info("background_receive_loop_stopped")
    
    async def _receive_loop(self) -> None:
        """Основной цикл приёма сообщений.
        
        КРИТИЧНО: Это единственное место, где вызывается receive()
        """
        while not self._should_stop:
            try:
                # Получаем сообщение из WebSocket
                message = await self._transport.receive()
                
                # Маршрутизируем сообщение в нужную очередь
                routing_key = self._router.route(message)
                
                if routing_key.queue_type == "response":
                    await self._queues.put_response(routing_key.request_id, message)
                elif routing_key.queue_type == "notification":
                    await self._queues.put_notification(message)
                elif routing_key.queue_type == "permission":
                    await self._queues.put_permission_request(message)
                else:
                    self._logger.warning(f"unknown_message_type: {message}")
                    
            except asyncio.CancelledError:
                self._logger.info("background_loop_cancelled")
                break
            except Exception as e:
                self._logger.error(f"receive_loop_error: {e}")
                # Можно добавить reconnect логику здесь
                break
```

#### 2.4 Modified receive() - Получение из Очереди

**Изменения в `ACPTransportService.receive()`:**

```python
async def receive(self) -> dict[str, Any]:
    """Получает сообщение из очереди RPC ответов для текущего request.
    
    ВАЖНО: Не вызывает receive() на WebSocket напрямую!
    Сообщения доставляются background loop и распределяются по очередям.
    """
    # Сохраняем id текущего request для маршрутизации
    if not hasattr(self, '_current_request_id'):
        raise RuntimeError("No request_id set for receive()")
    
    request_id = self._current_request_id
    queue = await self._queues.get_or_create_response_queue(request_id)
    
    try:
        # Ждем сообщение с таймаутом (для graceful shutdown)
        message = await asyncio.wait_for(queue.get(), timeout=300)
        return message
    finally:
        # Очищаем очередь после использования
        await self._queues.cleanup_response_queue(request_id)
```

#### 2.5 receive_async() - Для Асинхронных Уведомлений

**Новый метод в `ACPTransportService`:**

```python
async def receive_async(self) -> dict[str, Any]:
    """Получает асинхронное уведомление (session/update, permission request).
    
    Это НЕ блокирует request_with_callbacks().
    Может быть использовано отдельными слушателями для уведомлений.
    """
    message = await self._queues.notification_queue.get()
    return message

async def receive_permission_request(self) -> dict[str, Any]:
    """Получает запрос разрешения для обработки."""
    message = await self._queues.permission_queue.get()
    return message
```

#### 2.6 Modified request_with_callbacks() - Использование Очередей

**Изменения в `request_with_callbacks()`:**

```python
async def request_with_callbacks(
    self,
    method: str,
    params: dict[str, Any] | None = None,
    on_update: Callable | None = None,
    on_permission: Callable | None = None,
    ...
) -> dict[str, Any]:
    """Выполняет request, обрабатывая callbacks из очередей.
    
    Ключевое изменение: использует очереди вместо блокирующего receive()
    """
    
    # Убеждаемся, что background loop запущен
    await self._ensure_background_loop_started()
    
    if not self.is_connected():
        # ... reconnect логика ...
    
    # Создаем JSON-RPC запрос
    request = ACPMessage.request(method=method, params=params)
    request_data = request.to_dict()
    
    # Отправляем запрос
    await self.send(request_data)
    
    # Создаем очередь для этого request_id
    response_queue = await self._queues.get_or_create_response_queue(request.id)
    
    # Обрабатываем ответы и уведомления
    while True:
        try:
            # Используем asyncio.wait для мониторинга нескольких очередей одновременно
            response_queue_task = asyncio.create_task(response_queue.get())
            notification_task = asyncio.create_task(self._queues.notification_queue.get())
            permission_task = asyncio.create_task(self._queues.permission_queue.get())
            
            # Ждем первого результата
            done, pending = await asyncio.wait(
                [response_queue_task, notification_task, permission_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Обработка в зависимости от того, какая очередь выдала сообщение
            if response_queue_task in done:
                response_data = response_queue_task.result()
                # Это ответ на наш запрос
                return response_data
            
            elif notification_task in done:
                message = notification_task.result()
                if message.get("method") == "session/update" and on_update:
                    on_update(message)
                # Возвращаем сообщение в очередь для других слушателей
                notification_queue.put_nowait(message)
            
            elif permission_task in done:
                message = permission_task.result()
                if on_permission:
                    result = on_permission(message)
                    # Отправляем ответ разрешения
                    await self.send(ACPMessage.response(message.id, result).to_dict())
                # Возвращаем сообщение в очередь для других слушателей
                permission_queue.put_nowait(message)
        
        finally:
            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
```

**ИЛИ (более простой вариант) — использовать одну основную очередь:**

```python
async def request_with_callbacks(
    self,
    method: str,
    params: dict[str, Any] | None = None,
    on_update: Callable | None = None,
    on_permission: Callable | None = None,
    ...
) -> dict[str, Any]:
    """Выполняет request с обработкой callbacks из очередей."""
    
    await self._ensure_background_loop_started()
    
    if not self.is_connected():
        # ... reconnect логика ...
    
    request = ACPMessage.request(method=method, params=params)
    await self.send(request.to_dict())
    
    # Создаем очередь для этого request_id
    response_queue = await self._queues.get_or_create_response_queue(request.id)
    
    while True:
        # Получаем ответ для этого запроса (из его личной очереди)
        response_data = await asyncio.wait_for(response_queue.get(), timeout=300)
        response = ACPMessage.from_dict(response_data)
        
        # Проверяем, это ответ на наш запрос или что-то еще?
        if response.id == request.id:
            # Это финальный ответ
            return response_data
        else:
            # Это промежуточное уведомление (обработанное background loop, но положенное в очередь)
            # Это не должно происходить! Только response_queue[id] содержит для этого id
            pass
```

---

### 3. Lifecycle Management

#### 3.1 Инициализация при Подключении

```python
async def connect(self) -> None:
    """Устанавливает соединение и запускает background receive loop."""
    
    if self.is_connected():
        return
    
    try:
        # Создаем транспорт
        if self._transport is None:
            self._transport = WebSocketTransport(self.host, self.port)
        
        # Открываем WebSocket
        await self._transport.__aenter__()
        
        # Инициализируем routing infrastructure
        self._queues = RoutingQueues()
        self._router = MessageRouter()
        self._background_loop = BackgroundReceiveLoop(
            self._transport,
            self._router,
            self._queues,
            self._logger
        )
        
        # Запускаем background loop
        await self._background_loop.start()
        
        self._logger.info("connected_and_background_loop_started")
        
    except Exception as e:
        self._transport = None
        raise RuntimeError(f"Connection failed: {e}") from e
```

#### 3.2 Очистка при Отключении

```python
async def disconnect(self) -> None:
    """Останавливает background loop и закрывает соединение."""
    
    if not self.is_connected():
        return
    
    try:
        # Сначала останавливаем background loop
        if self._background_loop:
            await self._background_loop.stop()
        
        # Закрываем транспорт
        if self._transport is not None:
            await self._transport.__aexit__(None, None, None)
        
        self._logger.info("disconnected")
        
    except Exception as e:
        self._logger.warning(f"disconnect_error: {e}")
    
    finally:
        self._transport = None
        self._background_loop = None
        self._queues = None
        self._router = None
```

#### 3.3 Graceful Shutdown

```python
async def shutdown(self) -> None:
    """Корректное завершение работы."""
    
    try:
        # Даем время на завершение pending операций (timeout)
        await asyncio.wait_for(self.disconnect(), timeout=10.0)
    except asyncio.TimeoutError:
        self._logger.error("shutdown_timeout")
        # Force cleanup
        self._transport = None
        self._background_loop = None
```

---

### 4. Обработка Errors и Edge Cases

#### 4.1 WebSocket Disconnection Handling

```python
async def _receive_loop(self) -> None:
    """Background loop с обработкой разрывов соединения."""
    
    while not self._should_stop:
        try:
            message = await self._transport.receive()
            # ... маршрутизация ...
        
        except ConnectionError as e:
            self._logger.warning(f"connection_lost: {e}")
            # Уведомляем все pending requests об ошибке
            await self._queues.broadcast_connection_error(e)
            break
        
        except Exception as e:
            self._logger.error(f"receive_error: {e}")
            break
```

#### 4.2 Request Timeout

```python
async def receive(self) -> dict[str, Any]:
    """Получение с таймаутом."""
    
    request_id = self._current_request_id
    queue = await self._queues.get_or_create_response_queue(request_id)
    
    try:
        # Таймаут 300 сек (5 минут) — достаточно для долгоживущих операций
        message = await asyncio.wait_for(queue.get(), timeout=300)
        return message
    except asyncio.TimeoutError:
        self._logger.error(f"request_timeout: {request_id}")
        await self._queues.cleanup_response_queue(request_id)
        raise RuntimeError(f"Request {request_id} timed out") from None
```

#### 4.3 Duplicate Request IDs

```python
async def request_with_callbacks(self, ...) -> dict[str, Any]:
    """Защита от повторного использования request_id."""
    
    request = ACPMessage.request(method=method, params=params)
    
    # Проверяем, нет ли уже обработки для этого id
    if self._queues.response_queue_exists(request.id):
        raise RuntimeError(f"Request {request.id} already in progress")
    
    # ... дальше нормально ...
```

---

### 5. Integration Points

#### 5.1 Текущий Код, Требующий Изменений

| Файл | Компонент | Изменение |
|------|-----------|-----------|
| `acp_transport_service.py` | `ACPTransportService.__init__()` | Инициализировать `_queues`, `_router`, `_background_loop` |
| `acp_transport_service.py` | `ACPTransportService.connect()` | Запустить `background_loop.start()` |
| `acp_transport_service.py` | `ACPTransportService.disconnect()` | Остановить `background_loop.stop()` |
| `acp_transport_service.py` | `ACPTransportService.receive()` | Получать из очереди вместо `transport.receive()` |
| `acp_transport_service.py` | `ACPTransportService.request_with_callbacks()` | Использовать очереди вместо блокирующего receive() |
| `acp_transport_service.py` | (новый) | `_ensure_background_loop_started()` — проверка что background loop работает |

#### 5.2 Новые Компоненты для Создания

| Файл | Класс | Назначение |
|------|-------|-----------|
| `message_router.py` | `MessageRouter` | Анализ и маршрутизация сообщений |
| `routing_queues.py` | `RoutingQueues` | Управление очередями |
| `background_receive_loop.py` | `BackgroundReceiveLoop` | Фоновый loop для receive() |

#### 5.3 Текущие Методы, Не Требующие Изменений

- `send()` — остается как есть
- `listen()` — может остаться для генерации всех сообщений
- `is_connected()` — остается как есть
- Все остальные Use Cases — работают без изменений (через `request_with_callbacks()`)

---

## 6. Альтернативы и Выбор

### 6.1 Альтернатива 1: Мьютекс на receive() (Текущее решение)

```python
class ACPTransportService:
    def __init__(self):
        self._receive_lock = asyncio.Lock()
    
    async def receive(self):
        async with self._receive_lock:
            return await self._transport.receive()
```

**Плюсы:**
- Минимальные изменения кода
- Просто работает

**Минусы:**
- Блокирует все вызывающие — нет истинной конкурентности
- Может привести к deadlock в сложных сценариях
- Не обрабатывает асинхронные уведомления хорошо

### 6.2 Альтернатива 2: Message Routing System (РЕКОМЕНДУЕМОЕ)

```python
# Background loop обрабатывает receive()
# Очереди распределяют сообщения
# Все вызывающие получают из очередей без блокировок
```

**Плюсы:**
- Истинная конкурентность — нет блокировок
- Хорошая архитектура для масштабирования
- Поддержка множественных сессий и запросов
- Асинхронные уведомления обрабатываются правильно
- Graceful shutdown и error handling

**Минусы:**
- Больше кода
- Требует нескольких новых классов

**Вывод:** Альтернатива 2 лучше для production, но требует больше работы.

---

## 7. Сложность Реализации

### 7.1 Компоненты и их Сложность

| Компонент | Строк кода | Сложность | Риск |
|-----------|-----------|----------|------|
| `MessageRouter` | 50-70 | Низкая | Низкий |
| `RoutingQueues` | 100-150 | Средняя | Средний |
| `BackgroundReceiveLoop` | 80-120 | Средняя | Средний |
| Изменения в `ACPTransportService` | 150-200 | Средняя | Средний |
| **Итого** | **380-540** | **Средняя** | **Средний** |

### 7.2 Критические Точки

1. **Синхронизация очередей** — asyncio.Queue уже thread-safe
2. **Graceful shutdown** — нужен правильный порядок остановки
3. **Error propagation** — ошибки в background loop должны видны вызывающим
4. **Memory leaks** — очищать очереди после использования

---

## 8. Тестирование

### 8.1 Новые Unit Тесты

```python
# test_message_router.py
- test_route_response_message
- test_route_notification_message
- test_route_permission_message
- test_unknown_message_routing

# test_routing_queues.py
- test_put_and_get_response
- test_put_and_get_notification
- test_queue_cleanup
- test_multiple_concurrent_requests

# test_background_receive_loop.py
- test_loop_starts_and_stops
- test_messages_dispatched_correctly
- test_loop_handles_receive_error
- test_graceful_shutdown

# test_acp_transport_service_integration.py
- test_concurrent_receive_calls_no_error
- test_multiple_requests_concurrent
- test_background_loop_lifecycle
- test_notification_handling_with_requests
```

### 8.2 Существующие Тесты (Совместимость)

- `test_concurrent_receive_calls.py` — должны проходить без изменений
- Все остальные тесты `ACPTransportService` — должны проходить
- Тесты Use Cases — должны проходить

---

## 9. План Реализации

### Фаза 1: Infrastructure (Основные компоненты)
- [ ] Создать `message_router.py` с `MessageRouter`
- [ ] Создать `routing_queues.py` с `RoutingQueues`
- [ ] Создать `background_receive_loop.py` с `BackgroundReceiveLoop`
- [ ] Unit тесты для каждого компонента

### Фаза 2: Integration (Интеграция в основной сервис)
- [ ] Изменить `ACPTransportService.__init__()`
- [ ] Изменить `ACPTransportService.connect()`
- [ ] Изменить `ACPTransportService.disconnect()`
- [ ] Переписать `ACPTransportService.receive()`
- [ ] Обновить `ACPTransportService.request_with_callbacks()`
- [ ] Интеграционные тесты

### Фаза 3: Testing & Polish
- [ ] Запустить все существующие тесты
- [ ] Добавить edge case тесты
- [ ] Документировать изменения
- [ ] Performance testing

---

## 10. Минимальный Путь (Quick Fix vs Полное Решение)

### Quick Fix (1-2 часа)
```python
# Просто добавить asyncio.Lock в receive()
# + несколько guard checks
```

### Полное Решение (4-6 часов)
```python
# Реализовать всю Message Routing архитектуру
# с правильным lifecycle management
```

**Рекомендация:** Начать с Quick Fix для прохождения тестов, затем планомерно переходить на Полное Решение для лучшей архитектуры.

---

## Выводы

1. **Проблема:** RuntimeError: Concurrent call to receive() — это следствие неправильной архитектуры, где `request_with_callbacks()` блокирует одно WebSocket соединение.

2. **Решение:** Message Routing System с Background Receive Loop разделяет заботы:
   - Background loop — единственный источник receive()
   - Очереди — распределение по запросам и уведомлениям
   - Вызывающие — получают из очередей без блокировок

3. **Преимущества:**
   - Истинная конкурентность на одном WebSocket
   - Чистая архитектура
   - Легко масштабировать на множественные сессии
   - Правильная обработка асинхронных уведомлений

4. **Сложность:** Средняя — требует 3-4 новых класса и изменения основного сервиса.

5. **Альтернативы:** Мьютекс — проще, но менее красиво; Message Routing — сложнее, но лучше.
