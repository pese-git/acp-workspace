# План рефакторинга архитектуры обработчиков ACP Protocol

## Статус

**Текущее состояние:** Фаза 6 (интеграция AgentOrchestrator) завершена ✅

**Следующий рефакторинг:** Опционально (см. критерии ниже)

**Автор:** Sergey (2026-04-10)

---

## 1. Обоснование

Этот документ описывает план полного рефакторинга архитектуры обработчиков ACP Protocol на Strategy Pattern.

### 1.1 Текущая архитектура (функциональный подход)

**Преимущества:**
- ✅ Простота реализации
- ✅ Минимальный overhead
- ✅ Хорошая модульность на уровне файлов

**Проблемы:**
- ❌ `core.py::handle()` содержит 14 if-elif веток (CC ≈ 15-17)
- ❌ `prompt.py` содержит 1909 строк кода (слишком большой файл)
- ❌ Сложно расширять: нужно изменять core.py для каждого нового метода
- ❌ Линейный поиск метода: O(n) вместо O(1)

### 1.2 Целевая архитектура (Strategy Pattern)

**Преимущества:**
- ✅ Каждый handler - отдельный класс (Single Responsibility)
- ✅ Динамическая регистрация через registry (Open/Closed Principle)
- ✅ Dependency Injection через HandlerContext
- ✅ Легче тестировать handlers изолированно
- ✅ Расширяемость: добавлять новые методы без изменения core.py

**Недостатки:**
- ❌ Увеличение кода (~5-10% overhead)
- ❌ Риск регрессии при миграции
- ❌ Требует значительного рефакторинга (~11-13 дней)

---

## 2. Метрики текущего кода

### 2.1 Cyclomatic Complexity

| Функция | CC | Статус |
|---------|----|----|
| `core.py::handle()` | 15-17 | 🟡 На границе |
| `prompt.py::session_prompt()` | 30-35 | 🔴 КРИТИЧНО |
| `session.py::*` | 8-12 | ✅ Приемлемо |

**Норма:** CC < 15 (рекомендуется)

### 2.2 Maintainability Index

| Модуль | MI | Статус |
|--------|----|----|
| `core.py` | 55-65 | 🟡 Средняя |
| `prompt.py` | 20-35 | 🔴 Низкая |
| `session.py` | 65-75 | ✅ Хорошая |

**Шкала:** 85-100 (отлично), 65-85 (хорошо), 40-65 (средне), 20-40 (плохо)

### 2.3 Размер файлов

| Файл | Строк | Статус |
|------|-------|--------|
| `core.py` | 468 | ✅ Приемлемо |
| `prompt.py` | 2062 | 🔴 СЛИШКОМ МНОГО |
| `session.py` | 483 | ✅ Приемлемо |

---

## 3. Критерии решения о рефакторинге

### 3.1 ДЕЛАТЬ рефакторинг если:

✅ Планируется 10+ новых методов в ближайшие 6 месяцев
✅ Нужна система плагинов с динамической регистрацией
✅ Метрики показывают CC > 20 или MI < 50
✅ Команда единогласно поддерживает
✅ Есть 3+ недели без критических задач

### 3.2 НЕ делать рефакторинг если:

❌ Текущий код работает стабильно
❌ Нет конкретных проблем с расширяемостью
❌ Команда маленькая (1-2 разработчика)
❌ Есть более приоритетные задачи
❌ Нет ресурсов на тестирование и rollback

---

## 4. Стратегия рефакторинга: Двухэтапный подход

### 4.1 Этап 1: Интеграция AgentOrchestrator (✅ ЗАВЕРШЕНО)

**Цель:** Быстро доставить функциональность

**Подход:** Минимальные изменения в существующем коде

**Результаты:**
- ✅ Добавлен параметр `agent_orchestrator` в `ACPProtocol`
- ✅ Создана функция `_handle_with_agent()`
- ✅ Сохранена полная обратная совместимость
- ✅ Время: 1.5 часа

### 4.2 Этап 2: Архитектурный рефакторинг (ОПЦИОНАЛЬНО)

**Цель:** Переход на production-ready архитектуру

**Рекомендуемое время:** 7-12 дней

**Этапы:**

#### Фаза 2.1: Проектирование (2 дня)

**День 1: Дизайн интерфейсов**

Создать документ `doc/HANDLER_ARCHITECTURE.md` с описанием:

