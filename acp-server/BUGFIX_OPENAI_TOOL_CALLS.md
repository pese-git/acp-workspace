# Исправление ошибки формирования истории сообщений для OpenAI API

## Проблема

При использовании OpenAI API через Azure возникала ошибка:

```
openai.BadRequestError: Error code: 400 - {'error': {'message': 'Provider returned error', 'code': 400, 'metadata': {'raw': '{\n  "error": {\n    "message": "Invalid parameter: messages with role \'tool\' must be a response to a preceeding message with \'tool_calls\'.",\n    "type": "invalid_request_error",\n    "param": "messages.[3].role",\n    "code": null\n  }\n}', 'provider_name': 'Azure', 'is_byok': False}}}
```

## Корневая причина

OpenAI API требует, чтобы:
1. Сообщения с ролью `tool` всегда следовали после сообщения `assistant` с полем `tool_calls`
2. Каждое `tool` сообщение содержало `tool_call_id`, соответствующий ID из `tool_calls`

Текущая реализация имела следующие проблемы:

1. **`LLMMessage` не поддерживал tool_calls и tool_call_id**
   - Структура содержала только `role` и `content`
   - Не хранила информацию о `tool_calls` (для assistant) и `tool_call_id` (для tool)

2. **Преобразование в OpenAI формат теряло информацию**
   - В `openai_provider.py:97` сообщения преобразовывались как `{"role": msg.role, "content": msg.content}`
   - Терялась информация о `tool_calls` и `tool_call_id`

3. **Неправильное добавление сообщений в naive.py**
   - Assistant message добавлялся без `tool_calls`
   - Tool messages добавлялись без `tool_call_id`

## Решение

### 1. Расширение структуры LLMMessage

**Файл:** `acp-server/src/acp_server/llm/base.py`

Добавлены опциональные поля для поддержки OpenAI формата:

```python
@dataclass
class LLMMessage:
    """Сообщение для LLM."""
    role: str  # "system", "user", "assistant", "tool"
    content: str | None = None
    tool_calls: list["LLMToolCall"] | None = None  # Для assistant messages
    tool_call_id: str | None = None  # Для tool messages
    name: str | None = None  # Для tool messages
```

### 2. Правильное преобразование в OpenAI формат

**Файл:** `acp-server/src/acp_server/llm/openai_provider.py`

Добавлен метод `_convert_to_openai_format()`, который:
- Преобразует `LLMMessage` в формат OpenAI API
- Сохраняет `tool_calls` для assistant messages
- Сохраняет `tool_call_id` и `name` для tool messages

### 3. Валидация истории сообщений

**Файл:** `acp-server/src/acp_server/llm/openai_provider.py`

Добавлен метод `_validate_message_history()`, который проверяет:
- Tool messages имеют `tool_call_id`
- Tool messages следуют после assistant messages с `tool_calls`

Валидация вызывается перед отправкой запроса в OpenAI API.

### 4. Исправление логики в NaiveAgent

**Файл:** `acp-server/src/acp_server/agent/naive.py`

Обновлено добавление сообщений:

```python
# Assistant message с tool_calls
messages.append(
    LLMMessage(
        role="assistant",
        content=response.text,
        tool_calls=response.tool_calls,  # ДОБАВЛЕНО
    )
)

# Tool message с tool_call_id
messages.append(
    LLMMessage(
        role="tool",
        content=tool_result_text,
        tool_call_id=tool_call.id,  # ДОБАВЛЕНО
        name=tool_call.name,  # ДОБАВЛЕНО
    )
)
```

## Тестирование

Добавлен новый файл с тестами: `acp-server/tests/test_openai_message_history.py`

Тесты покрывают:
- Преобразование простых сообщений
- Преобразование assistant messages с tool_calls
- Преобразование tool messages с tool_call_id
- Валидацию корректной истории
- Валидацию некорректных сценариев (tool без tool_call_id, tool без предшествующего assistant)
- Полный цикл conversation с tool calls

Все тесты проходят успешно:
```bash
cd acp-server && uv run python -m pytest tests/test_openai_message_history.py -v
# 9 passed in 0.31s
```

## Совместимость

Изменения обратно совместимы:
- Все новые поля в `LLMMessage` опциональные
- Существующий код продолжает работать без изменений
- Все существующие тесты для LLM провайдера и агентов проходят успешно

## Файлы изменены

1. `acp-server/src/acp_server/llm/base.py` - расширена структура `LLMMessage`
2. `acp-server/src/acp_server/llm/openai_provider.py` - добавлены методы преобразования и валидации
3. `acp-server/src/acp_server/agent/naive.py` - исправлена логика добавления сообщений
4. `acp-server/tests/test_openai_message_history.py` - новые тесты (создан)

## Результат

После исправления:
- История сообщений формируется согласно требованиям OpenAI API
- Tool messages всегда следуют после assistant messages с tool_calls
- Каждое tool message содержит корректный tool_call_id
- Добавлена валидация перед отправкой в API для раннего обнаружения проблем
- Все тесты проходят успешно
