# Этап 4 (HIGH): Интеграция оркестраторов в prompt.py — Детальный план

**Статус:** 🔄 Активная разработка  
**Дата:** 2026-04-12  
**Приоритет:** 🔴 HIGH  

---

## 📋 Обзор

Этап 4 реализует интеграцию всех компонентов Этапа 3 (StateManager, PlanBuilder, TurnLifecycleManager, PromptOrchestrator) и Этапа 2 (ToolCallHandler, PermissionManager, ClientRPCHandler) в основную функцию `session_prompt` в файле [`prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py).

**Главная цель:** Полностью рефакторить `session_prompt` для использования `PromptOrchestrator` вместо разбросанной логики.

---

## 🎯 Задачи

### Задача 1: Обновить импорты в prompt.py
**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)

**Добавить импорты:**
```python
from .prompt_orchestrator import PromptOrchestrator
from .state_manager import StateManager
from .plan_builder import PlanBuilder
from .turn_lifecycle_manager import TurnLifecycleManager
from .tool_call_handler import ToolCallHandler
from .permission_manager import PermissionManager
from .client_rpc_handler import ClientRPCHandler
```

**Статус:** 📋 Требуется

---

### Задача 2: Создать factory для инициализации PromptOrchestrator
**Файл:** [`acp-server/src/acp_server/protocol/handlers/prompt.py`](acp-server/src/acp_server/protocol/handlers/prompt.py)

**Функция:**
```python
def create_prompt_orchestrator() -> PromptOrchestrator:
    """Создает полностью инициализированный PromptOrchestrator со всеми компонентами.
    
    Returns:
        Готовый к использованию PromptOrchestrator
    """
    state_manager = StateManager()
    plan_builder = PlanBuilder()
    turn_lifecycle_manager = TurnLifecycleManager()
    tool_call_handler = ToolCallHandler()
    permission_manager = PermissionManager()
    client_rpc_handler = ClientRPCHandler()
    
    return PromptOrchestrator(
        state_manager=state_manager,
        plan_builder=plan_builder,
        turn_lifecycle_manager=turn_lifecycle_manager,
        tool_call_handler=tool_call_handler,
        permission_manager=permission_manager,
        client_rpc_handler=client_rpc_handler,
    )
```

**Статус:** 📋 Требуется

---

### Задача 3: Рефакторить session_prompt функцию
**Текущая функция:** [`session_prompt`](acp-server/src/acp_server/protocol/handlers/prompt.py:243) (2156 строк)

**Новая структура:**
```python
async def session_prompt(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    sessions: dict[str, SessionState],
    config_specs: dict[str, dict[str, Any]],
    agent_orchestrator: AgentOrchestrator | None = None,
) -> ProtocolOutcome:
    """Обрабатывает session/prompt через PromptOrchestrator.
    
    Новая реализация делегирует всю логику оркестратору.
    """
    
    # Валидация параметров (этот код остается)
    session_id = params.get("sessionId")
    prompt = params.get("prompt")
    
    # Проверки безопасности
    if not isinstance(session_id, str):
        return ProtocolOutcome(response=ACPMessage.error_response(...))
    
    session = sessions.get(session_id)
    if session is None:
        return ProtocolOutcome(response=ACPMessage.error_response(...))
    
    if not isinstance(prompt, list):
        return ProtocolOutcome(response=ACPMessage.error_response(...))
    
    content_error = validate_prompt_content(request_id, prompt)
    if content_error is not None:
        return ProtocolOutcome(response=content_error)
    
    # Делегирование оркестратору
    orchestrator = create_prompt_orchestrator()
    return await orchestrator.handle_prompt(
        request_id=request_id,
        params=params,
        session=session,
        sessions=sessions,
        agent_orchestrator=agent_orchestrator,
    )
```

**Статус:** 📋 Требуется

---

### Задача 4: Добавить обработчик session/cancel через PromptOrchestrator
**Функция:** `session_cancel` (новая или существующая)

**Реализация:**
```python
async def session_cancel(
    request_id: JsonRpcId | None,
    params: dict[str, Any],
    sessions: dict[str, SessionState],
) -> ProtocolOutcome:
    """Обрабатывает session/cancel через PromptOrchestrator."""
    
    session_id = params.get("sessionId")
    session = sessions.get(session_id)
    
    if session is None:
        return ProtocolOutcome(
            response=ACPMessage.error_response(
                request_id,
                code=-32001,
                message=f"Session not found: {session_id}",
            )
        )
    
    # Делегирование оркестратору
    orchestrator = create_prompt_orchestrator()
    return await orchestrator.handle_cancel(
        request_id=request_id,
        session=session,
        sessions=sessions,
    )
```

**Статус:** 📋 Требуется

---

### Задача 5: Обновить обработку client RPC responses
**Функции в prompt.py:**
- `resolve_pending_client_rpc_response_impl` (строки ~1426-1430)
- `finalize_failed_client_rpc_request` (строки ~2007-2057)
- `resolve_permission_response_impl` (строки ~2059-2155)

**Изменения:**
1. Оставить функции для совместимости
2. Добавить вызовы через PromptOrchestrator где подходящее
3. Обновить импорты

**Статус:** 📋 Требуется

---

### Задача 6: Написать интеграционные тесты
**Файл:** [`acp-server/tests/test_prompt_integration.py`](acp-server/tests/test_prompt_integration.py) (новый)

**Тесты (45-50 unit-тестов):**

```python
class TestPromptSessionIntegration:
    """Интеграционные тесты session/prompt с PromptOrchestrator."""
    
    async def test_session_prompt_with_orchestrator(self):
        """Полный цикл session/prompt через оркестратор."""
        # Arrange
        orchestrator = create_prompt_orchestrator()
        session = SessionState(session_id="sess_1", ...)
        sessions = {"sess_1": session}
        params = {"sessionId": "sess_1", "prompt": [...]}
        
        # Act
        outcome = await session_prompt(
            request_id="req_1",
            params=params,
            sessions=sessions,
            config_specs={},
            agent_orchestrator=None,
        )
        
        # Assert
        assert outcome.response is None or outcome.response.method is None
        assert len(outcome.notifications) > 0
    
    async def test_session_cancel_integration(self):
        """Полный цикл session/cancel через оркестратор."""
        # Arrange
        session = SessionState(session_id="sess_1", ...)
        session.active_turn = ActiveTurnState(...)
        sessions = {"sess_1": session}
        params = {"sessionId": "sess_1"}
        
        # Act
        outcome = await session_cancel(
            request_id="req_1",
            params=params,
            sessions=sessions,
        )
        
        # Assert
        assert session.active_turn is None or session.active_turn.stop_reason == "cancelled"
```

**Статус:** 📋 Требуется

---

### Задача 7: Тестирование с make check
**Команда:**
```bash
make check
```

**Ожидаемый результат:**
- ✅ Все 550+ тесты Этапа 3 проходят
- ✅ Новые 45-50 интеграционных тестов проходят
- ✅ Ruff check: 0 ошибок
- ✅ Type check: 0 ошибок
- ✅ Pytest: 100% success rate

**Статус:** 📋 Требуется

---

## 📊 Метрики планирования

| Метрика | Значение |
|---------|----------|
| **Файлы для изменения** | 2 (prompt.py, новый test_prompt_integration.py) |
| **Строк кода к удалению** | ~200-300 (дублирование в session_prompt) |
| **Строк кода к добавлению** | ~100-150 (новые функции + тесты) |
| **Новых тестов** | ~45-50 |
| **Ожидаемое покрытие** | 95%+ |
| **Совместимость** | 100% (breaking changes: нет) |

---

## 🔄 Процесс интеграции

### Фаза 1: Подготовка (1-2 часа)
1. ✅ Добавить импорты в prompt.py
2. ✅ Создать factory функцию
3. ✅ Подготовить структуру тестов

### Фаза 2: Рефакторинг (2-3 часа)
1. ⏳ Обновить session_prompt
2. ⏳ Обновить session_cancel (если требуется)
3. ⏳ Обновить client RPC handlers

### Фаза 3: Тестирование (1-2 часа)
1. ⏳ Написать интеграционные тесты
2. ⏳ Запустить make check
3. ⏳ Регрессионное тестирование

### Фаза 4: Валидация (1 час)
1. ⏳ Проверка ACP conformance
2. ⏳ Type safety валидация
3. ⏳ Финальный review

---

## ⚠️ Потенциальные риски

| Риск | Вероятность | Импакт | Стратегия |
|------|-----------|------|----|
| **Regression в session/prompt** | Средняя | Критический | Comprehensive integration tests |
| **Циклические импорты** | Низкая | Высокий | Careful import order |
| **Async issues** | Средняя | Средний | Thorough async testing |
| **Состояние session** | Средняя | Высокий | Mock session objects |
| **Breaking API changes** | Низкая | Критический | Maintain backward compatibility |

---

## ✅ Критерии успеха

1. **Функциональность:** session/prompt и session/cancel работают через PromptOrchestrator
2. **Тесты:** 45-50 новых integration тестов, все проходят
3. **Качество:** make check 100% успех, 0 errors/warnings
4. **Совместимость:** Все существующие tests проходят, ACP protocol соблюдается
5. **Документация:** README обновлена с описанием новой архитектуры

---

## 📚 Ссылки на компоненты

- [`PromptOrchestrator`](acp-server/src/acp_server/protocol/handlers/prompt_orchestrator.py)
- [`StateManager`](acp-server/src/acp_server/protocol/handlers/state_manager.py)
- [`PlanBuilder`](acp-server/src/acp_server/protocol/handlers/plan_builder.py)
- [`TurnLifecycleManager`](acp-server/src/acp_server/protocol/handlers/turn_lifecycle_manager.py)
- [`ToolCallHandler`](acp-server/src/acp_server/protocol/handlers/tool_call_handler.py)
- [`PermissionManager`](acp-server/src/acp_server/protocol/handlers/permission_manager.py)
- [`ClientRPCHandler`](acp-server/src/acp_server/protocol/handlers/client_rpc_handler.py)

---

**Документ создан:** 2026-04-12  
**Версия:** 1.0  
**Статус:** 📋 Ready for implementation
