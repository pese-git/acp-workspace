# Этап 5 (CRITICAL): Глубокая интеграция PromptOrchestrator в session_prompt() — Детальный план

**Статус:** 🚀 Инициирован  
**Дата:** 2026-04-12  
**Приоритет:** 🔴 CRITICAL  

---

## 📋 Обзор

Этап 5 завершает интеграцию архитектуры путем глубокого рефакторинга функции [`session_prompt()`](acp-server/src/acp_server/protocol/handlers/prompt.py:288) для полного использования [`PromptOrchestrator`](acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py).

**Главная цель:** Заменить разбросанную логику обработки prompt-turn на унифицированный вызов оркестратора со всеми соответствующими обработчиками.

---

## 🎯 Задачи Этапа 5

### Задача 1: Анализ текущего состояния session_prompt()

**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py:288)

**Текущая структура:**
- **Размер:** ~900 строк логики
- **Основные компоненты:**
  1. Валидация параметров (sessionId, prompt)
  2. Проверка существования сессии
  3. Проверка содержимого промпта
  4. Обработка через agent_orchestrator (если передан)
  5. Инициализация active_turn
  6. Извлечение текста из prompt blocks
  7. Обработка prompt directives
  8. Построение notifications
  9. Управление tool calls, permissions, RPC запросами
  10. Финализация turn

**Статус:** 📊 Анализ выполнен

---

### Задача 2: Определить точки интеграции PromptOrchestrator

**PromptOrchestrator имеет методы:**

| Метод | Назначение | Статус |
|-------|-----------|--------|
| `handle_prompt()` | Основная обработка prompt-turn | ✅ Готов к использованию |
| `handle_cancel()` | Обработка отмены turn | ✅ Готов к использованию |
| `handle_permission_response()` | Обработка ответа на permission request | ✅ Готов к использованию |
| `handle_pending_client_rpc_response()` | Обработка ответа на client RPC | ✅ Готов к использованию |

**Интеграционные точки в session_prompt():**

1. **Точка A (Если agent_orchestrator передан):**
   - Строки 349-357 в текущем prompt.py
   - Использование: Делегировать обработку на `orchestrator.handle_prompt()`
   - Логика: Простой вызов без промежуточной валидации

2. **Точка B (Legacy режим без агента):**
   - Строки 368-640 в текущем prompt.py
   - Использование: Может быть сохранена как fallback или заменена минимальной реализацией
   - Логика: ACK + завершение

**Статус:** 📊 Определено

---

### Задача 3: Рефакторить session_prompt() для использования orchestrator

**Новая структура функции:**

