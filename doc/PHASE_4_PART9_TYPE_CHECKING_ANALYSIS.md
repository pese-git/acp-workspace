# Phase 4.9 - Анализ Type Checking Ошибок acp-client

**Дата анализа:** 2026-04-09  
**Type Checker:** ty (Rust-based type checker)  
**Целевой пакет:** acp-client  
**Версия Python:** 3.12+

---

## 1. Обзор результатов

| Метрика | Значение |
|---------|----------|
| **Всего диагностик** | 90 |
| **Ошибки (errors)** | 74 |
| **Предупреждения (warnings)** | 16 |
| **Файлов с ошибками** | 18 |
| **Критических проблем** | 28 |

---

## 2. Категоризация ошибок по типам

### 2.1 Missing Arguments (14 ошибок) - **КРИТИЧЕСКИЙ ПРИОРИТЕТ**

**Статус:** Это реальные ошибки - компоненты требуют обязательные параметры  
**Затронутые компоненты:**

| Компонент | Параметр | Файлы | Количество |
|-----------|----------|-------|-----------|
| `TerminalLogModal` | `terminal_log_vm` | app.py, test_* | 2 |
| `FileViewerModal` | `file_viewer_vm` | app.py, test_tui_file_viewer.py | 3 |
| `PermissionModal` | `permission_vm` | app.py, test_tui_permission_modal.py | 4 |
| `FileTree` | `filesystem_vm` | test_tui_file_tree.py | 5 |

**Файлы с ошибками:**
- `src/acp_client/tui/app.py:490` - TerminalLogModal без terminal_log_vm
- `src/acp_client/tui/app.py:666` - FileViewerModal без file_viewer_vm
- `src/acp_client/tui/app.py:977` - PermissionModal без permission_vm
- `tests/test_tui_file_tree.py` - 5 тестов без filesystem_vm
- `tests/test_tui_file_viewer.py` - 2 теста без file_viewer_vm
- `tests/test_tui_permission_modal.py` - 3 теста без permission_vm

**Причина:** ViewModels стали обязательными параметрами после MVVM рефакторинга, но не все места обновлены

**Решение:** Передать инстансы ViewModels в конструкторы компонентов

---

### 2.2 Invalid Argument Type для subscribe/unsubscribe (28 ошибок) - **ВЫСОКИЙ ПРИОРИТЕТ**

**Статус:** Конфликт типов между определением и использованием EventHandler  
**Файл:** `tests/test_infrastructure_events_bus.py` - все 28 ошибок

**Проблема:**
```python
# Объявление в bus.py
def subscribe(self, event_type: type[T], handler: EventHandler) -> None:
    # EventHandler = Callable[[DomainEvent], Any]

# Использование в тесте:
def sync_handler(event: SessionCreatedEvent) -> None:
    pass

bus.subscribe(SessionCreatedEvent, sync_handler)
# Ошибка: тип sync_handler не совпадает с EventHandler
```

**Причина:** Type checker считает, что специфичный тип `SessionCreatedEvent` не совпадает с базовым `DomainEvent`

**Решение:** Использовать `cast()` или обновить аннотацию типов для EventHandler

---

### 2.3 Unused Type Ignore Comments (16 предупреждений) - **НИЗКИЙ ПРИОРИТЕТ**

**Файлы:**
- `src/acp_client/infrastructure/events/bus.py:141` - 1 предупреждение
- `tests/test_infrastructure_plugins_manager.py` - 14 предупреждений
- `tests/test_tui_plan_panel_mvvm.py` - 2 предупреждения

**Решение:** Удалить неиспользуемые `# type: ignore` комментарии

---

### 2.4 Unresolved Attribute `.plain` (13 ошибок) - **СРЕДНИЙ ПРИОРИТЕТ**

**Статус:** Type checker не знает о методе `.plain` на типе `ConsoleRenderable`  
**Файлы:**
- `tests/test_tui_footer_and_tool_panel_mvvm.py` - 9 ошибок
- `tests/test_tui_header.py` - 7 ошибок

**Проблема:**
```python
rendered = footer_bar.render().plain  # ошибка: ConsoleRenderable имеет no attribute 'plain'
```

**Причина:** Возвращаемый тип `render()` - это union типов, и не все варианты имеют `.plain`

**Решение:** Кастировать результат или использовать правильный API

---

### 2.5 Observable Type Issues (5 ошибок) - **СРЕДНИЙ ПРИОРИТЕТ**

**Файл:** `src/acp_client/presentation/observable.py`

**Ошибки:**
1. Line 39: invalid-return-type - `T@value` vs `T@__init__`
2. Line 53: invalid-assignment - присваивание `T@value` к `T@__init__`
3. Line 72: invalid-argument-type - `append(observer)` с неверным типом
4. Line 73: invalid-argument-type - `remove(observer)` с неверным типом
5. Line 88: unresolved-attribute - `observer.__name__` для callable

**Причина:** Generic параметры T не синхронизированы между `__init__` и методами

**Решение:** Переопределить типы в Observable для правильной работы с generics

---