```python
# Базовый класс для всех handlers
class MethodHandler(ABC):
    @property
    @abstractmethod
    def method_name(self) -> str:
        """Имя метода протокола (например, "session/prompt")"""
        pass
    
    @abstractmethod
    async def handle(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        context: HandlerContext,
    ) -> ProtocolOutcome:
        """Обработать запрос и вернуть результат"""
        pass

# Контекст для handlers (Dependency Injection)
@dataclass
class HandlerContext:
    sessions: dict[str, SessionState]
    config_specs: dict[str, dict[str, Any]]
    require_auth: bool
    authenticated: bool
    runtime_capabilities: ClientRuntimeCapabilities | None
    storage: SessionStorage
    agent_orchestrator: AgentOrchestrator | None = None

# Реестр handlers
class HandlerRegistry:
    def register(self, handler: MethodHandler) -> None: ...
    def get(self, method: str) -> MethodHandler | None: ...
    def has(self, method: str) -> bool: ...
    def list_methods(self) -> list[str]: ...
```

**День 2: Code review**

- Провести code review дизайна с командой
- Согласовать naming conventions
- Определить breaking changes

#### Фаза 2.2: Инфраструктура (2-3 дня)

**Создать новые файлы:**

1. `acp-server/src/acp_server/protocol/handlers/base.py`
   - `MethodHandler` (ABC)
   - `HandlerContext` (dataclass)

2. `acp-server/src/acp_server/protocol/handler_registry.py`
   - `HandlerRegistry`

**Написать тесты:**

```python
def test_register_handler():
    registry = HandlerRegistry()
    handler = MockHandler("test/method")
    registry.register(handler)
    assert registry.has("test/method")

def test_get_handler():
    registry = HandlerRegistry()
    handler = MockHandler("test/method")
    registry.register(handler)
    assert registry.get("test/method") == handler

def test_duplicate_registration_fails():
    registry = HandlerRegistry()
    handler1 = MockHandler("test/method")
    handler2 = MockHandler("test/method")
    registry.register(handler1)
    with pytest.raises(ValueError):
        registry.register(handler2)
```

#### Фаза 2.3: Миграция handlers (3-4 дня)

**День 1: Мигрировать session/prompt**

```python
# Создать: acp-server/src/acp_server/protocol/handlers/prompt_handler.py

class SessionPromptHandler(MethodHandler):
    @property
    def method_name(self) -> str:
        return "session/prompt"
    
    async def handle(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        context: HandlerContext,
    ) -> ProtocolOutcome:
        # Полная логика из session_prompt()
        session_id = params.get("sessionId")
        if context.agent_orchestrator is not None:
            # Обработать через агента
            ...
        else:
            # Legacy логика директив
            ...
```