```python
async def session_prompt(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    sessions: dict[str, SessionState],
    config_specs: dict[str, dict[str, Any]],
    agent_orchestrator: AgentOrchestrator | None = None,
) -> ProtocolOutcome:
    """Обрабатывает session/prompt, делегируя логику PromptOrchestrator.
    
    Этап 5: Глубокая интеграция оркестратора.
    """
    
    # === ЭТАП 1: Валидация входных параметров ===
    session_id = params.get("sessionId")
    prompt = params.get("prompt")
    
    # Проверка sessionId
    if not isinstance(session_id, str):
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: sessionId is required",
            )
        )
    
    # Получить сессию
    session = sessions.get(session_id)
    if session is None:
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32001,
                message=f"Session not found: {session_id}",
            )
        )
    
    # Проверка формата prompt
    if not isinstance(prompt, list):
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32602,
                message="Invalid params: prompt must be an array",
            )
        )
    
    # Валидация содержимого prompt
    content_error = validate_prompt_content(request_id, prompt)
    if content_error is not None:
        return ProtocolOutcome(response=content_error)
    
    # === ЭТАП 2: Обработка через PromptOrchestrator ===
    
    # Если передан agent_orchestrator, использовать оркестратор
    if agent_orchestrator is not None:
        # Создать оркестратор с полной конфигурацией
        orchestrator = create_prompt_orchestrator()
        
        try:
            outcome = await orchestrator.handle_prompt(
                request_id=request_id,
                params=params,
                session=session,
                sessions=sessions,
                agent_orchestrator=agent_orchestrator,
            )
            return outcome
        except Exception as e:
            logger.error(
                "orchestrator handle_prompt failed",
                session_id=session_id,
                error=str(e),
            )
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32603,
                    message=f"Internal error: {str(e)}",
                )
            )
    
    # === ЭТАП 3: Legacy режим (без агента) ===
    # Сохраняем текущую реализацию для backward compatibility
    # Здесь может быть минимальная реализация для случаев,
    # когда agent_orchestrator не передан
    
    # Проверить, нет ли активного turn
    if session.active_turn is not None:
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32002,
                message=f"Session busy: active turn in progress for {session_id}",
            )
        )
    
    # Инициализация
    session.active_turn = ActiveTurnState(
        prompt_request_id=request_id,
        session_id=session_id,
    )
    
    # Извлечение текста
    text_blocks = []
    for block in prompt:
        if (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            text_blocks.append(block["text"])
    
    text_preview = text_blocks[0] if text_blocks else "Prompt received"
    
    # Подготовка notifications
    notifications: list[ACPMessage] = []
    
    # ACK notification
    agent_text = f"ACK: {text_preview}"
    notifications.append(
        ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": agent_text,
                    },
                },
            },
        )
    )
    
    # Обновление истории
    session.history.append({"role": "user", "content": prompt})
    session.history.append(
        {
            "role": "agent",
            "content": [{"type": "text", "text": agent_text}],
        }
    )
    
    # Обновление timestamp
    session.updated_at = datetime.now(UTC).isoformat()
    
    # Session info update
    title_changed = False
    if session.title is None and text_preview:
        session.title = text_preview[:80]
        title_changed = True
    
    notifications.append(
        session_info_notification(
            session_id=session_id,
            title=session.title if title_changed else None,
            updated_at=session.updated_at,
        )
    )
    
    # Available commands update
    notifications.append(
        ACPMessage.notification(
            "session/update",
            {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "available_commands_update",
                    "availableCommands": _serialize_available_commands(
                        session.available_commands
                    ),
                },
            },
        )
    )
    
    # Завершить turn
    session.active_turn = None
    
    return ProtocolOutcome(
        response=ACPMessage.response(request_id, {"stopReason": "end_turn"}),
        notifications=notifications,
    )
```

**Ключевые изменения:**

1. ✅ Валидация параметров (остается без изменений)
2. ✅ Создание orchestrator при наличии agent_orchestrator
3. ✅ Делегирование `orchestrator.handle_prompt()`
4. ✅ Обработка ошибок оркестратора
5. ✅ Legacy режим для backward compatibility
6. ✅ Полная документация

**Статус:** 📋 Требуется реализация

---

### Задача 4: Обновить session_cancel() для интеграции с оркестратором

**Текущее расположение:** [`session_cancel()`](acp-server/src/acp_server/protocol/handlers/prompt.py:643)

**Новая реализация:**

```python
def session_cancel(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    sessions: dict[str, SessionState],
) -> ProtocolOutcome:
    """Отменяет текущий turn через PromptOrchestrator.
    
    Этап 5: Использование оркестратора для отмены.
    """
    
    session_id = params.get("sessionId")
    notifications: list[ACPMessage] = []
    
    if isinstance(session_id, str) and session_id in sessions:
        session = sessions[session_id]
        
        # Использовать оркестратор для отмены
        orchestrator = create_prompt_orchestrator()
        
        try:
            outcome = orchestrator.handle_cancel(
                request_id=request_id,
                params=params,
                session=session,
                sessions=sessions,
            )
            return outcome
        except Exception as e:
            logger.error(
                "orchestrator handle_cancel failed",
                session_id=session_id,
                error=str(e),
            )
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    request_id,
                    code=-32603,
                    message=f"Internal error: {str(e)}",
                )
            )
    
    if request_id is None:
        return ProtocolOutcome(response=None, notifications=[])
    
    return ProtocolOutcome(
        response=ACPMessage.response(request_id, None),
        notifications=[],
    )
```

**Статус:** 📋 Требуется реализация

---

### Задача 5: Создать интеграционные тесты для Этапа 5

**Файл:** [`acp-server/tests/test_prompt_orchestrator_integration.py`](acp-server/tests/test_prompt_orchestrator_integration.py)

**Тесты для session_prompt():**

1. **test_session_prompt_with_agent_orchestrator**
   - Проверить делегирование на `orchestrator.handle_prompt()`
   - Валидировать ProtocolOutcome с notifications

2. **test_session_prompt_without_agent_orchestrator**
   - Проверить legacy режим
   - Валидировать ACK notification и session info update

