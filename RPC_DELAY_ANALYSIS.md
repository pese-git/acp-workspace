# Детальный анализ проблемы с задержкой RPC ответов (32 секунды)

## Контекст проблемы

**Симптомы:**
- Сервер отправляет RPC запрос `fs/read_text_file` в **12:06:46.878**
- Клиент успешно читает файл и отправляет ответ (34KB) в **12:06:46.879**
- Сервер получает **timeout через 30 секунд** (12:07:16.879)
- Ответ от клиента приходит на сервер только в **12:07:18.685** (~**32 секунды задержки**)

---

## 🔴 НАЙДЕННАЯ ПРОБЛЕМА: Deadlock в обработке WebSocket

### Архитектурный deadlock

**На сервере (acp-server/src/acp_server/http_server.py):**

```python
# Строка 281: основной цикл обработки WebSocket
async for message in ws:
    # Строка 287: парсинг сообщения
    acp_request = ACPMessage.from_json(message.data)
    
    # Строка 335: СИНХРОННАЯ обработка в основном цикле
    outcome = await protocol.handle(acp_request)
```

**На сервере (acp-server/src/acp_server/client_rpc/service.py):**

```python
# Строка 145: БЛОКИРУЮЩЕЕ ОЖИДАНИЕ ответа от клиента
result = await asyncio.wait_for(future, timeout=self._timeout)  # 30 сек
```

### Сценарий deadlock-а:

```
ВРЕМЕННАЯ ШКАЛА:

T0 (12:06:46.878)
├─ Клиент отправляет session/prompt на сервер
└─ Сервер: async for message in ws получает это сообщение
   └─ Сервер: await protocol.handle(acp_request) ←─ ОСНОВНОЙ ЦИКЛ НАЧИНАЕТ ОБРАБОТКУ
      └─ prompt.session_prompt() вызывает агента/tool executor
         └─ client_rpc_service.read_text_file() ОТПРАВЛЯЕТ RPC НА КЛИЕНТ
            └─ await asyncio.wait_for(future, timeout=30) ← ЖДЕТ ОТВЕТА

T1 (12:06:46.879)
├─ Клиент УСПЕШНО ЧИТАЕТ ФАЙЛ (34KB)
├─ Клиент отправляет ответ на RPC запрос
└─ ОТВ ЕТ ПРИХОДИТ НА СЕРВЕР

T2 (ВСЕ ЕЩЕ 12:06:46.879)
└─ ❌ ПРОБЛЕМА: Основной цикл WebSocket ВСЕ ЕЩЕ ЗАНЯТ в await asyncio.wait_for()
   └─ async for message in ws НЕ МОЖЕТ ОБРАБОТАТЬ НОВЫЕ СООБЩЕНИЯ
   └─ Ответ от клиента ОСТАЕТСЯ В БУФЕРЕ СОКЕТА

T3 (12:07:16.879 - через 30 сек)
└─ asyncio.wait_for() выбрасывает TimeoutError
└─ Основной цикл НАКОНЕЦ может обработать следующий цикл

T4 (12:07:16.879 + еще несколько сек)
├─ Основной цикл заканчивает обработку message.data
└─ async for message in ws может получить ДРУГОЕ сообщение

T5 (12:07:18.685)
└─ Ответ на RPC НАКОНЕЦ обрабатывается в handle_client_response()
   (но к этому моменту уже истек timeout на сервере)
```

---

## 📋 Детальный анализ каждого компонента

### 1. **Server-side: ClientRPCService (acp-server/src/acp_server/client_rpc/service.py)**

**Строки 59-77:**
```python
def __init__(
    self,
    send_request_callback: Callable,
    client_capabilities: dict,
    timeout: float = 30.0,  # ←─ ТАЙМАУТ 30 СЕКУНД
) -> None:
    self._send_request = send_request_callback
    self._capabilities = client_capabilities
    self._timeout = timeout
    self._pending_requests: dict[str, asyncio.Future] = {}
```

**Строки 103-155 (основной метод `_call_method`):**
```python
async def _call_method(
    self,
    method: str,
    params: dict,
    response_model: type[BaseModel],
) -> Any:
    request_id = str(uuid.uuid4())
    future: asyncio.Future = asyncio.Future()
    self._pending_requests[request_id] = future

    try:
        # Отправить JSON-RPC request
        await self._send_request({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        })

        logger.debug(
            "Отправлен RPC запрос на клиент",
            extra={"method": method, "request_id": request_id},
        )

        # ❌ ПРОБЛЕМА: БЛОКИРУЮЩЕЕ ОЖИДАНИЕ (строка 145)
        result = await asyncio.wait_for(future, timeout=self._timeout)
        
        # Парсить ответ
        return response_model.model_validate(result)

    except TimeoutError as err:
        # ❌ Выбрасываем TimeoutError через 30 сек, но ответ может быть в пути
        raise ClientRPCTimeoutError(
            f"Timeout при вызове {method} (>{self._timeout}s)"
        ) from err
    finally:
        self._pending_requests.pop(request_id, None)
```

