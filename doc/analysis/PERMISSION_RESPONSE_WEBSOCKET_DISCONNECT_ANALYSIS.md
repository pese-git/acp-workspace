# Анализ разрыва WebSocket соединения после permission response

## Проблема

WebSocket соединение разрывается через 2.5 минуты после обработки permission response, хотя сервер корректно обрабатывает response и генерирует ProtocolOutcome с notifications и followup_responses.

## Временная шкала событий

```
13:55:30.433Z - session/prompt обработан, отправлен session/request_permission
13:55:33.279Z - permission response получен от клиента
13:55:33.279Z - response маршрутизирован в handle_client_response
13:55:33.279Z - request received (method=None)
[НЕТ ЛОГОВ О NOTIFICATIONS/FOLLOWUP_RESPONSES]
13:57:59.699Z - ws connection closed (через 2.5 минуты)
```

## Анализ логов

### Что есть в логах:
```
2026-04-17T13:55:33.279763Z [debug] message received
2026-04-17T13:55:33.279829Z [debug] response received, routing to handle_client_response request_id=570a0dc3
2026-04-17T13:55:33.279877Z [info] request received method=None request_id=570a0dc3 session_id=None
2026-04-17T13:57:59.699170Z [info] ws connection closed connection_id=4da15a0a duration=166.435 pending_deferred_tasks=0
```

### Чего НЕТ в логах:
- ❌ `notification sent` для tool_call_update (in_progress)
- ❌ `notification sent` для tool_call_update (completed)
- ❌ `notification sent` для session_info
- ❌ `followup response sent` для завершения turn

## Анализ кода

### 1. resolve_permission_response_impl() генерирует корректный ProtocolOutcome

**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py:2035-2142`](acp-server/src/acp_server/protocol/handlers/prompt.py:2035)

```python
def resolve_permission_response_impl(
    *,
    session: SessionState,
    permission_request_id: JsonRpcId,
    result: Any,
    sessions: dict[str, SessionState],
) -> ProtocolOutcome | None:
    # ... валидация ...
    
    # ✅ Генерируются notifications для tool execution
    notifications.extend(
        build_policy_tool_execution_updates(
            session=session,
            session_id=session_id,
            tool_call_id=tool_call_id,
            allowed=True,
        )
    )
    
    # ✅ Добавляется session_info notification
    session.updated_at = datetime.now(UTC).isoformat()
    notifications.append(
        session_info_notification(
            session_id=session_id,
            title=None,
            updated_at=session.updated_at,
        )
    )
    
    # ✅ Генерируется followup_response для завершения turn
    completed = finalize_active_turn(session=session, stop_reason="end_turn")
    return ProtocolOutcome(
        notifications=notifications,
        followup_responses=[completed] if completed is not None else [],
    )
```

**Вывод:** Код корректно генерирует:
- 2 notifications для tool_call_update (in_progress, completed)
- 1 notification для session_info
- 1 followup_response для завершения turn

### 2. build_policy_tool_execution_updates() генерирует notifications

**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py:1108-1186`](acp-server/src/acp_server/protocol/handlers/prompt.py:1108)

```python
def build_policy_tool_execution_updates(
    *,
    session: SessionState,
    session_id: str,
    tool_call_id: str,
    allowed: bool,
) -> list[ACPMessage]:
    if not allowed:
        # ... cancelled case ...
    
    notifications: list[ACPMessage] = []
    
    # ✅ in_progress notification
    update_tool_call_status(session, tool_call_id, "in_progress")
    notifications.append(
        ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": tool_call_id,
                    "status": "in_progress",
                },
            },
        )
    )
    
    # ✅ completed notification
    completed_content = [...]
    update_tool_call_status(session, tool_call_id, "completed", content=completed_content)
    notifications.append(
        ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "tool_call_update",
                    "toolCallId": tool_call_id,
                    "status": "completed",
                    "content": completed_content,
                },
            },
        )
    )
    return notifications
```

