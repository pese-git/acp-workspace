# Phase 4 Part 2: TUI Component Refactoring Plan 🎨

**Статус:** Phase 4.5 ✅ Завершена, Phase 4.6 ✅ Завершена
**Дата обновления:** 8 апреля 2026
**Язык:** Русский
**Foundation:** Phase 4.1-4.4 MVVM Architecture (Observable, ViewModels)

---

## 📋 Обзор Phase 4 Part 2

### Цели
1. ✅ Переписать 7 основных TUI компонентов для использования ViewModels из Phase 4.1
2. ✅ Интегрировать DIContainer для инъекции зависимостей (Phase 4.6)
3. ⏳ Реализовать Plugin Support для расширения ViewModels (Phase 4.7)
4. ✅ Подготовить TUI к использованию Event-Driven архитектуры (Phase 3)

### Завершённые фазы

#### Phase 4.5: TUI Component MVVM Refactoring ✅
- HeaderBar с подпиской на UIViewModel (connection_status, is_loading)
- Sidebar с подпиской на SessionViewModel (sessions, selected_session_id)
- ChatView с подпиской на ChatViewModel (messages, tool_calls, streaming)
- PromptInput с подпиской на ChatViewModel (is_streaming)
- FooterBar с подпиской на UIViewModel (error/info/warning messages)
- ToolPanel с подпиской на ChatViewModel (tool_calls)
- **Итог:** 58 новых тестов, все пройдены ✅

#### Phase 4.6: DIContainer Integration ✅
- **Файл:** [`acp-client/src/acp_client/presentation/view_model_factory.py`](acp-client/src/acp_client/presentation/view_model_factory.py)
- **Описание:** ViewModelFactory для централизованной регистрации ViewModels в DIContainer
- **Интеграция в ACPClientApp:** DIContainer инициализируется в `__init__()`, ViewModels разрешаются в `compose()`
- **Backward compatibility:** Все компоненты имеют опциональные параметры ViewModel (работают без них)
- **Тесты:** 17 новых тестов, все пройдены ✅

### 📊 Статистика Phase 4.6

| Метрика | Значение |
|---------|----------|
| Новые файлы | 1 (view_model_factory.py) |
| Модифицированные файлы | 3 (app.py, header.py, __init__.py presentation) |
| Новые тесты | 17 |
| Покрытие | UIViewModel (всегда), SessionViewModel/ChatViewModel (с coordinator) |
| Lint issues | 0 ✅ |
| Type check | Проходит ✅ |

### 🏗️ Архитектура Phase 4.6

```
ACPClientApp.__init__()
    ↓
DIContainer() created
    ↓
ViewModelFactory.register_view_models(container)
    ├─ UIViewModel (singleton) - регистрируется всегда
    ├─ SessionViewModel (singleton) - с coordinator
    └─ ChatViewModel (singleton) - с coordinator
    ↓
app._container.resolve(UIViewModel) → app._ui_vm
app._container.resolve(SessionViewModel) → app._session_vm (или None)
app._container.resolve(ChatViewModel) → app._chat_vm (или None)
    ↓
ACPClientApp.compose()
    ├─ HeaderBar(ui_vm=app._ui_vm)
    ├─ Sidebar(session_vm=app._session_vm)
    ├─ ChatView(chat_vm=app._chat_vm)
    ├─ PromptInput(chat_vm=app._chat_vm)
    ├─ FooterBar(ui_vm=app._ui_vm)
    └─ ToolPanel(chat_vm=app._chat_vm)
```

### 🎯 Ключевые особенности

#### ViewModelFactory
```python
ViewModelFactory.register_view_models(
    container,
    session_coordinator=None,  # опционально
    event_bus=None,
    logger=None,
)
```

#### Singleton scope
- UIViewModel всегда регистрируется (не требует coordinator)
- SessionViewModel регистрируется только если coordinator доступен
- ChatViewModel регистрируется только если coordinator доступен
- Множественные resolve() возвращают один и тот же экземпляр

#### Backward compatibility
- Все компоненты имеют опциональные параметры ViewModel
- Если ViewModel не передан, компонент работает в fallback режиме
- Старые тесты продолжают работать без изменений

---

