# Сравнение архитектур для управления Tool Execution

## Обзор проблемы

Текущая реализация NaiveAgent выполняет tool calls внутри себя, минуя permission flow в PromptOrchestrator. Нужно выбрать оптимальное архитектурное решение.

---

## Сравнительная таблица

| Критерий | Вариант A | Вариант B | Вариант C | Вариант D |
|----------|-----------|-----------|-----------|-----------|
| **Архитектурная чистота** | ✅ Отличная | ✅ Хорошая | ✅ Отличная | ❌ Плохая |
| **Breaking changes** | ⚠️ Есть | ❌ Нет | ❌ Нет | ❌ Нет |
| **Code duplication** | ✅ Нет | ✅ Нет | ⚠️ Есть | ✅ Нет |
| **Complexity** | ✅ Простая | ⚠️ Средняя | ⚠️ Средняя | ⚠️ Средняя |
| **Testability** | ✅ Легко | ✅ Легко | ✅ Легко | ⚠️ Сложно |
| **Maintainability** | ✅ Отличная | ✅ Хорошая | ⚠️ Худшая | ⚠️ Хорошая |
| **Performance** | ✅ Нет overhead | ✅ Нет overhead | ⚠️ +1 наследование | ✅ Нет overhead |
| **Compliance к архитектуре** | ✅ 100% | ✅ 95% | ✅ 100% | ❌ 30% |

---

## Детальное описание вариантов

### Вариант A (Рекомендуемый) - Clean Architecture

**Описание**: NaiveAgent возвращает tool_calls БЕЗ выполнения, PromptOrchestrator управляет всем decision flow.

**Изменения**:
```python
# naive.py - НОВОЕ ПОВЕДЕНИЕ
if response.tool_calls:
    return AgentResponse(
        text=response.text,
        tool_calls=response.tool_calls,  # Вернуть как есть!
        stop_reason=response.stop_reason,
    )
```

**Плюсы**:
- ✅ **Архитектурная чистота**: Agent = простой LLM interface, PromptOrchestrator = decision logic
- ✅ **Separation of concerns**: Каждый компонент отвечает за одно
- ✅ **Соответствует SERVER_PERMISSION_INTEGRATION_ARCHITECTURE.md**: 100% compliance
- ✅ **Простота reasoning**: "Где выполняются tools?" → "В PromptOrchestrator"
- ✅ **Scalability**: Если захотим новую логику (logging, monitoring, retry) - добавляем в PromptOrchestrator

**Минусы**:
- ⚠️ **Breaking change**: Существующая логика, которая ожидает пустой tool_calls список, может сломаться
- ⚠️ **Требует обновления тестов**: Tests, которые проверяют NaiveAgent поведение, нужно переписать

**Scope изменений**:
- 1 файл: `naive.py` (~50 строк изменений)
- Обновить 2-3 теста для NaiveAgent
- Убедиться что PromptOrchestrator полностью готов (уже готов!)

**Риск**: Низкий (PromptOrchestrator уже имеет _process_tool_calls реализованный)

---

### Вариант B - Conditional Execution

**Описание**: Добавить флаг `auto_execute_tools` в NaiveAgent для контроля поведения.

**Изменения**:
```python
class NaiveAgent(LLMAgent):
    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        max_iterations: int = 5,
        auto_execute_tools: bool = True,  # НОВЫЙ ФЛАГ
    ):
        self.auto_execute_tools = auto_execute_tools

    if response.tool_calls:
        if self.auto_execute_tools:
            # СТАРОЕ ПОВЕДЕНИЕ - выполнять tools
            for tool_call in response.tool_calls:
                result = await self.tools.execute_tool(...)
                messages.append(LLMMessage(role="tool", ...))
        else:
            # НОВОЕ ПОВЕДЕНИЕ - вернуть для PromptOrchestrator
            return AgentResponse(
                text=response.text,
                tool_calls=response.tool_calls,
                stop_reason=response.stop_reason,
            )
```

**Плюсы**:
- ✅ **Backward compatible**: Старый код продолжает работать (auto_execute_tools=True по умолчанию)
- ✅ **Постепенная миграция**: Можно переключить флаг когда готово
- ✅ **Flexibility**: Позволяет обоим поведениям сосуществовать

**Минусы**:
- ⚠️ **Conditional logic**: Код содержит if/else что усложняет понимание
- ⚠️ **Несогласованность**: Поведение зависит от флага, а не от архитектуры
- ❌ **Dead code problem**: Старая логика остается в codebase, нужно поддерживать обе ветки
- ⚠️ **Тестирование**: Нужны тесты для обоих путей

**Scope изменений**:
- 1 файл: `naive.py` (~80 строк изменений с условной логикой)
- Обновить 4-6 тестов (для обоих путей)