**Проблема:** Метод используется как `await client_rpc_service.read_text_file()` ВНУТРИ основного цикла WebSocket, блокируя его на 30 секунд.

---

### 2. **Server-side: HTTP Server WebSocket loop (acp-server/src/acp_server/http_server.py)**

**Строки 281-335:**
```python
try:
    async for message in ws:  # ← ОСНОВНОЙ ЦИКЛ ОБРАБОТКИ
        if message.type == WSMsgType.TEXT:
            method_name: str | None = None
            session_id: str | None = None
            request_id: str | None = None
            try:
                acp_request = ACPMessage.from_json(message.data)
                method_name = acp_request.method
                request_id = str(acp_request.id) if acp_request.id is not None else None

                if method_name is None:
                    outcome = protocol.handle_client_response(acp_request)
                else:
                    # ... другие методы ...
                    if isinstance(acp_request.params, dict):
                        raw_session_id = acp_request.params.get("sessionId")
                        if isinstance(raw_session_id, str):
                            session_id = raw_session_id
                    
                    # ❌ СИНХРОННАЯ обработка session/prompt БЕЗ spawn'а
                    outcome = await protocol.handle(acp_request)
```

**Критический момент (строка 335):**
- `await protocol.handle(acp_request)` вызывает `session_prompt()`
- `session_prompt()` вызывает `client_rpc_service.read_text_file()`
- `read_text_file()` ждет ответа **30 секунд** в `await asyncio.wait_for(future, timeout=30)`
- **ВСЕ ЭТО ПРОИСХОДИТ ВНУТРИ основного цикла WebSocket!**
- `async for message in ws` **НЕ МОЖЕТ ПОЛУЧИТЬ ОТВЕТ** до тех пор, пока обработка не завершится

**Результат:** Классический deadlock - основной цикл заблокирован, ответ не может быть обработан.

---

### 3. **Client-side: Background Receive Loop (acp-client/src/acp_client/infrastructure/services/background_receive_loop.py)**

**Строки 132-153:**
```python
async def _receive_loop(self) -> None:
    """Основной цикл приёма сообщений."""
    self._logger.info("receive_loop_starting")

    try:
        while not self._should_stop:
            try:
                # Получаем сообщение из WebSocket
                # ✓ ЗДЕСЬ ВСЕ ПРАВИЛЬНО - единственный вызов receive()
                json_message = await self._transport.receive_text()
                message = json.loads(json_message)
                self._messages_received += 1

                # Определяем маршрут сообщения
                routing_key = self._router.route(message)
```

**Строки 167-186:**
```python
                # Распределяем по очередям в зависимости от маршрута
                if routing_key.queue_type == "response":
                    # RPC ответ на конкретный запрос
                    request_id = routing_key.request_id
                    if request_id is not None:
                        await self._queues.put_response(request_id, message)
                        self._messages_routed += 1
```

**✓ Проблемы НЕ здесь** - это правильно архитектурировано.

---

### 4. **Client-side: ACPTransportService (acp-client/src/acp_client/infrastructure/services/acp_transport_service.py)**

**Строки 466-523:**
```python
async with self._callbacks_request_lock:  # ← ГЛОБАЛЬНАЯ БЛОКИРОВКА
    # Получаем или создаем очередь для этого request_id
    response_queue = await self._queues.get_or_create_response_queue(request_id)

    # Отправляем запрос
    await self.send(request_data)

    # Получаем ответы, обрабатывая промежуточные события.
    while True:
        # Создаем задачи для ожидания из разных очередей.
        response_task = asyncio.create_task(
            asyncio.wait_for(response_queue.get(), timeout=300.0)
        )
        
        if should_listen_notifications:
            # ❌ ПРОБЛЕМА: timeout = 0.1 сек (100ms)
            notification_task = asyncio.create_task(
                asyncio.wait_for(self._queues.notification_queue.get(), timeout=0.1)
            )
            permission_task = asyncio.create_task(
                asyncio.wait_for(self._queues.permission_queue.get(), timeout=0.1)
            )

        # Ждем первого результата.
        done, pending = await asyncio.wait(
            [response_task]
            if notification_task is None or permission_task is None
            else [response_task, notification_task, permission_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Отменяем оставшиеся задачи.
        for task in pending:
            task.cancel()
```

**Проблема:** Хотя это архитектурировано правильно для обработки RPC запросов от сервера, глобальная блокировка может вызвать задержки, если несколько конкурентных запросов отправляются одновременно.

**Дополнительная проблема (строка 511):** Timeout в 100ms для notification может вызвать много переквантования и отмен задач.

---

## 🎯 Причина 32-секундной задержки

### Корневая причина: **Архитектурный deadlock в WebSocket обработке**