## 📝 Тесты Phase 4.6

**Файл:** [`acp-client/tests/test_di_container_integration.py`](acp-client/tests/test_di_container_integration.py)

### TestViewModelFactory (8 тестов)
1. ✅ `test_register_view_models_registers_ui_vm` - UIViewModel регистрируется
2. ✅ `test_register_view_models_requires_coordinator` - SessionViewModel требует coordinator
3. ✅ `test_register_view_models_with_coordinator` - все три VM с coordinator
4. ✅ `test_ui_view_model_is_singleton` - UIViewModel singleton
5. ✅ `test_view_models_are_singletons_with_coordinator` - все VM singletons
6. ✅ `test_register_view_models_with_event_bus` - event_bus передается
7. ✅ `test_register_view_models_with_logger` - logger передается
8. ✅ `test_register_view_models_different_containers` - разные контейнеры = разные VM

### TestDIContainerViewModelIntegration (5 тестов)
1. ✅ `test_resolve_ui_view_model` - resolve возвращает UIViewModel
2. ✅ `test_resolve_all_view_models_with_coordinator` - resolve всех VM
3. ✅ `test_container_scope_is_singleton` - Scope.SINGLETON соблюдается
4. ✅ `test_multiple_viewmodel_instances_independent` - VM независимы
5. ✅ `test_container_clear_removes_singletons` - clear() сбрасывает

### TestACPClientAppViewModelIntegration (4 теста)
1. ✅ `test_app_initializes_container` - ACPClientApp создает контейнер
2. ✅ `test_app_registers_ui_viewmodel` - UIViewModel регистрируется в app
3. ✅ `test_app_stores_ui_viewmodel` - UIViewModel сохранён как _ui_vm
4. ✅ `test_app_viewmodels_are_singletons` - ViewModels в app singletons

---

## 🔄 Интеграция с компонентами

### HeaderBar
```python
HeaderBar(ui_vm: UIViewModel | None = None)
# Подписывается на: connection_status, is_loading
# Fallback: показывает "ACP-Client TUI" без VM
```

### Sidebar
```python
Sidebar(session_vm: SessionViewModel | None = None)
# Подписывается на: sessions, selected_session_id, is_loading_sessions
# Fallback: показывает пустой список без VM
```

### ChatView
```python
ChatView(chat_vm: ChatViewModel | None = None)
# Подписывается на: messages, tool_calls, is_streaming, streaming_text
# Fallback: показывает пустой чат без VM
```

### PromptInput
```python
PromptInput(chat_vm: ChatViewModel | None = None)
# Подписывается на: is_streaming
# Fallback: всегда включено без VM
```

### FooterBar
```python
FooterBar(ui_vm: UIViewModel | None = None)
# Подписывается на: connection_status, error_message, info_message, warning_message
# Fallback: пусто без VM
```

### ToolPanel
```python
ToolPanel(chat_vm: ChatViewModel | None = None)
# Подписывается на: tool_calls
# Fallback: показывает "нет активных вызовов" без VM
```

---

## 📋 Следующие шаги (Phase 4.7)

### Phase 4.7: Plugin Support для ViewModels
1. Создать `ViewModelExtension` ABC для расширения
2. Реализовать Plugin Manager для ViewModels
3. Примеры плагинов:
   - LoggingExtension (логирование всех изменений)
   - MetricsExtension (сбор метрик)
   - PersistenceExtension (сохранение состояния)
4. Интеграция плагинов в ViewModelFactory
5. Тесты для плагинов

### Future (Phase 5+)
- Async ViewModels для heavy operations
- ViewModel pooling для очень частых создаваний
- Интеграция с Time Travel Debugging
- Пример: Redux DevTools integration

---

## ✅ Чек-лист Phase 4.6

- [x] ViewModelFactory реализован
- [x] DIContainer интеграция в ACPClientApp
- [x] Инъекция ViewModels в compose()
- [x] Все компоненты имеют опциональные VM параметры
- [x] 17 новых тестов (все пройдены)
- [x] Lint issues исправлены
- [x] Type check пройден
- [x] Документация обновлена
- [x] Backward compatibility сохранена

**Phase 4.6 ЗАВЕРШЕНА** ✅
