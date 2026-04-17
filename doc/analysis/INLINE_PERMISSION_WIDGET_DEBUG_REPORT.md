# Отчет диагностики: InlinePermissionWidget не отображается в UI

**Дата:** 2026-04-17  
**Статус:** ✅ Проблема найдена  
**Критичность:** Высокая

## Краткое описание проблемы

При получении `session/request_permission` от сервера, встроенный виджет `InlinePermissionWidget` не отображается в `ChatView`, хотя tool call с ID `call_001` виден в статусе `pending`.

## Анализ кода

### 1. Проверка flow permission request

Ожидаемый flow:
```
Server → ACPTransportService → PermissionHandler → App.show_permission_modal → ChatView.show_permission_request → InlinePermissionWidget
```

### 2. Найденная проблема

**Место прерывания flow:** [`acp-client/src/acp_client/application/permission_handler.py:485-507`](acp-client/src/acp_client/application/permission_handler.py:485)

#### Код с проблемой:

```python
async def handle_request(
    self,
    request: RequestPermissionRequest,
    callback: (
        Callable[[str | int, PermissionToolCall, list[PermissionOption]], None]
        | None
    ) = None,
) -> PermissionOutcome:
    """Обработать входящий session/request_permission от сервера."""
    
    try:
        # Если callback передан, используем его для показа modal
        # через coordinator.request_permission
        if callback is not None:
            self._logger.info(
                "permission_callback_provided_showing_ui_modal",
                request_id=request_id,
                session_id=session_id,
                tool_call_id=tool_call.toolCallId,
            )
            outcome = await self._coordinator.request_permission(
                request=request,
                callback=callback,  # ← ПРОБЛЕМА: callback передается дальше
            )
        else:
            # Fallback: показать ошибку логирования и вернуть cancelled
            self._logger.warning(
                "permission_request_no_callback_returning_cancelled",
                request_id=request_id,
                session_id=session_id,
                tool_call_id=tool_call.toolCallId,
                tool_name=tool_call.title,
                message="UI modal НЕ будет показан - callback отсутствует",
            )
            outcome = CancelledPermissionOutcome(outcome="cancelled")
```

#### Проблема: Двойной вызов callback

**Текущее поведение:**
1. `ACPTransportService._handle_permission_request_with_handler()` вызывает `PermissionHandler.handle_request(callback=self._permission_callback)`
2. `PermissionHandler.handle_request()` **снова** вызывает `SessionCoordinator.request_permission(callback=callback)`
3. `SessionCoordinator.request_permission()` вызывает `callback()` **третий раз**

**Результат:** Callback вызывается **дважды** вместо одного раза:
- Первый раз в `SessionCoordinator.request_permission()` (строка 242)
- Второй раз... нигде, потому что `PermissionHandler` передает callback в coordinator вместо того, чтобы вызвать его напрямую

**Фактическая проблема:** `PermissionHandler.handle_request()` делегирует вызов callback в `SessionCoordinator.request_permission()`, который:
1. Создает новый `PermissionRequest` через `request_manager.create_request()`
2. Вызывает `callback(request.id, tool_call, options)` для показа UI
3. Ждет результата через `await perm_request.wait_for_outcome()`

Но `PermissionHandler` **уже должен был** управлять этим процессом сам, а не делегировать его coordinator'у!

### 3. Корректный flow (как должно быть)

```python
# В PermissionHandler.handle_request():
if callback is not None:
    # Создать PermissionRequest через self._request_manager
    perm_request = self._request_manager.create_request(
        request_id=request.id,
        session_id=request.params.sessionId,
        tool_call=request.params.toolCall,
        options=request.params.options,
        timeout=300.0,
    )
    
    # Вызвать callback напрямую для показа UI
    callback(request.id, request.params.toolCall, request.params.options)
    
    # Дождаться результата
    outcome = await perm_request.wait_for_outcome()
else:
    outcome = CancelledPermissionOutcome(outcome="cancelled")
```

## Диагностические логи

### Ожидаемые события в логах:

1. ✅ `permission_callback_set` - callback установлен в `ACPTransportService`
2. ✅ `handling_permission_request_with_handler` - начало обработки в `ACPTransportService`
3. ✅ `permission_callback_provided_showing_ui_modal` - callback передан в `PermissionHandler`
4. ✅ `showing_permission_modal_to_user` - callback вызван в `SessionCoordinator`
5. ❌ `showing_inline_permission_widget` - **НЕ ВЫЗЫВАЕТСЯ** в `App.show_permission_modal`
6. ❌ События из `InlinePermissionWidget` - **НЕ СОЗДАЕТСЯ**
7. ❌ События из `ChatViewPermissionManager` - **НЕ МОНТИРУЕТСЯ**

### Почему виджет не показывается:

Проблема в архитектуре: `PermissionHandler.handle_request()` делегирует управление в `SessionCoordinator.request_permission()`, который:
- Создает **новый** `PermissionRequest` через свой `request_manager`
- Вызывает callback
- Ждет результата

Но `PermissionHandler` **уже имеет** свой `_request_manager` и должен управлять lifecycle сам!

## Решение

### Вариант 1: Исправить PermissionHandler (рекомендуется)

Изменить [`acp-client/src/acp_client/application/permission_handler.py:424-570`](acp-client/src/acp_client/application/permission_handler.py:424):