1. **T0:** Клиент отправляет `session/prompt`, сервер получает в основной цикл WebSocket
2. **T0:** `async for message in ws` начинает обработку через `await protocol.handle()`
3. **T0.1:** `session_prompt()` → `client_rpc_service.read_text_file()`
4. **T0.2:** `read_text_file()` отправляет RPC на клиент и вызывает `await asyncio.wait_for(future, timeout=30)`
5. **T0.3:** **DEADLOCK**: основной цикл WebSocket ЗАБЛОКИРОВАН в `await asyncio.wait_for()`
6. **T0.4:** Клиент ОТПРАВЛЯЕТ ОТВЕТ (34KB) в **12:06:46.879**
7. **T30:** Таймаут истекает (**12:07:16.879**), основной цикл наконец может продолжить
8. **T30+2:** Ответ от клиента НАКОНЕЦ обрабатывается в `handle_client_response()` (**12:07:18.685**)

**Математика:** 30 сек (таймаут) + ~2 сек (задержка до полной обработки) = **~32 секунды**

---

## 📊 Временная диаграмма

```
Сервер                          Клиент                  WebSocket буфер
─────────────────────────────────────────────────────────────────────

12:06:46.878
│  
├─ session/prompt ─────────────────────────────────────→
                                                          [сообщение в буфере]
│
├─ async for message ─ получает session/prompt
│  │
│  └─ await protocol.handle()
│     │
│     └─ session_prompt()
│        │
│        └─ client_rpc_service.read_text_file()
│           │
│           └─ ОТПРАВЛЯЕТ RPC ────────────────────────→
│              │
│              └─ await asyncio.wait_for(future, 30s)  │
│                 │                                      │
│                 │ (DEADLOCK НАЧИНАЕТСЯ)               │
│                 │                                      │

12:06:46.879
                                                        ← fs/read_text_file RPC
                                                          [в буфере]
                                   │
                                   └─ Читает файл (ms)
                                   │
                                   └─ ответ (34KB) ────→ [в буфере]
                                                          
│ DEADLOCK ПРОДОЛЖАЕТСЯ (основной цикл заблокирован)   [ответ ждет обработки]
│ async for message in ws НЕ МОЖЕТ получить новые     
│ сообщения из буфера

12:07:16.879 (через 30 сек)
│
└─ TimeoutError в asyncio.wait_for()
   │
   └─ except TimeoutError выбросит ClientRPCTimeoutError
   │
   └─ finally: очистит pending_requests[request_id]
   │
   └─ ОСВОБОЖДАЕТ основной цикл WebSocket

12:07:16.879 + ~2 сек = 12:07:18.685
│
├─ async for message in ws может ТЕПЕРЬ получить следующее сообщение
│  │
│  └─ Ответ от клиента НАКОНЕЦ обрабатывается
│     │
│     └─ handle_client_response()
│
└─ ❌ Но уже слишком поздно - сервер уже выбросил TimeoutError
```

---

## 🔧 Решение

### Архитектурное изменение: Spawn long-running prompts

Вместо синхронной обработки `session/prompt` в основном цикле WebSocket, нужно **отделить обработку** в отдельный `asyncio.Task`:

**Текущий (НЕПРАВИЛЬНЫЙ) код на http_server.py:**
```python
async for message in ws:
    # ОСНОВНОЙ ЦИКЛ ЗАБЛОКИРОВАН на обработку одного большого запроса
    outcome = await protocol.handle(acp_request)  # Может ждать 30+ сек!
```

**ПРАВИЛЬНЫЙ код:**
```python
async for message in ws:
    if method_name == "session/prompt" and session_id is not None:
        # ✓ Spawn отдельный task для обработки
        task = asyncio.create_task(
            protocol.handle_long_running(acp_request)
        )
        deferred_prompt_tasks[session_id] = task
        # Основной цикл продолжает работать!
    else:
        outcome = await protocol.handle(acp_request)  # Быстро
```

### Альтернативное решение: Асинхронный client_rpc_service с отменой

Или уменьшить таймаут и использовать cancellation token:

```python
# На сервере вместо 30 сек, использовать 5 сек с повторными попытками
timeout: float = 5.0  # Вместо 30.0

# С отдельным механизмом повторных попыток для долгих операций
```

---

## 📌 Выводы

| Компонент | Проблема | Статус |
|-----------|----------|--------|
| **ClientRPCService** | 30-секундный таймаут в блокирующем вызове | ✓ Корректно реализовано |
| **HTTP Server WebSocket** | Обработка `session/prompt` в основном цикле | ❌ **DEADLOCK** |
| **Background Receive Loop** | ✓ Правильно архитектурировано | ✓ OK |
| **ACPTransportService** | Глобальная блокировка для request_with_callbacks | ⚠️ OK, но неоптимально |

**Главная проблема:** Основной цикл WebSocket на сервере обрабатывает долгие RPC запросы синхронно, блокируя себя от получения ответов.