3. **test_session_prompt_invalid_sessionId**
   - Проверить валидацию sessionId
   - Ожидать error_response с кодом -32602

4. **test_session_prompt_session_not_found**
   - Проверить ошибку "Session not found"
   - Ожидать error_response с кодом -32001

5. **test_session_prompt_invalid_prompt_format**
   - Проверить валидацию формата prompt
   - Ожидать error_response

6. **test_session_cancel_with_orchestrator**
   - Проверить делегирование на `orchestrator.handle_cancel()`
   - Валидировать результат

7. **test_session_cancel_no_active_turn**
   - Проверить поведение при отсутствии active turn
   - Ожидать empty notifications

**Статус:** 📋 Требуется реализация

---

### Задача 6: Провести финальную валидацию

**Проверки перед коммитом:**

```bash
# 1. Запустить проверку типов
uv run --directory acp-server pyright .

# 2. Запустить linting
uv run --directory acp-server ruff check .

# 3. Запустить тесты
uv run --directory acp-server python -m pytest tests/test_prompt_orchestrator_integration.py -v

# 4. Запустить полный набор проверок
make check

# 5. Проверить импорты
python3 -c "from acp_server.protocol.handlers.prompt import session_prompt, session_cancel, create_prompt_orchestrator; print('✅ All imports successful')"
```

**Ожидаемые результаты:**
- ✅ Все тесты проходят
- ✅ Нет ошибок типизации
- ✅ Нет ошибок linting
- ✅ Все импорты работают

**Статус:** 📋 Требуется выполнение

---

### Задача 7: Git коммит результатов Этапа 5

**Сообщение коммита:**

```
Этап 5: Глубокая интеграция PromptOrchestrator в session_prompt()

- Рефакторить session_prompt() для использования PromptOrchestrator
- Обновить session_cancel() для использования оркестратора
- Добавить интеграционные тесты для новой реализации
- Сохранить backward compatibility с legacy режимом
- Все проверки (type, lint, test) успешны

Refs: STAGE_5_DETAILED_PLAN.md
```

**Файлы для коммита:**
- `acp-server/src/acp_server/protocol/handlers/prompt.py` (модифицирован)
- `acp-server/tests/test_prompt_orchestrator_integration.py` (новый)
- `acp-server/STAGE_5_DETAILED_PLAN.md` (новый)

**Статус:** 📋 Требуется выполнение

---

## 🔄 Результаты по завершении Этапа 5

| Метрика | Целевое значение |
|---------|-----------------|
| **Строк рефакторинга в session_prompt()** | ~300 (реструктуризация) |
| **Новых интеграционных тестов** | 7+ |
| **Покрытие тестами session_prompt()** | 100% путей |
| **Покрытие тестами session_cancel()** | 100% путей |
| **Git коммиты** | 1 ✅ |
| **Backward compatibility** | 100% сохранена |
| **Документация** | STAGE_5_DETAILED_PLAN.md ✅ |

---

## 🏛️ Архитектурное состояние после Этапа 5

```
До Этапа 5:
  session_prompt() → [разбросанная логика] → ProtocolOutcome
  session_cancel()  → [разбросанная логика] → ProtocolOutcome
  
↓

После Этапа 5:
  session_prompt() → [валидация] → PromptOrchestrator.handle_prompt() → ProtocolOutcome
  session_cancel()  → [валидация] → PromptOrchestrator.handle_cancel()  → ProtocolOutcome
  
  PromptOrchestrator → [6 компонентов Этапа 2-3] → Полная оркестрация
```

---

## 📊 Критерии успеха Этапа 5

✅ session_prompt() полностью использует PromptOrchestrator  
✅ session_cancel() полностью использует PromptOrchestrator  
✅ Валидация параметров сохранена  
✅ Legacy режим работает для backward compatibility  
✅ Все интеграционные тесты проходят  
✅ make check выполняется успешно  
✅ Git коммит создан и задокументирован  
✅ Нет регрессий функциональности  

---

## 🚀 Что дальше (Этап 6+)

После Этапа 5 проект будет готов к:
- **Этап 6:** Интеграция с WebSocket/HTTP транспортом
- **Этап 7:** End-to-end тестирование сценариев
- **Этап 8:** Оптимизация производительности
- **Этап 9:** Документация и примеры использования
- **Этап 10:** Release подготовка