**Риск**: Средний (две версии логики требуют более внимательного тестирования)

---

### Вариант C - New Agent Class

**Описание**: Создать новый `PermissionAwareAgent` который наследует `NaiveAgent` и переопределяет поведение.

**Изменения**:
```python
class PermissionAwareAgent(NaiveAgent):
    """Агент который возвращает tool_calls без выполнения."""
    
    async def process_prompt(self, context: AgentContext) -> AgentResponse:
        # Вызвать родительский метод до point где выполняются tools
        # Переопределить поведение на возврат tool_calls
        ...

# В ACPProtocol:
agent = PermissionAwareAgent(llm, tools, max_iterations=5)
```

**Плюсы**:
- ✅ **Не трогаем NaiveAgent**: Старый код остается неизменным
- ✅ **OOP правила**: Наследование и переопределение методов
- ✅ **Архитектурно чистый**: Новый агент имеет четкую ответственность
- ✅ **Backward compatible**: Можно использовать оба агента параллельно

**Минусы**:
- ⚠️ **Code duplication**: Часть логики дублируется из NaiveAgent
- ⚠️ **Maintainability nightmare**: Если изменим NaiveAgent, нужно следить за PermissionAwareAgent
- ⚠️ **Confusion**: Два агента с почти идентичным кодом, почему?
- ❌ **Усложнение**: Двойная иерархия классов требует больше внимания при изменениях

**Scope изменений**:
- Создать новый файл: `acp-server/src/acp_server/agent/permission_aware.py` (~150 строк)
- Обновить ACPProtocol инициализацию
- Обновить 2-3 теста

**Риск**: Высокий (code duplication приводит к проблемам при maintenance)

---

### Вариант D - Permissions in NaiveAgent

**Описание**: Оставить NaiveAgent как есть, но добавить permission checks перед выполнением tools.

**Изменения**:
```python
for idx, tool_call in enumerate(response.tool_calls):
    # НОВОЕ: Проверка разрешений перед выполнением
    decision = await self._check_permission(tool_call.name)
    
    if decision != "allow":
        logger.debug("Tool execution rejected by permission check")
        continue  # Пропустить этот tool
    
    # СТАРОЕ: Выполнить инструмент
    result = await self.tools.execute_tool(...)
```

**Плюсы**:
- ✅ **Минимальные изменения**: Добавить ~20 строк в NaiveAgent
- ✅ **Backward compatible**: Логика остается той же

**Минусы**:
- ❌ **Нарушение архитектуры**: Agent получает business logic, которая должна быть в PromptOrchestrator
- ❌ **Проблема с notification/messaging**: Agent не может отправлять session/request_permission (он не знает про session/update)
- ❌ **Асинхронность**: Agent выполняет tools и одновременно ждет permission - очень сложно
- ❌ **Несовместимость с protocol**: ACP spec требует чтобы permission requests были notifications, а не blocking calls
- ⚠️ **Testability nightmare**: Трудно тестировать permission flow внутри agent loop

**Scope изменений**:
- 1 файл: `naive.py` (~100 строк)
- Требует рефакторинга tool execution loop
- Много новых тестов для permission logic

**Риск**: ОЧЕНЬ ВЫСОКИЙ (архитектурно неправильно, не может правильно реализовать асинхронный permission flow)

---

## Рекомендация

### Выбираем Вариант A (Clean Architecture)

**Причины**:

1. **Архитектурная чистота** - Соответствует SERVER_PERMISSION_INTEGRATION_ARCHITECTURE.md 100%
2. **Минимальные изменения** - Всего ~50 строк в одном файле
3. **Ясная логика** - Каждый компонент знает свою роль
4. **Future-proof** - Если понадобится новая логика (retry, logging, async), легко добавляется в PromptOrchestrator
5. **Test coverage** - Легче тестировать permission flow отдельно от agent loop
6. **PromptOrchestrator готов** - Весь permission flow уже реализован и протестирован

**Breaking changes - МИНИМАЛЬНЫ**:
- Нет существующих test suite'ов которые зависят от NaiveAgent выполняющего tools
- ACPProtocol уже вызывает _process_tool_calls() после agent_response
- Все необходимые компоненты готовы

**План реализации**:
1. Изменить NaiveAgent.process_prompt() - вернуть tool_calls без выполнения
2. Добавить логирование в _process_tool_calls() для отладки
3. Исправить формат response клиента (success field в file_system_handler.py)
4. Протестировать end-to-end flow
5. Запустить make check

---

## Итоговая оценка

```
Вариант A: ████████████ 95/100 (Выбираем это!)
Вариант B: ██████████░░ 75/100 (Backup option)
Вариант C: ████████░░░░ 60/100 (Avoid if possible)
Вариант D: ██░░░░░░░░░░ 15/100 (Don't use)
```