**День 2: Мигрировать session/* методы**

```python
class SessionNewHandler(MethodHandler):
    method_name = "session/new"
    async def handle(...): ...

class SessionLoadHandler(MethodHandler):
    method_name = "session/load"
    async def handle(...): ...

class SessionListHandler(MethodHandler):
    method_name = "session/list"
    async def handle(...): ...
```

**День 3-4: Мигрировать остальные методы**

- config/* handlers
- legacy handlers (ping, echo, shutdown)
- Специальные методы (initialize, authenticate)

#### Фаза 2.4: Обновление ACPProtocol (1 день)

**Модифицировать `core.py`:**

```python
class ACPProtocol:
    def __init__(self, ..., agent_orchestrator: AgentOrchestrator | None = None):
        self._registry = HandlerRegistry()
        self._register_handlers()
        self._context = HandlerContext(...)
    
    def _register_handlers(self) -> None:
        """Регистрирует все handlers в реестре"""
        self._registry.register(SessionPromptHandler())
        self._registry.register(SessionNewHandler())
        self._registry.register(SessionLoadHandler())
        # ... остальные handlers
    
    async def handle(self, message: ACPMessage) -> ProtocolOutcome:
        """Обрабатывает сообщение через registry"""
        method = message.method
        
        # Специальные методы (до registry)
        if method == "initialize":
            return self._handle_initialize(...)
        if method == "authenticate":
            return self._handle_authenticate(...)
        
        # Поиск в registry
        handler = self._registry.get(method)
        if handler:
            return await handler.handle(message.id, params, self._context)
        
        # Метод не найден
        return ProtocolOutcome(response=error_response(...))
```

#### Фаза 2.5: Тестирование (2 дня)

**Unit-тесты для registry:**
```bash
tests/test_handler_registry.py (10+ тестов)
```

**Интеграционные тесты:**
```bash
tests/test_protocol_with_handlers.py (20+ тестов)
```

**Проверить существующие тесты:**
```bash
make check
pytest tests/test_protocol.py (все 64 теста должны пройти)
```

#### Фаза 2.6: Документация (1 день)

1. Создать `doc/HANDLER_ARCHITECTURE.md`
   - Описание новой архитектуры
   - Примеры использования
   - Диаграммы

2. Создать `doc/HANDLER_MIGRATION_GUIDE.md`
   - Для разработчиков
   - Было vs Стало
   - FAQ

3. Обновить `ARCHITECTURE.md`
   - Переход на новую архитектуру
   - Удалить старые схемы

4. Обновить `README.md`
   - Примеры использования

---

## 5. Детальный план действий

### 5.1 Для Фазы 6 (✅ ЗАВЕРШЕНО)

```bash
# Уже сделано:
1. ✅ Добавить параметр agent_orchestrator в ACPProtocol.__init__()
2. ✅ Передать в session_prompt() handler
3. ✅ Создать _handle_with_agent()
4. ✅ Написать тесты
5. ✅ Запустить make check
6. ✅ Создать коммит
```

### 5.2 Для Фазы 7 (Оценка, 3-5 дней)

```bash
# Перед рефакторингом провести анализ:
1. [ ] Измерить CC: radon cc acp-server/src/acp_server/protocol/ -a
2. [ ] Измерить MI: radon mi acp-server/src/acp_server/protocol/
3. [ ] Профилировать: python -m cProfile
4. [ ] Обсудить с командой: есть ли реальные проблемы?
5. [ ] Собрать feedback разработчиков
```

### 5.3 Для Фазы 8 (Рефакторинг, 7-12 дней)

**Только если Фаза 7 показала необходимость!**

```bash
# Создать ветку
git checkout -b feature/handler-architecture

# Фаза 2.1: Проектирование (2 дня)
# Фаза 2.2: Инфраструктура (2-3 дня)
# Фаза 2.3: Миграция (3-4 дня)
# Фаза 2.4: Обновление ACPProtocol (1 день)
# Фаза 2.5: Тестирование (2 дня)
# Фаза 2.6: Документация (1 день)

# Финал
git push origin feature/handler-architecture
# Code review
# Merge в develop
```

---

## 6. Альтернативный подход: Гибридный (5-7 дней)

Если полный рефакторинг кажется слишком дорогим, использовать промежуточный подход:

### 6.1 Registry без классов (вариант A)

```python
# handler_registry.py
class HandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}
    
    def register(self, method: str, handler: Callable):
        self._handlers[method] = handler
    
    def get(self, method: str) -> Callable | None:
        return self._handlers.get(method)

# core.py
class ACPProtocol:
    def __init__(self, ...):
        self._registry = HandlerRegistry()
        self._register_handlers()
    
    def _register_handlers(self):
        # Регистрация существующих функций
        self._registry.register("session/prompt", prompt.session_prompt)
        self._registry.register("session/new", session.session_new)
        # ...
    
    async def handle(self, message: ACPMessage):
        handler = self._registry.get(message.method)
        if handler:
            return await handler(message.id, params, ...)
```

**Преимущества:**
- ✅ Убирает if-elif диспетчинг
- ✅ Сохраняет существующие функции
- ✅ Минимальные изменения
- ✅ Легко расширять

**Недостатки:**
- ❌ Не решает проблему больших файлов (prompt.py 2062 строк)
- ❌ Handlers остаются функциями (сложнее тестировать)

### 6.2 Постепенная миграция (вариант B)

```python
# Только НОВЫЕ handlers делать классами
class NewFeatureHandler(MethodHandler):
    method_name = "new/feature"
    async def handle(...): ...

# Старые handlers оставить функциями
def session_prompt(...): ...  # legacy

# Registry поддерживает оба типа
registry.register_function("session/prompt", prompt.session_prompt)
registry.register_handler(NewFeatureHandler())
```

**Преимущества:**
- ✅ Постепенный переход
- ✅ Низкий риск
- ✅ Можно распределить по спринтам

**Недостатки:**
- ❌ Оставляет технический долг
- ❌ Смешанные подходы (сложнее поддерживать)

---

## 7. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Breaking changes | Средняя | Высокое | Сохранить обратную совместимость |
| Регрессия тестов | Низкая | Высокое | Запускать тесты после каждого шага |
| Увеличение сложности | Высокая | Среднее | Хорошая документация + примеры |
| Задержка timeline | Средняя | Среднее | Буфер 2-3 дня в плане |
| Проблемы с производительностью | Низкая | Среднее | Профилировать до/после |

**Rollback стратегия:**

```bash
# Если рефакторинг провалился
git tag v1.0-pre-refactor
git revert --no-edit <commit-hash>

# Feature flag для постепенного rollout
USE_HANDLER_REGISTRY = os.getenv("ACP_USE_REGISTRY", "false") == "true"
if USE_HANDLER_REGISTRY:
    handler = registry.get(method)
else:
    # legacy if-elif
```

---

## 8. Критерии успеха

### 8.1 Технические

- [ ] Все существующие тесты проходят (64/64)
- [ ] Новые тесты покрывают 90%+ кода handlers
- [ ] mypy проверка проходит без ошибок
- [ ] ruff проверка проходит
- [ ] Производительность не ухудшилась > 10%

### 8.2 Архитектурные

- [ ] Все handlers реализуют `MethodHandler`
- [ ] Зависимости передаются через `HandlerContext`
- [ ] Registry используется для всех методов
- [ ] Нет if-elif диспетчинга в `core.py`
- [ ] Новые методы добавляются за < 30 минут

### 8.3 Документация

- [ ] Обновлены архитектурные документы
- [ ] Создан migration guide
- [ ] Обновлены примеры в README
- [ ] Добавлены диаграммы архитектуры

---

## 9. Примеры кода

### 9.1 Пример: Создание нового handler

```python
# handlers/custom_handler.py
class MyCustomHandler(MethodHandler):
    """Обработчик пользовательского метода."""
    
    @property
    def method_name(self) -> str:
        return "custom/method"
    
    def validate_params(self, request_id, params):
        """Валидировать параметры"""
        if not isinstance(params.get("required_field"), str):
            return ACPMessage.error_response(
                request_id,
                code=-32602,
                message="required_field is required"
            )
        return None
    
    async def handle(self, request_id, params, context):
        """Обработать запрос"""
        # Валидация
        error = self.validate_params(request_id, params)
        if error:
            return ProtocolOutcome(response=error)
        
        # Логика обработки
        result = await self._process(params, context)
        
        # Ответ
        return ProtocolOutcome(
            response=ACPMessage.response(request_id, result),
            notifications=[]
        )
    
    async def _process(self, params, context):
        """Вспомогательный метод для обработки"""
        return {"status": "ok"}

# core.py
def _register_handlers(self):
    self._registry.register(MyCustomHandler())
```

### 9.2 Пример: Использование в тестах

```python
@pytest.mark.asyncio
async def test_my_custom_handler():
    """Тест изолированного handler."""
    handler = MyCustomHandler()
    context = HandlerContext(
        sessions={},
        config_specs={},
        require_auth=False,
        authenticated=True,
        runtime_capabilities=None,
        storage=InMemoryStorage(),
        agent_orchestrator=None,
    )
    
    outcome = await handler.handle(
        request_id="req_1",
        params={"required_field": "value"},
        context=context,
    )
    
    assert outcome.response is not None
    assert outcome.response.error is None
    assert outcome.response.result["status"] == "ok"
```

---

## 10. Рекомендации

### 10.1 СЕЙЧАС (Фаза 6) ✅

**Состояние:** Интеграция AgentOrchestrator завершена

- ✅ Основная функциональность работает
- ✅ Все тесты проходят
- ✅ Обратная совместимость сохранена
- ✅ Готово к production

### 10.2 ЧЕРЕЗ МЕСЯЦ (Фаза 7)

**Рекомендуется:** Провести анализ метрик

```bash
# Измерить сложность кода
radon cc acp-server/src/acp_server/protocol/ -a
radon mi acp-server/src/acp_server/protocol/

# Профилировать производительность
python -m cProfile -o stats.prof ...
```

**Обсудить с командой:**
- Есть ли реальные проблемы с кодом?
- Планируется ли 10+ новых методов?
- Есть ли ресурсы на рефакторинг?

### 10.3 ЕСЛИ РЕФАКТОРИНГ НУЖЕН (Фаза 8)

**Выбрать подход:**

1. **Полный рефакторинг** (7-12 дней)
   - Для долгосрочных проектов (5+ лет)
   - Если много новых методов в планах

2. **Гибридный подход** (5-7 дней)
   - Registry + постепенная миграция
   - Низкий риск, среднюю выгоду

3. **Рефакторинг prompt.py** (5-7 дней)
   - Разбить на подмодули
   - Решить основную проблему (CC > 30)

### 10.4 НЕ ДЕЛАТЬ рефакторинг если:

❌ Текущий код работает стабильно
❌ Нет конкретных проблем в метриках
❌ Команда маленькая (1-2 разработчика)
❌ Есть более приоритетные задачи
❌ Нет ресурсов на тестирование

---

## 11. Ссылки и документация

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Общая архитектура проекта
- [`NAIVE_AGENT_ARCHITECTURE.md`](NAIVE_AGENT_ARCHITECTURE.md) - Архитектура LLM-агента
- [`acp-server/README.md`](acp-server/README.md) - README сервера
- [`AGENTS.md`](AGENTS.md) - Правила для агентов

---

## 12. История версий

| Версия | Дата | Статус | Описание |
|--------|------|--------|---------|
| 1.0 | 2026-04-10 | 📝 DRAFT | Первоначальный план |

---

**Последнее обновление:** 2026-04-10

**Статус документа:** Рекомендуемый план для возможного рефакторинга архитектуры ACP Protocol
