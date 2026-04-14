# Этап 6: WebSocket Интеграция PromptOrchestrator — Гайд и Best Practices

**Статус:** 📖 Завершено  
**Дата:** 2026-04-12  

---

## 📋 Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Поток обработки prompt](#поток-обработки-prompt)
3. [Управление deferred_prompt_tasks](#управление-deferred_prompt_tasks)
4. [Edge cases и их обработка](#edge-cases-и-их-обработка)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## 🏛️ Обзор архитектуры

### Слои WebSocket интеграции

```
┌─────────────────────────────────────────┐
│  Клиент (WebSocket)                     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  ACPHttpServer.handle_ws_request()      │
│  - Управление подключением              │
│  - Routing на ACPProtocol               │
│  - Управление deferred_prompt_tasks     │
│  - Отправка notifications и responses   │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  ACPProtocol.handle()                   │
│  - Диспетчинг методов                   │
│  - Валидация состояния                  │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  session_prompt() handler               │
│  - Валидация параметров                 │
│  - Делегирование на orchestrator        │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  PromptOrchestrator.handle_prompt()     │
│  - Инициализация turn                   │
│  - Извлечение текста                    │
│  - Вызов LLM через agent_orchestrator   │
│  - Управление tool calls, permissions   │
│  - Финализация turn                     │
└─────────────────────────────────────────┘
```

### Отправка данных в WebSocket

```python
# Порядок отправки сообщений:
1. Notifications (session/update, session/request_permission)
   ↓
2. Response (с результатом или ошибкой)
   ↓
3. Followup responses (дополнительные ответы, если есть)
```

---

## 🔄 Поток обработки prompt

### Фаза 1: Инициализация

```python
# На входе: JSON-RPC request с sessionId и prompt
{
  "jsonrpc": "2.0",
  "id": "prompt_1",
  "method": "session/prompt",
  "params": {
    "sessionId": "sess_xyz",
    "prompt": [{"type": "text", "text": "..."}]
  }
}
```

### Фаза 2: Обработка

```
handle_ws_request():
  1. Парсить ACPMessage
  2. Проверить initialize флаг
  3. Вызвать protocol.handle(acp_request)
    └─→ session_prompt():
        ├─ Валидировать параметры
        ├─ Создать PromptOrchestrator
        └─ Вызвать orchestrator.handle_prompt()
          └─ Получить ProtocolOutcome с notifications
  4. Отправить notifications в порядке
  5. Отправить response
  6. Если нужен deferred turn, создать asyncio.Task
```

### Фаза 3: Отправка результата

```python
# ProtocolOutcome содержит:
ProtocolOutcome(
    notifications=[...],      # session/update, session/request_permission
    response=...,             # Основной ответ с ID
    followup_responses=[...]  # Дополнительные ответы
)

# Порядок отправки на WebSocket:
for notification in outcome.notifications:
    ws.send_str(notification.to_json())

if outcome.response:
    ws.send_str(outcome.response.to_json())

for followup in outcome.followup_responses:
    ws.send_str(followup.to_json())
```

---

## 🔐 Управление deferred_prompt_tasks

### Назначение

Механизм отложенного завершения turn для имитации асинхронной обработки:

```python
# Пример: prompt → task создается → 50ms задержка → завершение turn
deferred_prompt_tasks[session_id] = asyncio.create_task(
    _complete_deferred_prompt(...)
)
```

### Жизненный цикл задачи

```
1. СОЗДАНИЕ (session/prompt обработан без response)
   ├─ Создается asyncio.Task
   ├─ Task помещается в deferred_prompt_tasks[session_id]
   └─ Логируется создание

2. ОЖИДАНИЕ (50ms задержка)
   ├─ Task спит
   └─ Клиент может отправить session/cancel

3. ЗАВЕРШЕНИЕ или ОТМЕНА
   ├─ ЗАВЕРШЕНИЕ:
   │  ├─ complete_active_turn() вызывается
   │  ├─ Response отправляется в WebSocket
   │  └─ Task удаляется из словаря
   │
   └─ ОТМЕНА (session/cancel пришел):
      ├─ task.cancel() вызывается
      ├─ CancelledError перехватывается
      └─ Task удаляется из словаря

4. CLEANUP при разрыве соединения
   ├─ В finally блоке handle_ws_request()
   ├─ Все оставшиеся tasks отменяются
   └─ Словарь очищается
```

### Обработка ошибок в _complete_deferred_prompt()

```python
try:
    # Ожидание перед завершением
    await asyncio.sleep(0.05)
    
    # Попытка завершить turn
    response = protocol.complete_active_turn(...)
    
except TimeoutError:
    # Timeout при обработке - логируем и пропускаем отправку
    logger.warning("deferred prompt completion timeout")
    response = None
    
except Exception as exc:
    # Неожиданная ошибка - логируем, но не пробрасываем
    logger.error("deferred prompt completion error", exc_info=True)
    response = None
    
finally:
    # Гарантированная очистка
    deferred_prompt_tasks.pop(session_id, None)
```

---

## ⚠️ Edge cases и их обработка

### Edge Case 1: Клиент отправил cancel до turn_complete

**Сценарий:**
```
1. Client отправляет session/prompt
2. Server обрабатывает, создает deferred_prompt_task
3. Client отправляет session/cancel до завершения turn
4. Задача должна быть отменена gracefully
```

**Обработка:**
```python
if method_name == "session/cancel" and session_id is not None:
    task = deferred_prompt_tasks.pop(session_id, None)
    if task is not None:
        task.cancel()  # Отправляет CancelledError в задачу
```

**Логирование:**
```
[info] deferred prompt cancelled by client
       connection_id=conn_id session_id=sess_id
```

---

### Edge Case 2: Разрыв WebSocket во время deferred turn

**Сценарий:**
```
1. Deferred task выполняется
2. WebSocket разрывается (клиент отключился)
3. Task пытается отправить response в закрытое соединение
```

**Обработка:**
```python
if response is not None and not ws.closed:
    try:
        await ws.send_str(response.to_json())
    except Exception as exc:
        logger.error("deferred prompt send error", exc_info=True)
```

**Логирование:**
```
[debug] deferred prompt skipped (websocket closed)
[error] deferred prompt send error
        error=... exc_info=True
```

---

### Edge Case 3: Исключение в _complete_deferred_prompt()

**Сценарий:**
```
1. protocol.complete_active_turn() выбросит исключение
2. Task не должна привести к зависанию или утечке памяти
```

**Обработка:**
```python
try:
    response = protocol.complete_active_turn(...)
except Exception as exc:
    logger.error("deferred prompt completion error", 
                 error=str(exc), exc_info=True)
    response = None
finally:
    # Гарантированная очистка
    removed = deferred_prompt_tasks.pop(session_id, None)
```

---

### Edge Case 4: Быстрые prompts подряд для одной сессии

**Сценарий:**
```
1. Client отправляет prompt_1
2. Server создает deferred_task_1
3. Client отправляет prompt_2 ДО завершения prompt_1
4. Что произойдет?
```

**Текущее поведение:**
```python
# prompt_2 перезапишет deferred_prompt_tasks[session_id]
task = deferred_prompt_tasks.pop(session_id, None)  # Получит task_1
if task is not None:
    task.cancel()  # Отменит task_1

# Создает новую задачу task_2
deferred_prompt_tasks[session_id] = asyncio.create_task(...)
```

**Вывод:** Клиент должен дождаться turn_complete перед отправкой следующего prompt.

---

### Edge Case 5: Cleanup при разрыве соединения

**Сценарий:**
```
1. Connection закрывается (CLOSE, ERROR, или разрыв)
2. В handle_ws_request() может быть несколько deferred_tasks
```

**Обработка в finally:**
```python
finally:
    if deferred_prompt_tasks:
        conn_logger.info(
            "cleaning up deferred prompt tasks",
            pending_tasks_count=len(deferred_prompt_tasks),
        )
        for session_id_to_cancel, task_to_cancel in list(deferred_prompt_tasks.items()):
            if not task_to_cancel.done():
                task_to_cancel.cancel()
            deferred_prompt_tasks.pop(session_id_to_cancel, None)
```

**Логирование:**
```
[info] cleaning up deferred prompt tasks
       pending_tasks_count=3
[debug] deferred prompt task cancelled
        session_id=sess_1
[debug] deferred prompt task cancelled
        session_id=sess_2
[debug] deferred prompt task cancelled
        session_id=sess_3
[info] ws connection closed
       duration=1.234 pending_deferred_tasks=0
```

---

## ✅ Best Practices

### 1. Порядок отправки сообщений

**✅ ПРАВИЛЬНО:**
```python
# Отправить уведомления ДО response
for notification in outcome.notifications:
    await ws.send_str(notification.to_json())

# Затем отправить response
if outcome.response:
    await ws.send_str(outcome.response.to_json())
```

**❌ НЕПРАВИЛЬНО:**
```python
# Отправить response сразу
await ws.send_str(outcome.response.to_json())

# Потом уведомления (порядок нарушен!)
for notification in outcome.notifications:
    await ws.send_str(notification.to_json())
```

---

### 2. Обработка исключений в async функциях

**✅ ПРАВИЛЬНО:**
```python
try:
    await async_operation()
except TimeoutError:
    logger.warning("Operation timeout")
except Exception as exc:
    logger.error("Operation failed", exc_info=True)
finally:
    cleanup()  # Гарантированный cleanup
```

**❌ НЕПРАВИЛЬНО:**
```python
try:
    await async_operation()
finally:
    cleanup()  # Cleanup при исключении может не быть вызван
```

---

### 3. Проверка состояния WebSocket перед отправкой

**✅ ПРАВИЛЬНО:**
```python
if response is not None and not ws.closed:
    try:
        await ws.send_str(response.to_json())
    except Exception:
        logger.error("Send failed", exc_info=True)
```

**❌ НЕПРАВИЛЬНО:**
```python
# Не проверяем closed флаг
if response is not None:
    await ws.send_str(response.to_json())
```

---

### 4. Логирование для отладки

**✅ ПРАВИЛЬНО:**
```python
conn_logger = logger.bind(
    connection_id=connection_id,
    session_id=session_id
)

conn_logger.info("request received", method=method_name)
conn_logger.debug("deferred prompt created")
conn_logger.error("send error", exc_info=True)
```

**Результат в логах:**
```
[info] request received
       connection_id=a1b2c3d4 session_id=sess_xyz method=session/prompt
```

---

### 5. Таймауты для long-running операций

**✅ РЕКОМЕНДУЕТСЯ:**
```python
# Для deferred prompts: 30 секунд timeout
DEFERRED_PROMPT_TIMEOUT = 30.0

# Для WebSocket операций: 1-5 секунд
await asyncio.wait_for(ws.receive_json(), timeout=1.0)
```

---

## 🔧 Troubleshooting

### Проблема: Deferred prompts "зависают"

**Симптомы:**
```
- Клиент ждет response, но не получает
- В логах нет "deferred prompt completed"
- Connection остается открытой
```

**Вероятные причины:**
1. Exception в `protocol.complete_active_turn()`
2. WebSocket закрыт до отправки
3. Задача не была запланирована в `deferred_prompt_tasks`

**Решение:**
```python
# Проверить логи на уровне DEBUG
[debug] deferred prompt created
[debug] deferred prompt skipped (websocket closed)
[error] deferred prompt completion error
        error=... exc_info=True
```

---

### Проблема: Множественные сессии "смешивают" данные

**Симптомы:**
```
- Notifications от session A приходят как результат для session B
- sessionId в notifications не совпадает с sessionId prompt'а
```

**Проверка:**
```python
# Убедиться, что sessionId правильно передается
session_id = acp_request.params.get("sessionId")

# Убедиться, что все notifications содержат правильный sessionId
assert notification.params.get("sessionId") == session_id
```

---

### Проблема: Rapid prompts приводят к deadlock

**Симптомы:**
```
- Client отправляет 10+ prompts подряд
- Server перестает отвечать
- Connection висит
```

**Решение:**
1. Client должен дождаться `session/turn_complete` перед следующим prompt
2. Server должен обрабатывать prompts последовательно (текущее поведение)
3. Добавить мониторинг на количество pending deferred_tasks

---

### Проблема: Cleanup при разрыве соединения не работает

**Симптомы:**
```
- После разрыва соединения deferred_tasks остаются в памяти
- Утечка памяти при разрывах
```

**Решение:**
```python
finally:
    # Убедиться, что cleanup вызывается
    for session_id, task in list(deferred_prompt_tasks.items()):
        if not task.done():
            task.cancel()
        deferred_prompt_tasks.pop(session_id, None)
    
    # Проверить, что словарь пуст
    assert len(deferred_prompt_tasks) == 0
```

---

## 📊 Мониторинг и метрики

### Ключевые метрики для отслеживания

```python
# 1. Количество активных WebSocket подключений
ws_connections_active: int

# 2. Количество deferred prompts в момент времени
deferred_prompts_pending: int

# 3. Время обработки prompt
prompt_processing_time_ms: float

# 4. Процент успешных completions
completion_success_rate: float = (successful / total)

# 5. Процент отмен (session/cancel)
cancellation_rate: float = (cancelled / total)
```

### Пример логирования метрик

```python
duration = time.time() - start_time
conn_logger.info(
    "ws connection closed",
    duration=round(duration, 3),
    pending_deferred_tasks=len(deferred_prompt_tasks),
    prompts_processed=prompts_count,
)
```

---

## 🔗 Ссылки на документацию

- [`acp-server/src/acp_server/http_server.py`](acp-server/src/acp_server/http_server.py) - WebSocket handler
- [`acp-server/src/acp_server/protocol/core.py`](acp-server/src/acp_server/protocol/core.py) - ACPProtocol
- [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py) - session_prompt() handler
- [`acp-server/tests/test_http_server_stage6.py`](acp-server/tests/test_http_server_stage6.py) - Новые интеграционные тесты

---

## 📝 Заключение

WebSocket интеграция Этапа 6 обеспечивает:

✅ Надежную обработку deferred_prompt_tasks  
✅ Graceful обработку ошибок и разрывов соединений  
✅ Правильный порядок отправки notifications и responses  
✅ Полное покрытие edge cases  
✅ Детальное логирование для отладки  

Следуйте best practices при добавлении новых функций или изменении WebSocket обработки.