### 2.6 Infrastructure Issues (6 ошибок) - **СРЕДНИЙ ПРИОРИТЕТ**

**Детали:**

| Файл | Линия | Ошибка | Причина |
|------|-------|--------|---------|
| `session_coordinator.py` | 90 | unknown-argument | Logger не поддерживает kwargs host/port |
| `state_machine.py` | 223 | unresolved-attribute | `listener.__name__` для callback |
| `di_container.py` | 214 | call-top-callable | Unsafe call для callable |
| `plugins/base.py` | 14 | unresolved-import | Handler не экспортируется из handler_registry |
| `acp_transport_service.py` | 117 | invalid-method-override | Несовместимое переопределение listen() |
| `handlers.py` | 56 | unresolved-attribute | Доступ к tool_call_id у union типа |

---

### 2.7 TUI Components Issues (6 ошибок) - **СРЕДНИЙ ПРИОРИТЕТ**

**Детали:**

| Файл | Ошибка | Описание |
|------|--------|----------|
| `chat_view.py:140-141` | no-matching-overload | `dict.get("type", "unknown")` - type не совпадает |
| `file_tree.py:254` | invalid-method-override | `remove()` несовместим с Widget.remove() |
| `tool_panel.py:102` | missing-argument | TerminalOutputPanel без terminal_vm |

---

### 2.8 Import & Assignment Issues (3 ошибки) - **НИЗКИЙ ПРИОРИТЕТ**

| Файл | Ошибка | Решение |
|------|--------|---------|
| `base_view_model.py:18` | invalid-assignment | `DomainEvent = Any` требует явной аннотации |

---

## 3. Файлы с наибольшим количеством ошибок

```
test_infrastructure_events_bus.py      - 28 ошибок (invalid-argument-type subscribe)
test_infrastructure_plugins_manager.py - 16 предупреждений (unused type: ignore)
test_tui_footer_and_tool_panel_mvvm.py - 9 ошибок (.plain attribute)
test_tui_header.py                     - 7 ошибок (.plain attribute)
test_tui_file_tree.py                  - 5 ошибок (missing-argument)
presentation/observable.py             - 5 ошибок (generic type issues)
test_tui_permission_modal.py           - 3 ошибки (missing-argument)
test_tui_file_viewer.py                - 2 ошибки (missing-argument)
tui/app.py                             - 3 ошибки (missing-argument)
infrastructure/session_coordinator.py  - 2 ошибки (unknown-argument)
```

---

## 4. Приоритизация исправлений

### ФАЗА 1: КРИТИЧЕСКИЕ (Блокирующие) - 14 ошибок

**Срок:** НЕМЕДЛЕННО - влияют на работоспособность приложения

1. **Missing Arguments в компонентах (14 ошибок)**
   - Обновить `src/acp_client/tui/app.py` - передать ViewModels в модальные окна
   - Обновить тесты в `tests/` - передать ViewModels при создании компонентов
   - **Файлы для исправления:**
     - `src/acp_client/tui/app.py` - 3 места
     - `tests/test_tui_file_tree.py` - 5 мест
     - `tests/test_tui_file_viewer.py` - 2 места
     - `tests/test_tui_permission_modal.py` - 3 места
     - `src/acp_client/tui/components/tool_panel.py` - 1 место

---

### ФАЗА 2: ВЫСОКИЙ ПРИОРИТЕТ - 34 ошибки

**Срок:** Before merge - влияют на type safety

1. **EventHandler type signature (28 ошибок)**
   - Обновить `src/acp_client/infrastructure/events/bus.py`
   - Использовать `Callable[[DomainEvent], Any]` или Generic EventHandler
   - **Решение:** Переписать типизацию EventHandler для поддержки наследования типов

2. **Observable Generic Types (5 ошибок)**
   - Переписать `src/acp_client/presentation/observable.py`
   - Правильно использовать Generic[T] для callback функций
   - Исправить методы append/remove для `List[Callback[T]]`

3. **Missing Argument в view_model_factory (1 ошибка)**
   - Обновить `tests/test_di_container_integration.py:51`

---

### ФАЗА 3: СРЕДНИЙ ПРИОРИТЕТ - 35 ошибок

**Срок:** Before release - code quality improvements

1. **Unresolved Attribute `.plain` (13 ошибок)**
   - Обновить тесты в `tests/test_tui_*.py`
   - Правильно кастировать результат `render()` или использовать правильный API
   - Возможно использовать `str(rendered)` вместо `.plain`

2. **Infrastructure Issues (6 ошибок)**
   - Исправить типизацию Logger в `session_coordinator.py`
   - Исправить callback типы в `state_machine.py`
   - Экспортировать Handler из `handler_registry.py`
   - Правильно переопределить `listen()` в `acp_transport_service.py`

3. **Dict.get Overload Issues (2 ошибки)**
   - Обновить `chat_view.py:140-141`
   - Правильно типировать аргументы default для dict.get()

4. **Widget.remove Override (1 ошибка)**
   - Обновить сигнатуру в `file_tree.py:254`

