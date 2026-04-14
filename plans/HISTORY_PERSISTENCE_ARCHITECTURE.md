# Архитектура персистентности истории переписки

---
**Статус:** ✅ РЕАЛИЗОВАНО (95%)  
**Дата завершения:** 13 апреля 2026  
**Что осталось:** End-to-end тест с перезапуском сервера для валидации полной восстановление истории  

**Связанные компоненты:**
- [`acp-server/src/acp_server/storage/json_file.py`](../../acp-server/src/acp_server/storage/json_file.py)
- [`acp-server/src/acp_server/protocol/state.py`](../../acp-server/src/acp_server/protocol/state.py)
- [`acp-client/src/acp_client/application/session_coordinator.py`](../../acp-client/src/acp_client/application/session_coordinator.py)

**Связанные тесты:**
- [`acp-server/tests/test_storage_json_file.py`](../../acp-server/tests/test_storage_json_file.py)
- [`acp-server/tests/test_end_to_end_with_storage.py`](../../acp-server/tests/test_end_to_end_with_storage.py)
- [`acp-client/tests/test_application_load_session_use_case.py`](../../acp-client/tests/test_application_load_session_use_case.py)

---

## Требование

После перезапуска клиента или переключения сессии пользователь должен видеть:
- ✓ User messages
- ✓ Assistant responses
- ✓ System notifications (session/update, session/turn_complete, etc.)
- ✓ Tool execution history
- ✓ Permission requests/decisions

---

## Проблема

На логах видно что:
1. LLM отвечает: "Hello! How can I assist you today?" ✓
2. agent_processed_prompt_successfully логируется ✓
3. session_saved логируется ✓

Но в сохраненном JSON файле assistant message **отсутствует**.

### Корневая причина

В `prompt_orchestrator.py`:
```python
final_text = _extract_final_assistant_text(session.history)
```

Ищет message в session.history который:
- **НЕ добавлен агентом** (мы его удалили из `agent/orchestrator.py`)
- **НЕ добавлен в `prompt_orchestrator`** (потому что `final_text` пустой)
- Поэтому `if agent_response_text:` НЕ выполняется

---

## Решение: Two-Level History Model

### 1. SessionState содержит две истории

```python
@dataclass
class SessionState:
    # Существующее...
    session_id: str
    cwd: str
    mcp_servers: list
    
    # История СООБЩЕНИЙ (только контент)
    messages_history: list[HistoryMessage] = field(default_factory=list)
    
    # История СОБЫТИЙ (системные уведомления)
    events_history: list[HistoryEvent] = field(default_factory=list)
```

### 2. Две таблицы в JSON storage

```json
{
  "session_id": "sess_123",
  "cwd": "/tmp",
  
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "type": "text",
      "content": "hi",
      "timestamp": "2026-04-13T05:33:22Z",
      "status": "completed"
    },
    {
      "id": "msg_2",
      "role": "assistant",
      "type": "text",
      "content": "Hello! How can I assist you today?",
      "timestamp": "2026-04-13T05:33:23Z",
      "status": "completed"
    }
  ],
  
  "events": [
    {
      "type": "session_update",
      "event": "session_info",
      "title": "hi",
      "timestamp": "2026-04-13T05:33:22Z"
    },
    {
      "type": "session_update",
      "event": "agent_message_chunk",
      "content": "Hello! How can I assist you today?",
      "timestamp": "2026-04-13T05:33:23Z"
    },
    {
      "type": "turn_complete",
      "stopReason": "end_turn",
      "timestamp": "2026-04-13T05:33:23Z"
    }
  ]
}
```

---

## Flow обработки session/prompt

### Phase 1: Setup
```python
# prompt_orchestrator.py
session.active_turn_status = "in_progress"
self.state_manager.add_user_message(session, prompt)
send_ack_notification(session_id)  # Не сохраняем
```

### Phase 2: LLM Processing
```python
agent_response = await agent_orchestrator.process_prompt(
    session, 
    prompt_text
)
# agent_orchestrator RETURNS response.text (не добавляет в историю!)
```

