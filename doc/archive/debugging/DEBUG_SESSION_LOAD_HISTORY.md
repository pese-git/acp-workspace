# Отладка проблемы с отображением истории при загрузке сессии

## Проблема

При загрузке сессии (`session/load`) сервер отправляет `session/update` уведомления с историей, но сообщения не отображаются в UI клиента.

## Анализ логов

Из логов `~/.acp-client/logs/acp-client.log` видно:

1. ✅ Сервер отправляет 6 `session/update` уведомлений при каждом `session/load`
2. ✅ Клиент получает уведомления: `route_notification_update method=session/update`
3. ✅ Уведомления попадают в очередь: `notification_queued method=session/update`
4. ✅ Есть один лог обработки: `handling_session_update`
5. ❌ НО нет логов обработки в ChatViewModel (должны быть логи добавления сообщений)

## Гипотезы о причинах проблемы

### Гипотеза 1: Race condition в обработке уведомлений

**Описание**: Уведомления приходят быстрее, чем `request_with_callbacks` начинает их обрабатывать.

**Механизм**:
1. Сервер отправляет 6 `session/update` уведомлений сразу после получения `session/load`
2. Background receive loop кладет их в `notification_queue`
3. `request_with_callbacks` начинает цикл ожидания с таймаутом 0.1 сек для notification_task
4. Если уведомления уже в очереди, они могут быть пропущены из-за короткого таймаута

**Код**: [`acp_transport_service.py:488-579`](acp-client/src/acp_client/infrastructure/services/acp_transport_service.py:488-579)

```python
# Цикл ожидания response с обработкой уведомлений
while True:
    response_task = asyncio.create_task(
        asyncio.wait_for(response_queue.get(), timeout=300.0)
    )
    notification_task = asyncio.create_task(
        asyncio.wait_for(self._queues.notification_queue.get(), timeout=0.1)  # ⚠️ Короткий таймаут!
    )
    
    done, pending = await asyncio.wait(
        [response_task, notification_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
```

**Проблема**: Если уведомления пришли до начала цикла, они остаются в очереди необработанными.

### Гипотеза 2: Callback не вызывается для всех уведомлений

**Описание**: `LoadSessionUseCase` собирает replay_updates через callback, но callback может не вызываться для всех уведомлений.

**Код**: [`use_cases.py:380-397`](acp-client/src/acp_client/application/use_cases.py:380-397)

```python
replay_updates: list[dict[str, Any]] = []

def handle_update(update_data: dict[str, Any]) -> None:
    """Собирает `session/update` во время `session/load` для UI-реплея."""
    replay_updates.append(update_data)

response_data = await self._transport.request_with_callbacks(
    method="session/load",
    params={
        "sessionId": request.session_id,
        "cwd": load_cwd,
        "mcpServers": load_mcp_servers,
    },
    on_update=handle_update,  # ⚠️ Callback для обработки уведомлений
)
```

**Проблема**: Если `request_with_callbacks` не обрабатывает все уведомления из очереди, `replay_updates` будет пустым.

### Гипотеза 3: Уведомления обрабатываются, но не применяются к UI

**Описание**: `restore_session_from_replay` вызывается, но не обновляет UI.

**Код**: [`app.py:340-341`](acp-client/src/acp_client/tui/app.py:340-341)

```python
replay_updates = loaded.get("replay_updates", [])
if isinstance(replay_updates, list):
    self._chat_vm.restore_session_from_replay(session_id, replay_updates)
```

**Проблема**: Если `replay_updates` пустой, UI не обновится.

## Добавленное логирование

Для диагностики проблемы добавлено детальное логирование в ключевых точках:

### 1. LoadSessionUseCase - callback обработки уведомлений

**Файл**: `acp-client/src/acp_client/application/use_cases.py`

```python
def handle_update(update_data: dict[str, Any]) -> None:
    """Собирает `session/update` во время `session/load` для UI-реплея."""
    
    self._logger.debug(
        "load_session_update_received",
        update_type=update_data.get("params", {}).get("update", {}).get("sessionUpdate"),
        total_updates=len(replay_updates) + 1,
    )
    replay_updates.append(update_data)
```

**Что проверяем**: Вызывается ли callback для каждого уведомления?

### 2. ACPTransportService - обработка уведомлений в request_with_callbacks

**Файл**: `acp-client/src/acp_client/infrastructure/services/acp_transport_service.py`

```python
if (
    notification.method == "session/update"
    and on_update is not None
):
    self._logger.debug(
        "handling_session_update",
        method=method,
        request_id=request.id,
        has_callback=on_update is not None,
    )
    on_update(notification_data)
elif notification.method == "session/update" and on_update is None:
    self._logger.warning(
        "session_update_received_but_no_callback",
        method=method,
        request_id=request.id,
    )
```