**Вывод:** Функция корректно генерирует 2 notifications.

### 3. ACPProtocol.handle_client_response() возвращает ProtocolOutcome

**Файл:** [`acp-server/src/acp_server/protocol/core.py:390-438`](acp-server/src/acp_server/protocol/core.py:390)

```python
def handle_client_response(self, message: ACPMessage) -> ProtocolOutcome:
    """Обрабатывает входящий response от клиента для server-originated requests."""
    
    if message.id is None:
        return ProtocolOutcome()
    
    # ... обработка client RPC responses ...
    
    # ✅ Вызывается _resolve_permission_response
    resolved = self._resolve_permission_response(message.id, message.result)
    if resolved is None:
        return ProtocolOutcome()
    return resolved  # ✅ Возвращается ProtocolOutcome с notifications и followup_responses
```

**Вывод:** Метод корректно возвращает ProtocolOutcome.

### 4. 🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА: http_server.py НЕ ОТПРАВЛЯЕТ ProtocolOutcome

**Файл:** [`acp-server/src/acp_server/http_server.py:412-511`](acp-server/src/acp_server/http_server.py:412)

```python
async for message in ws:
    if message.type == WSMsgType.TEXT:
        method_name: str | None = None
        session_id: str | None = None
        request_id: str | None = None
        try:
            acp_request = ACPMessage.from_json(message.data)
            method_name = acp_request.method
            request_id = str(acp_request.id) if acp_request.id is not None else None
            
            # ... обработка initialize, session/prompt и т.д. ...
            
            # ✅ Вызывается protocol.handle() для всех сообщений
            outcome = await protocol.handle(acp_request)  # line 480
            
            # ✅ Логируется request received
            conn_logger.info(
                "request received",
                method=method_name,
                request_id=request_id,
                session_id=session_id,
            )  # line 483-488
        except Exception as exc:
            # ... error handling ...
        
        # ✅ Вызывается _finalize_outcome_and_send
        await _finalize_outcome_and_send(
            method_name=method_name,
            session_id=session_id,
            request_id=request_id,
            outcome=outcome,
        )  # line 505-510
```

**Анализ _finalize_outcome_and_send():**

**Файл:** [`acp-server/src/acp_server/http_server.py:331-368`](acp-server/src/acp_server/http_server.py:331)

```python
async def _finalize_outcome_and_send(
    *,
    method_name: str | None,
    session_id: str | None,
    request_id: str | None,
    outcome: ProtocolOutcome,
) -> None:
    """Применяет post-processing outcome и отправляет его в WS."""
    
    # ❌ ПРОБЛЕМА: Для permission response method_name=None
    # Эти условия НЕ выполняются:
    if method_name == "session/cancel" and session_id is not None:
        # ... не выполняется ...
    
    if (
        method_name == "session/prompt"  # ❌ method_name=None!
        and session_id is not None
        and outcome.response is None
        and protocol.should_auto_complete_active_turn(session_id)
    ):
        # ... не выполняется ...
    
    # ✅ Вызывается _send_outcome
    await _send_outcome(outcome, request_id=request_id)  # line 364
    
    if method_name == "shutdown":
        # ... не выполняется ...
```

**Анализ _send_outcome():**

**Файл:** [`acp-server/src/acp_server/http_server.py:289-329`](acp-server/src/acp_server/http_server.py:289)