### Phase 3: Update History
```python
# Добавляем assistant message в session.messages_history
self.state_manager.add_assistant_message(session, agent_response.text)

# Записываем события в session.events_history
self.state_manager.add_event(session, {
    "type": "session_update",
    "event": "agent_message_chunk",
    "content": agent_response.text
})
self.state_manager.add_event(session, {
    "type": "turn_complete",
    "stopReason": "end_turn"
})
```

### Phase 4: Persist (В КОНЦЕ!)
```python
# core.py - после полной обработки request
await self._storage.save_session(session)
```

### Phase 5: Send Notifications
```python
# Отправляем клиенту
send_notifications([
    session_update(agent_message_chunk),
    session_update(session_info),
    turn_complete()
])
```

---

## Реализация: StateManager обновления

### ДО (неправильно):
```python
def add_assistant_message(self, session, content):
    session.history.append({
        "role": "assistant",
        "text": content
    })
```

### ПОСЛЕ (правильно):
```python
def add_assistant_message(self, session, content):
    # Добавляем в messages_history
    session.messages_history.append({
        "id": f"msg_{uuid4()}",
        "role": "assistant",
        "type": "text",
        "content": content,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "completed"
    })
    session.updated_at = datetime.now(UTC).isoformat()

def add_event(self, session, event_data):
    # Добавляем в events_history
    session.events_history.append({
        **event_data,
        "timestamp": datetime.now(UTC).isoformat()
    })
```

---

## Storage (JsonFileStorage обновления)

### При save_session()
```python
async def save_session(self, session: SessionState):
    data = {
        "session_id": session.session_id,
        "cwd": session.cwd,
        "title": session.title,
        "updated_at": session.updated_at,
        
        # Сохраняем ОБЕ истории
        "messages": self._serialize_messages(session.messages_history),
        "events": self._serialize_events(session.events_history),
        
        # Остальное...
        "config_values": session.config_values,
        ...
    }
    await self._write_json(session.session_id, data)
```

### При load_session()
```python
async def load_session(self, session_id: str) -> SessionState:
    data = await self._read_json(session_id)
    
    session = SessionState(
        session_id=session_id,
        ...
    )
    
    # Загружаем ОБЕ истории
    session.messages_history = self._deserialize_messages(data.get("messages", []))
    session.events_history = self._deserialize_events(data.get("events", []))
    
    return session
```

---

## Клиент: Восстановление истории

### В ChatViewModel
```python
def restore_session_from_replay(self, session_id, replay_updates):
    # Восстанавливаем messages
    for msg in session.messages_history:
        self.messages.append({
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"]
        })
    
    # Восстанавливаем events
    for event in session.events_history:
        self.display_event(event)
```

---

## Benefits

✅ **Atomic Persistence** - Сессия сохраняется когда она полностью готова
✅ **Message Integrity** - Messages содержат только завершенные сообщения
✅ **Event Tracking** - События отслеживают весь lifecycle
✅ **Full Replay** - Клиент может восстановить полную историю
✅ **Debugging** - Легко видеть что произошло в каком порядке
✅ **Flexible** - Легко добавить новые типы событий

---

## Приоритет

1. **CRITICAL** - Исправить базовую логику сохранения assistant message
   - Agent должен ВОЗВРАЩАТЬ текст (не добавлять в историю)
   - PromptOrchestrator должен добавлять
   - Core.py должен сохранять в КОНЦЕ

2. **HIGH** - Добавить events_history для сохранения notifications
   - StateManager.add_event()
   - Storage обновления

3. **HIGH** - Обновить клиент для восстановления из обеих историй

4. **MEDIUM** - Миграция старых sessions (без events_history)

---

## Последовательность реализации

```
Step 1: Исправить agent/orchestrator
  └─ Вернуть text вместо добавления в историю

Step 2: Исправить prompt_orchestrator  
  └─ Получить response от agent
  └─ Добавить в session.messages_history
  └─ Добавить события в session.events_history

Step 3: Перенести save в core.py
  └─ Сохранять в КОНЦЕ обработки request
  └─ После всех изменений state

Step 4: Обновить SessionState
  └─ Добавить messages_history и events_history
  └─ Сохранить backward compatibility

Step 5: Обновить Storage
  └─ Сериализовать обе истории
  └─ Десериализовать при загрузке

Step 6: Обновить клиент
  └─ Восстанавливать из events_history
  └─ Отображать события в UI
```