**Что проверяем**: Обрабатываются ли уведомления в цикле ожидания?

### 3. ChatViewModel - восстановление истории

**Файл**: `acp-client/src/acp_client/presentation/chat_view_model.py`

```python
def restore_session_from_replay(
    self,
    session_id: str,
    replay_updates: list[dict[str, Any]],
) -> None:
    self.logger.info(
        "restore_session_from_replay_started",
        session_id=session_id,
        replay_updates_count=len(replay_updates),
    )
    
    # ... обработка ...
    
    self.logger.info(
        "restore_session_from_replay_completed",
        session_id=session_id,
        rebuilt_messages_count=len(rebuilt_messages),
        is_active_session=self._active_session_id == session_id,
    )
```

**Что проверяем**: Сколько уведомлений получено и сколько сообщений восстановлено?

## Инструкции для тестирования

### 1. Запустить сервер

```bash
cd acp-server
uv run python -m acp_server.cli --host 127.0.0.1 --port 8765
```

### 2. Запустить клиент с логированием

```bash
cd acp-client
uv run python -m acp_client.tui --host 127.0.0.1 --port 8765
```

### 3. Создать сессию и отправить несколько сообщений

1. В TUI создать новую сессию
2. Отправить 2-3 сообщения
3. Дождаться ответов от агента
4. Закрыть клиент

### 4. Загрузить сессию и проверить логи

1. Запустить клиент снова
2. Выбрать существующую сессию из списка
3. Проверить логи в `~/.acp-client/logs/acp-client.log`

### 5. Анализ логов

Искать следующие записи в логах:

#### Ожидаемые логи при успешной загрузке:

```
# 1. Уведомления получены и маршрутизированы
route_notification_update method=session/update
notification_queued method=session/update

# 2. Уведомления обработаны в request_with_callbacks
handling_session_update method=session/load request_id=X has_callback=True

# 3. Callback вызван в LoadSessionUseCase
load_session_update_received update_type=user_message_chunk total_updates=1
load_session_update_received update_type=agent_message_chunk total_updates=2
...

# 4. История восстановлена в ChatViewModel
restore_session_from_replay_started session_id=X replay_updates_count=6
restore_session_from_replay_completed session_id=X rebuilt_messages_count=3 is_active_session=True
```

#### Признаки проблемы:

1. **Уведомления не обрабатываются**:
   ```
   notification_queued method=session/update
   # НО НЕТ: handling_session_update
   ```

2. **Callback не вызывается**:
   ```
   handling_session_update method=session/load
   # НО НЕТ: load_session_update_received
   ```

3. **Replay updates пустой**:
   ```
   restore_session_from_replay_started session_id=X replay_updates_count=0
   ```

## Возможные решения

### Решение 1: Увеличить таймаут для notification_task

**Проблема**: Короткий таймаут 0.1 сек может пропускать уведомления.

**Решение**: Увеличить таймаут или использовать другой подход к обработке уведомлений.

```python
notification_task = asyncio.create_task(
    asyncio.wait_for(self._queues.notification_queue.get(), timeout=1.0)  # Увеличить до 1 сек
)
```

### Решение 2: Обработать все уведомления из очереди перед возвратом response

**Проблема**: Уведомления могут остаться в очереди после получения финального response.

**Решение**: После получения response обработать все оставшиеся уведомления из очереди.

```python
# После получения финального response
while not self._queues.notification_queue.empty():
    try:
        notification_data = self._queues.notification_queue.get_nowait()
        notification = ACPMessage.from_dict(notification_data)
        if notification.method == "session/update" and on_update is not None:
            on_update(notification_data)
    except asyncio.QueueEmpty:
        break
```

### Решение 3: Использовать отдельную задачу для обработки уведомлений

**Проблема**: Текущий подход обрабатывает уведомления только в цикле ожидания response.

**Решение**: Создать отдельную фоновую задачу для обработки уведомлений.

```python
async def notification_handler():
    while not response_received:
        try:
            notification_data = await asyncio.wait_for(
                self._queues.notification_queue.get(),
                timeout=0.1
            )
            if on_update is not None:
                on_update(notification_data)
        except TimeoutError:
            continue

notification_task = asyncio.create_task(notification_handler())
```

## Следующие шаги

1. ✅ Добавить логирование в ключевых точках
2. ⏳ Запустить клиент с реальным сервером
3. ⏳ Проанализировать логи для подтверждения гипотезы
4. ⏳ Применить соответствующее решение
5. ⏳ Протестировать исправление