```python
async def handle_request(
    self,
    request: RequestPermissionRequest,
    callback: (
        Callable[[str | int, PermissionToolCall, list[PermissionOption]], None]
        | None
    ) = None,
) -> PermissionOutcome:
    """Обработать входящий session/request_permission от сервера."""
    request_id = request.id
    session_id = request.params.sessionId
    tool_call = request.params.toolCall

    self._logger.info(
        "handling_permission_request",
        request_id=request_id,
        session_id=session_id,
        tool_call_id=tool_call.toolCallId,
    )

    try:
        if callback is not None:
            # Создать PermissionRequest через наш request_manager
            perm_request = self._request_manager.create_request(
                request_id=request_id,
                session_id=session_id,
                tool_call=tool_call,
                options=request.params.options,
                timeout=300.0,
            )
            
            self._logger.info(
                "permission_callback_provided_showing_ui_modal",
                request_id=request_id,
                session_id=session_id,
                tool_call_id=tool_call.toolCallId,
            )
            
            # Вызвать callback напрямую для показа UI
            callback(request_id, tool_call, request.params.options)
            
            # Дождаться результата выбора пользователя
            self._logger.debug(
                "waiting_for_user_permission_choice",
                request_id=request_id,
                session_id=session_id,
            )
            outcome = await perm_request.wait_for_outcome()
            
            self._logger.info(
                "permission_outcome_received",
                request_id=request_id,
                outcome=outcome.outcome,
            )
        else:
            # Fallback: без callback не можем показать UI
            self._logger.warning(
                "permission_request_no_callback_returning_cancelled",
                request_id=request_id,
                session_id=session_id,
                tool_call_id=tool_call.toolCallId,
            )
            outcome = CancelledPermissionOutcome(outcome="cancelled")

    except asyncio.CancelledError:
        self._logger.info(
            "permission_request_cancelled",
            request_id=request_id,
        )
        outcome = CancelledPermissionOutcome(outcome="cancelled")

    except Exception as e:
        self._logger.error(
            "permission_request_error",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        outcome = CancelledPermissionOutcome(outcome="cancelled")

    # Отправить response на сервер
    try:
        response = self.build_response(request_id, outcome)
        self._logger.info(
            "sending_permission_response_to_server",
            request_id=request_id,
            session_id=session_id,
            tool_call_id=tool_call.toolCallId,
            outcome=outcome.outcome,
            option_id=getattr(outcome, 'optionId', None),
        )
        await self._transport.send(response.to_dict())

        self._logger.info(
            "permission_response_sent_successfully",
            request_id=request_id,
            session_id=session_id,
            tool_call_id=tool_call.toolCallId,
            outcome=outcome.outcome,
        )

    except Exception as e:
        self._logger.error(
            "permission_response_send_failed",
            request_id=request_id,
            session_id=session_id,
            tool_call_id=tool_call.toolCallId,
            error=str(e),
            error_type=type(e).__name__,
        )

    finally:
        # Очистить request из менеджера
        self._request_manager.remove_request(request_id)

    return outcome
```

### Вариант 2: Упростить архитектуру (альтернатива)

Удалить дублирование между `PermissionHandler._request_manager` и `SessionCoordinator.request_permission()`:
- Оставить управление lifecycle только в `PermissionHandler`
- Удалить метод `SessionCoordinator.request_permission()` или сделать его простым wrapper

## Проверка решения

После исправления проверить:

1. **Логи должны показывать:**
   ```
   permission_callback_set
   handling_permission_request_with_handler
   permission_callback_provided_showing_ui_modal
   showing_inline_permission_widget  ← Должен появиться!
   permission_widget_mounted         ← Должен появиться!
   ```

2. **UI должен показывать:**
   - InlinePermissionWidget в ChatView
   - Кнопки для выбора опций (Allow Once, Reject Once, и т.д.)
   - Tool call информацию (kind, title, toolCallId)

3. **Тесты должны проходить:**
   ```bash
   cd acp-client
   uv run python -m pytest tests/test_tui_inline_permission_widget_mvvm.py -v
   uv run python -m pytest tests/test_tui_chat_view_permission_integration.py -v
   ```

## Дополнительные наблюдения

### Архитектурная проблема

Текущая архитектура имеет **дублирование ответственности**:

1. `PermissionHandler` имеет `_request_manager` для управления requests
2. `SessionCoordinator` имеет метод `request_permission()` который **также** создает requests через handler's manager
3. Это создает путаницу: кто отвечает за lifecycle?

**Рекомендация:** Оставить управление lifecycle только в `PermissionHandler`, а `SessionCoordinator.request_permission()` использовать только для resolve/cancel операций из UI.

## Связанные файлы

- [`acp-client/src/acp_client/application/permission_handler.py`](acp-client/src/acp_client/application/permission_handler.py) - **Требует исправления**
- [`acp-client/src/acp_client/application/session_coordinator.py`](acp-client/src/acp_client/application/session_coordinator.py) - Может быть упрощен
- [`acp-client/src/acp_client/infrastructure/services/acp_transport_service.py`](acp-client/src/acp_client/infrastructure/services/acp_transport_service.py) - Работает корректно
- [`acp-client/src/acp_client/tui/app.py`](acp-client/src/acp_client/tui/app.py) - Работает корректно
- [`acp-client/src/acp_client/tui/components/chat_view.py`](acp-client/src/acp_client/tui/components/chat_view.py) - Работает корректно

## Заключение

**Корневая причина:** `PermissionHandler.handle_request()` делегирует управление в `SessionCoordinator.request_permission()` вместо того, чтобы управлять lifecycle напрямую через свой `_request_manager`.

**Решение:** Изменить `PermissionHandler.handle_request()` чтобы он:
1. Создавал `PermissionRequest` через свой `_request_manager`
2. Вызывал callback напрямую
3. Ждал результата через `await perm_request.wait_for_outcome()`
4. Отправлял response на сервер
5. Очищал request из manager

Это устранит дублирование и обеспечит корректный показ `InlinePermissionWidget` в UI.