```python
async def _send_outcome(
    outcome: ProtocolOutcome,
    *,
    request_id: str | None,
) -> None:
    """Отправляет notifications/response/followups в рамках одного lock."""
    
    async with ws_send_lock:
        if ws.closed:
            return
        
        # ✅ Отправляются notifications
        for notification in outcome.notifications:
            notification_json = notification.to_json()
            await ws.send_str(notification_json)
            conn_logger.debug(
                "notification sent",
                method=notification.method,
                payload=_truncate_payload(notification_json),
            )
        
        # ✅ Отправляется response (если есть)
        if outcome.response is not None:
            response_json = outcome.response.to_json()
            await ws.send_str(response_json)
            conn_logger.debug(
                "response sent",
                request_id=request_id,
                has_error=outcome.response.error is not None,
                payload=_truncate_payload(response_json),
            )
        
        # ✅ Отправляются followup_responses
        for followup_response in outcome.followup_responses:
            followup_json = followup_response.to_json()
            await ws.send_str(followup_json)
            conn_logger.debug(
                "followup response sent",
                request_id=followup_response.id,
                payload=_truncate_payload(followup_json),
            )
```

**Вывод:** Функция `_send_outcome()` корректно отправляет все части ProtocolOutcome!

## 🔴 КОРНЕВАЯ ПРИЧИНА ПРОБЛЕМЫ

### Гипотеза 1: Exception в protocol.handle() ❌

Если бы было исключение, мы бы увидели лог:
```
[error] request parse error
```

Но такого лога нет. Значит, исключения не было.

### Гипотеза 2: ws.closed = True ❌

Если бы WebSocket был закрыт, мы бы не увидели лог:
```
[info] request received method=None
```

Но этот лог есть, значит, WebSocket был открыт.

### Гипотеза 3: outcome = ProtocolOutcome() (пустой) ✅ ВЕРОЯТНО

**КРИТИЧЕСКОЕ НАБЛЮДЕНИЕ:**

В логах есть:
```
2026-04-17T13:55:33.279877Z [info] request received method=None request_id=570a0dc3 session_id=None
```

Обратите внимание: **session_id=None**!

Давайте проверим, как извлекается session_id в http_server.py:

```python
if isinstance(acp_request.params, dict):
    raw_session_id = acp_request.params.get("sessionId")
    if isinstance(raw_session_id, str):
        session_id = raw_session_id
```

**ПРОБЛЕМА:** Permission response НЕ содержит `params.sessionId`!

Формат permission response:
```json
{
  "jsonrpc": "2.0",
  "id": "570a0dc3",
  "result": {
    "outcome": "selected",
    "optionId": "allow_once"
  }
}
```

Нет поля `params`, нет `sessionId`!

### Гипотеза 4: resolve_permission_response_impl() возвращает None ✅ КОРНЕВАЯ ПРИЧИНА

Давайте проверим условия в `resolve_permission_response_impl()`:

```python
def resolve_permission_response_impl(
    *,
    session: SessionState,
    permission_request_id: JsonRpcId,
    result: Any,
    sessions: dict[str, SessionState],
) -> ProtocolOutcome | None:
    """Реализация применения решения по permission-request к активному prompt-turn."""
    
    from .permissions import (
        extract_permission_option_id,
        extract_permission_outcome,
        resolve_permission_option_kind,
    )
    
    # ❌ ПРОБЛЕМА: Если active_turn=None, возвращается None
    if session.active_turn is None:
        return None
    
    tool_call_id = session.active_turn.permission_tool_call_id
    
    # ❌ ПРОБЛЕМА: Если permission_tool_call_id=None, возвращается None
    if tool_call_id is None:
        return None
    
    # ... остальная логика ...
```

**КРИТИЧЕСКОЕ НАБЛЮДЕНИЕ:**

В логах первого session/prompt мы видим:
```
2026-04-17T13:55:30.433496Z [debug] session_saved_after_orchestrator_processing session_id=sess_0e14ee66552b
2026-04-17T13:55:30.433532Z [info] request received connection_id=4da15a0a method=session/prompt request_id=56bd102b session_id=sess_0e14ee66552b
```

Затем:
```
2026-04-17T13:55:30.433978Z [debug] response sent connection_id=4da15a0a has_error=False payload='{"jsonrpc":"2.0","id":"56bd102b","result":{"stopReason":"end_turn"}}' request_id=56bd102b
```

**ПРОБЛЕМА:** Response для session/prompt отправлен с `stopReason="end_turn"`!