5. **Unused type: ignore Comments (16 предупреждений)**
   - Удалить из:
     - `infrastructure/events/bus.py` - 1
     - `tests/test_infrastructure_plugins_manager.py` - 14
     - `tests/test_tui_plan_panel_mvvm.py` - 2

---

### ФАЗА 4: НИЗКИЙ ПРИОРИТЕТ - 7 ошибок

**Срок:** Next release - code quality polish

1. **Base ViewModel Assignment (1 ошибка)**
   - Добавить явную аннотацию в `base_view_model.py:18`

2. **Callable __name__ Access (2 ошибки)**
   - Использовать `getattr(listener, '__name__', '<unknown>')` в `state_machine.py`
   - Использовать `getattr(observer, '__name__', '<unknown>')` в `observable.py`

3. **DI Container call-top-callable (1 ошибка)**
   - Переписать логику в `di_container.py:214` с более специфичной типизацией

4. **Unresolved Import (1 ошибка)**
   - Экспортировать Handler из `handler_registry.py`

5. **Tool Call ID Access (1 ошибка)**
   - Обновить типизацию union в `handlers.py:56`

---

## 5. Рекомендации по подходу

### 5.1 Стратегия исправления

1. **Сначала исправить ФАЗУ 1** - это блокирует тестирование
   - Эти исправления небольшие и локализованные
   - Не требуют переписывания архитектуры

2. **Затем ФАЗУ 2** - улучшение type safety
   - EventHandler требует переработки типизации
   - Observable требует корректировки generics
   - Это более сложные изменения, требующие понимания design

3. **ФАЗЫ 3-4** - code quality
   - Большинство легких исправлений
   - Можно делать параллельно с другой работой

### 5.2 Порядок исправления внутри фазы

**ФАЗА 1 порядок:**
1. `test_tui_file_tree.py` - 5 ошибок (самая большая группа)
2. `acp-client/tui/app.py` - 3 критических компонента
3. `test_tui_file_viewer.py` - 2 ошибки
4. `test_tui_permission_modal.py` - 3 ошибки
5. `test_tui_footer_and_tool_panel_mvvm.py` - 1 ошибка в tool_panel.py

### 5.3 Инструменты и подход

```bash
# 1. Валидация после каждого исправления
uv run --directory acp-client ty check

# 2. Запуск тестов для ФАЗЫ 1
uv run --directory acp-client python -m pytest tests/test_tui_*.py

# 3. Проверка фиксов (если нужны)
uv run --directory acp-client ruff check .
```

### 5.4 Документирование изменений

- Каждое исправление должно иметь комментарий:
  ```python
  # Type checking fix: Pass required ViewModel parameter
  # See PHASE_4_PART9_TYPE_CHECKING_ANALYSIS.md
  ```

- Если нужны `# type: ignore`, то ТОЛЬКО с конкретным кодом ошибки:
  ```python
  # type: ignore[override]  # Liskov substitution principle exception
  ```

---

## 6. Метрики успеха

| Метрика | Целевое значение | Текущее | Статус |
|---------|-----------------|---------|--------|
| Всего диагностик | 0 | 90 | ❌ |
| Ошибки (errors) | 0 | 74 | ❌ |
| Предупреждения | 0 | 16 | ❌ |
| ФАЗА 1 исправлена | ✅ | ❌ | ⏳ |
| ФАЗА 2 исправлена | ✅ | ❌ | ⏳ |
| ФАЗА 3 исправлена | ✅ | ❌ | ⏳ |
| Тесты проходят | ✅ | ? | ? |

---

## 7. Дополнительные ресурсы

### Type Checker Reference
- [ty documentation](https://docs.astral.sh/ty/)
- Особенно полезны: Callable typing, Generic constraints, Union handling

### Связанные файлы в проекте
- `AGENTS.md` - правила проекта по типизации
- `acp-client/pyproject.toml` - конфигурация ty checker
- `acp-client/README.md` - документация по development

### Примеры исправлений

**Пример 1: Missing Argument Fix**
```python
# ДО (ошибка)
self.push_screen(TerminalLogModal(title=title))

# ПОСЛЕ (исправление)
self.push_screen(TerminalLogModal(
    terminal_log_vm=self.terminal_log_view_model,
    title=title
))
```

**Пример 2: Type Ignore Cleanup**
```python
# ДО (неиспользуемый type: ignore)
result = some_call()  # type: ignore

# ПОСЛЕ (удалено)
result = some_call()
```

**Пример 3: Union Type Handling**
```python
# ДО (ошибка - no attribute on union)
tool_call_id = update.tool_call_id  # union не имеет атрибута

# ПОСЛЕ (правильно)
if isinstance(update, ToolCallCreatedUpdate):
    tool_call_id = update.tool_call_id
elif isinstance(update, ToolCallStateUpdate):
    tool_call_id = update.tool_call_id
```

---

## 8. История анализа

| Дата | Версия | Статус |
|------|--------|--------|
| 2026-04-09 | 1.0 | Начальный анализ завершен |

---

**Подготовлено:** Roo (AI Engineer)  
**Для:** Phase 4.9 - Type Checking Error Resolution  
**Статус:** ✅ Анализ завершен, готов к исправлению