Это означает, что **active_turn был завершен** до получения permission response!

### Проверка: Когда завершается active_turn?

В логах видим:
```
2026-04-17T13:55:30.432734Z [debug] active turn cleared session_id=sess_0e14ee66552b
```

Это происходит **ДО** отправки permission request!

## Диагноз

### Последовательность событий:

1. **13:55:27** - session/prompt получен
2. **13:55:30** - Агент обработал prompt, создал tool call
3. **13:55:30** - Отправлен session/request_permission
4. **13:55:30** - ❌ **active_turn завершен** (finalize_active_turn вызван)
5. **13:55:30** - Response для session/prompt отправлен с stopReason="end_turn"
6. **13:55:33** - Permission response получен от клиента
7. **13:55:33** - resolve_permission_response_impl() вызван
8. **13:55:33** - ❌ **session.active_turn = None** → возвращается None
9. **13:55:33** - ProtocolOutcome() пустой → ничего не отправляется
10. **13:57:59** - Клиент ждет response, timeout → разрыв соединения

## Корневая причина

**session/prompt завершается слишком рано**, до получения permission response от клиента.

Это происходит потому, что:

1. В [`session_prompt()`](acp-server/src/acp_server/protocol/handlers/prompt.py) после обработки агентом вызывается `finalize_active_turn()`
2. `finalize_active_turn()` очищает `session.active_turn`
3. Когда приходит permission response, `session.active_turn = None`
4. `resolve_permission_response_impl()` возвращает `None`
5. Пустой `ProtocolOutcome()` не содержит notifications и followup_responses
6. Клиент не получает ответ и разрывает соединение по timeout

## Ожидаемое поведение

После отправки `session/request_permission`:

1. **НЕ завершать** active_turn
2. **Ждать** permission response от клиента
3. **После получения** permission response:
   - Отправить notifications (tool_call_update)
   - Выполнить tool call (если allowed)
   - Завершить turn с followup_response

## Решение

### Вариант 1: Не завершать turn при ожидании permission

В [`session_prompt()`](acp-server/src/acp_server/protocol/handlers/prompt.py) проверять, есть ли pending permission request:

```python
# Если есть pending permission request, НЕ завершать turn
if session.active_turn and session.active_turn.permission_request_id:
    # Не вызывать finalize_active_turn()
    # Вернуть ProtocolOutcome без response (deferred)
    return ProtocolOutcome(notifications=notifications)
```

### Вариант 2: Сохранять контекст для late permission response

Сохранять информацию о tool call вне active_turn:

```python
# В SessionState добавить:
pending_permission_contexts: dict[JsonRpcId, PendingPermissionContext]

# PendingPermissionContext содержит:
# - tool_call_id
# - session_id
# - request_id (для followup)
```

### Вариант 3: Использовать deferred completion (текущий подход)

Текущий код в http_server.py использует `deferred_prompt_tasks` для отложенного завершения turn.

**Проблема:** Deferred completion срабатывает только для `method_name="session/prompt"`, но permission response имеет `method_name=None`.

**Решение:** Добавить логику для возобновления deferred completion после permission response.

## Рекомендации

1. **Немедленное исправление:** Не завершать active_turn при наличии pending permission request
2. **Добавить логирование:** Логировать состояние active_turn при обработке permission response
3. **Добавить тесты:** Покрыть сценарий permission response после завершения turn
4. **Документация:** Обновить архитектурную документацию о lifecycle turn с permissions

## Связанные файлы

- [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)
- [`acp-server/src/acp_server/protocol/core.py`](acp-server/src/acp_server/protocol/core.py)
- [`acp-server/src/acp_server/http_server.py`](acp-server/src/acp_server/http_server.py)
- [`doc/architecture/PERMISSION_RESPONSE_HANDLING_ARCHITECTURE.md`](doc/architecture/PERMISSION_RESPONSE_HANDLING_ARCHITECTURE.md)
