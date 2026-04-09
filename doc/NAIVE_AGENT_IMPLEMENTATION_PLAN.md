# План реализации наивного LLM-агента для ACP Server

**Документ:** NAIVE_AGENT_IMPLEMENTATION_PLAN.md  
**Версия:** 1.0  
**Статус:** Планирование  
**Дата:** 2026-04-09

---

## Оглавление

1. [Обзор плана](#обзор-плана)
2. [Фазы реализации](#фазы-реализации)
3. [Детализация кода](#детализация-кода)
4. [План тестирования](#план-тестирования)
5. [Миграционная стратегия](#миграционная-стратегия)
6. [Чеклист для разработчика](#чеклист-для-разработчика)
7. [Возможные проблемы и решения](#возможные-проблемы-и-решения)
8. [Метрики успеха](#метрики-успеха)

---

## Обзор плана

### Общая стратегия

Реализация выполняется в **8 логических фаз**, каждая из которых:
- **Тестируемая** - имеет набор unit/integration тестов
- **Проверяемая** - проходит `make check` без ошибок
- **Совместимая** - сохраняет обратную совместимость
- **Минимальная** - вносит минимум изменений в существующий код
- **Завершённая** - имеет четкие критерии приемки

### Общие принципы

1. **Зависимости** добавляются через `uv add` в корне с флагом `--directory acp-server`
2. **Структура** следует архитектуре из `doc/NAIVE_AGENT_ARCHITECTURE.md`
3. **Проверка** - всегда `make check` после завершения фазы
4. **Комментарии** - все функции и классы должны быть задокументированы
5. **Экспорты** - публичные классы экспортируются в `__init__.py`

---

## Фазы реализации

### Фаза 0: Подготовка (зависимости, структура)

#### Цель фазы

Подготовить проект к реализации:
- Добавить необходимые зависимости
- Создать структуру папок и файлов
- Настроить конфигурацию для новых модулей

#### Зависимости для добавления

| Библиотека | Версия | Назначение |
|-----------|--------|-----------|
| `openai` | `>=1.50.0` | OpenAI API клиент |
| `pydantic` | `>=2.11.0` | (уже есть) Валидация конфигурации |
| `python-dotenv` | `>=1.0.0` | Загрузка переменных окружения |

**Команды:**

```bash
# Из корня репозитория
uv add openai>=1.50.0 --directory acp-server
uv add python-dotenv>=1.0.0 --directory acp-server
```

#### Файлы для создания

```
acp-server/src/acp_server/
├── agent/
│   ├── __init__.py                    # Экспорт: LLMAgent, NaiveAgent, AgentOrchestrator, AgentContext, AgentResponse
│   ├── base.py                        # Интерфейсы ABC: LLMAgent
│   ├── state.py                       # Dataclasses: AgentContext, AgentResponse, OrchestratorConfig
│   ├── naive_agent.py                 # Реализация: NaiveAgent
│   ├── orchestrator.py                # Реализация: AgentOrchestrator
│   └── config.py                      # Конфигурация из переменных окружения
├── llm/
│   ├── __init__.py                    # Экспорт: LLMProvider, LLMMessage, LLMResponse, LLMToolCall
│   ├── base.py                        # Интерфейсы ABC: LLMProvider
│   ├── openai_provider.py             # Реализация: OpenAIProvider
│   └── mock_provider.py               # Реализация: MockLLMProvider (для тестов)
└── tools/
    ├── __init__.py                    # Экспорт: ToolRegistry, ToolDefinition, ToolExecutionResult
    ├── base.py                        # Интерфейсы ABC: ToolRegistry, ToolExecutor
    ├── registry.py                    # Реализация: SimpleToolRegistry
    ├── executor.py                    # Вспомогательные функции для выполнения
    └── builtin_tools.py               # Встроенные ACP инструменты
```

#### Файлы для модификации

| Файл | Изменения | Причина |
|------|-----------|---------|
| `acp-server/pyproject.toml` | Добавить openai, python-dotenv в dependencies | Новые зависимости |
| `acp-server/src/acp_server/protocol/core.py` | Добавить инициализацию orchestrator в `__init__` | Интеграция |
| `acp-server/src/acp_server/protocol/handlers/prompt.py` | Добавить вызов orchestrator в `session_prompt()` | Обработка prompts |

#### Тесты для фазы

```python
# tests/test_agent_setup.py
def test_agent_module_imports():
    """Проверить что все модули импортируются без ошибок."""
    from acp_server.agent import LLMAgent, NaiveAgent, AgentOrchestrator
    from acp_server.llm import LLMProvider, OpenAIProvider
    from acp_server.tools import ToolRegistry

def test_dependencies_available():
    """Проверить что зависимости установлены."""
    import openai
    import dotenv
```

#### Проверка фазы

```bash
# Из корня репозитория
make check

# Или локально для acp-server
uv run --directory acp-server python -c "from acp_server import agent, llm, tools"
```

#### Критерии приемки

- [x] `openai>=1.50.0` добавлена в `acp-server/pyproject.toml`
- [x] `python-dotenv>=1.0.0` добавлена в `acp-server/pyproject.toml`
- [x] Папки `agent/`, `llm/`, `tools/` созданы
- [x] Все `__init__.py` файлы созданы (пусто или с минимальным импортом)
- [x] `make check` проходит без ошибок
- [x] Тесты в `test_agent_setup.py` проходят

---

### Фаза 1: Базовые интерфейсы и состояние

#### Цель фазы

Создать базовые интерфейсы (ABC) и dataclasses для всей системы:
- Интерфейсы LLMProvider, ToolRegistry, LLMAgent
- Dataclasses для состояния и контекста
- Типы для сообщений и результатов

#### Файлы для создания

**`acp-server/src/acp_server/llm/base.py`**

```python
"""Базовый интерфейс для провайдеров LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class LLMMessage:
    """Сообщение для LLM."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMToolCall:
    """Вызов инструмента из LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Ответ от LLM."""
    text: str
    tool_calls: list[LLMToolCall]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", "error"


class LLMProvider(ABC):
    """Интерфейс для взаимодействия с LLM API.
    
    Провайдер инкапсулирует всю специфику работы с конкретной LLM,
    включая форматирование сообщений, обработку tool calls, retry-логику.
    """

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Инициализация провайдера с конфигурацией."""
        pass

    @abstractmethod
    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Получить завершение от LLM."""
        pass

    @abstractmethod
    async def stream_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Потоковое получение ответа от LLM."""
        pass
```

**`acp-server/src/acp_server/tools/base.py`**

```python
"""Базовые интерфейсы для системы инструментов."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """Определение инструмента для LLM."""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    kind: str  # "terminal", "filesystem", "other"
    requires_permission: bool = True


@dataclass
class ToolExecutionResult:
    """Результат выполнения инструмента."""
    success: bool
    output: str | None = None
    error: str | None = None


class ToolRegistry(ABC):
    """Реестр инструментов с механизмом выполнения."""

    @abstractmethod
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        kind: str,
        executor: Callable,
        requires_permission: bool = True,
    ) -> None:
        """Регистрация инструмента."""
        pass

    @abstractmethod
    def get_available_tools(
        self,
        session_id: str,
        include_permission_required: bool = True,
    ) -> list[ToolDefinition]:
        """Получить доступные инструменты для сессии."""
        pass

    @abstractmethod
    def to_llm_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Преобразовать определения инструментов для LLM."""
        pass

    @abstractmethod
    async def execute_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Выполнить инструмент."""
        pass
```

**`acp-server/src/acp_server/agent/base.py`**

```python
"""Базовый интерфейс для LLM-агентов."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from acp_server.llm.base import LLMMessage, LLMToolCall, LLMProvider
from acp_server.tools.base import ToolDefinition, ToolRegistry


@dataclass
class AgentContext:
    """Контекст выполнения агента для одного prompt turn."""
    session_id: str
    prompt: list[dict[str, Any]]  # Содержимое prompt от пользователя
    conversation_history: list[LLMMessage]  # История сообщений для LLM
    available_tools: list[ToolDefinition]  # Инструменты для этого turn
    config: dict[str, Any]  # SessionState.config_values


@dataclass
class AgentResponse:
    """Ответ агента после обработки prompt."""
    text: str
    tool_calls: list[LLMToolCall]
    stop_reason: str  # "end_turn", "tool_use", "max_tokens", "error"
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMAgent(ABC):
    """Базовый интерфейс для LLM-агентов.
    
    Агент отвечает за:
    - Обработку prompt turns
    - Управление историей сообщений
    - Интеграцию с LLM провайдером
    - Координацию выполнения инструментов
    """

    @abstractmethod
    async def initialize(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
    ) -> None:
        """Инициализация агента."""
        pass

    @abstractmethod
    async def process_prompt(self, context: AgentContext) -> AgentResponse:
        """Обработать prompt и вернуть ответ."""
        pass

    @abstractmethod
    async def cancel_prompt(self, session_id: str) -> None:
        """Отменить текущую обработку prompt."""
        pass

    @abstractmethod
    def add_to_history(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Добавить сообщение в историю сессии."""
        pass

    @abstractmethod
    def get_session_history(self, session_id: str) -> list[LLMMessage]:
        """Получить историю сообщений для сессии."""
        pass

    @abstractmethod
    async def end_session(self, session_id: str) -> None:
        """Завершить сессию и освободить ресурсы."""
        pass
```

**`acp-server/src/acp_server/agent/state.py`**

```python
"""Состояние и конфигурация агента."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrchestratorConfig:
    """Конфигурация оркестратора."""
    enabled: bool = False  # Включить ли использование агента
    llm_provider_class: str = "openai"  # Класс провайдера ("openai", "mock")
    agent_class: str = "naive"  # Класс агента ("naive")
    llm_config: dict[str, Any] = field(default_factory=dict)  # Конфиг для LLM
    
    # LLM параметры
    model: str = "gpt-4o"  # Модель
    temperature: float = 0.7  # Температура
    max_tokens: int = 8192  # Максимум токенов
    
    # Поведение агента
    enable_tools: bool = True  # Использовать инструменты
    tool_timeout: float = 30.0  # Timeout для выполнения инструментов
    history_limit: int = 100  # Лимит истории сообщений
```

#### Файлы для модификации

- `acp-server/src/acp_server/llm/__init__.py` - экспорт LLMProvider, LLMMessage, LLMResponse, LLMToolCall
- `acp-server/src/acp_server/tools/__init__.py` - экспорт ToolRegistry, ToolDefinition, ToolExecutionResult
- `acp-server/src/acp_server/agent/__init__.py` - экспорт LLMAgent, AgentContext, AgentResponse, OrchestratorConfig

#### Тесты для фазы

```python
# tests/test_agent_base.py
import pytest
from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.llm.base import LLMMessage, LLMProvider, LLMToolCall, LLMResponse
from acp_server.tools.base import ToolDefinition, ToolRegistry


def test_llm_message_creation():
    """Проверить создание LLMMessage."""
    msg = LLMMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_agent_context_creation():
    """Проверить создание AgentContext."""
    context = AgentContext(
        session_id="test-session",
        prompt=[],
        conversation_history=[],
        available_tools=[],
        config={},
    )
    assert context.session_id == "test-session"


def test_agent_response_creation():
    """Проверить создание AgentResponse."""
    response = AgentResponse(
        text="Hello",
        tool_calls=[],
        stop_reason="end_turn",
    )
    assert response.text == "Hello"
    assert response.stop_reason == "end_turn"


def test_orchestrator_config_creation():
    """Проверить создание OrchestratorConfig."""
    config = OrchestratorConfig(enabled=True)
    assert config.enabled is True
    assert config.model == "gpt-4o"
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] Все ABC интерфейсы созданы в `base.py` файлах
- [x] Все dataclasses созданы в `state.py` файле
- [x] Все `__init__.py` файлы содержат экспорты
- [x] Все тесты в `test_agent_base.py` проходят
- [x] `make check` проходит без ошибок (ruff, ty, pytest)

---

### Фаза 2: LLM провайдер (OpenAI)

#### Цель фазы

Реализовать конкретный LLM провайдер для OpenAI:
- OpenAIProvider с полной функциональностью
- MockLLMProvider для тестирования
- Интеграция с OpenAI Python SDK

#### Файлы для создания

**`acp-server/src/acp_server/llm/openai_provider.py`**

```python
"""OpenAI LLM провайдер."""

import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from acp_server.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Провайдер для взаимодействия с OpenAI API.
    
    Поддерживает:
    - Обычные completion с инструментами
    - Потоковые completion
    - Преобразование инструментов в OpenAI формат
    """

    def __init__(self):
        """Инициализация провайдера."""
        self._client: AsyncOpenAI | None = None
        self._model: str = "gpt-4o"
        self._temperature: float = 0.7
        self._max_tokens: int = 8192

    async def initialize(self, config: dict[str, Any]) -> None:
        """Инициализировать провайдер с конфигурацией.
        
        Args:
            config: {
                "api_key": str (опционально, по умолчанию из переменной окружения),
                "model": str (по умолчанию "gpt-4o"),
                "temperature": float (по умолчанию 0.7),
                "max_tokens": int (по умолчанию 8192),
                "base_url": str (опционально),
            }
        """
        api_key = config.get("api_key")
        self._model = config.get("model", "gpt-4o")
        self._temperature = config.get("temperature", 0.7)
        self._max_tokens = config.get("max_tokens", 8192)

        base_url = config.get("base_url")

        # Создать async клиента OpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,  # Если None, использует OPENAI_API_KEY из env
            base_url=base_url,  # Если None, использует дефолтный
        )

        logger.info(f"OpenAI провайдер инициализирован: model={self._model}")

    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Получить завершение от OpenAI API.
        
        Args:
            messages: История сообщений
            tools: Список инструментов в OpenAI формате
            **kwargs: Дополнительные параметры (temperature, max_tokens, etc.)
            
        Returns:
            LLMResponse с текстом, tool calls и stop reason
        """
        if self._client is None:
            raise RuntimeError("Провайдер не инициализирован")

        # Преобразовать сообщения в формат OpenAI
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Подготовить параметры запроса
        request_params = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
        }

        # Добавить инструменты если есть
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        try:
            response: ChatCompletion = await self._client.chat.completions.create(
                **request_params
            )

            return self._parse_completion(response)

        except Exception as e:
            logger.error(f"Ошибка при вызове OpenAI: {e}")
            raise

    async def stream_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Потоковое получение ответа от OpenAI API.
        
        Генерирует промежуточные LLMResponse при получении данных.
        """
        if self._client is None:
            raise RuntimeError("Провайдер не инициализирован")

        # Преобразовать сообщения
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        request_params = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "stream": True,
        }

        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        try:
            with await self._client.chat.completions.create(
                **request_params
            ) as stream:
                buffer = ""
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        buffer += chunk.choices[0].delta.content
                        yield LLMResponse(
                            text=buffer,
                            tool_calls=[],
                            stop_reason="streaming",
                        )

        except Exception as e:
            logger.error(f"Ошибка при потоковом вызове OpenAI: {e}")
            raise

    def _parse_completion(self, response: ChatCompletion) -> LLMResponse:
        """Преобразовать ответ OpenAI в LLMResponse.
        
        Args:
            response: Ответ от OpenAI API
            
        Returns:
            LLMResponse с распарсенными инструментами
        """
        choice = response.choices[0]
        message = choice.message

        # Извлечь текст
        text = message.content or ""

        # Извлечь tool calls
        tool_calls = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                if tool_call.type == "function":
                    tool_calls.append(
                        LLMToolCall(
                            id=tool_call.id,
                            name=tool_call.function.name,
                            arguments=tool_call.function.arguments
                            if isinstance(tool_call.function.arguments, dict)
                            else {},
                        )
                    )

        # Определить stop reason
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )
```

**`acp-server/src/acp_server/llm/mock_provider.py`**

```python
"""Mock LLM провайдер для тестирования."""

from typing import Any, AsyncIterator

from acp_server.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall


class MockLLMProvider(LLMProvider):
    """Mock провайдер для unit-тестирования.
    
    Возвращает предсказуемые ответы для тестирования логики агента
    без обращения к реальному API.
    """

    def __init__(self, response: str = "Mock response", tool_calls: list | None = None):
        """Инициализация mock провайдера.
        
        Args:
            response: Текст ответа, который будет возвращен
            tool_calls: Список tool calls для возврата
        """
        self.response = response
        self.tool_calls = tool_calls or []
        self.last_messages: list[LLMMessage] | None = None
        self.last_tools: list[dict[str, Any]] | None = None

    async def initialize(self, config: dict[str, Any]) -> None:
        """Mock инициализация."""
        pass

    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Вернуть mock ответ."""
        self.last_messages = messages
        self.last_tools = tools

        return LLMResponse(
            text=self.response,
            tool_calls=self.tool_calls,
            stop_reason="end_turn" if not self.tool_calls else "tool_use",
        )

    async def stream_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Вернуть mock потоковый ответ."""
        self.last_messages = messages
        self.last_tools = tools

        yield LLMResponse(
            text=self.response,
            tool_calls=self.tool_calls,
            stop_reason="end_turn" if not self.tool_calls else "tool_use",
        )
```

#### Файлы для модификации

- `acp-server/src/acp_server/llm/__init__.py` - добавить экспорт OpenAIProvider, MockLLMProvider

#### Тесты для фазы

```python
# tests/test_llm_provider.py
import pytest
from acp_server.llm.base import LLMMessage, LLMResponse
from acp_server.llm.mock_provider import MockLLMProvider


@pytest.mark.asyncio
async def test_mock_provider_completion():
    """Проверить mock провайдер."""
    provider = MockLLMProvider(response="Test response")
    await provider.initialize({})

    messages = [LLMMessage(role="user", content="Hello")]
    response = await provider.create_completion(messages)

    assert response.text == "Test response"
    assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_mock_provider_with_tools():
    """Проверить mock провайдер с инструментами."""
    from acp_server.llm.base import LLMToolCall

    tool_call = LLMToolCall(
        id="1",
        name="test_tool",
        arguments={"arg1": "value1"},
    )
    provider = MockLLMProvider(response="Using tool", tool_calls=[tool_call])
    await provider.initialize({})

    messages = [LLMMessage(role="user", content="Hello")]
    response = await provider.create_completion(messages)

    assert response.text == "Using tool"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "test_tool"
    assert response.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_mock_provider_stream():
    """Проверить потоковое получение от mock провайдера."""
    provider = MockLLMProvider(response="Streaming response")
    await provider.initialize({})

    messages = [LLMMessage(role="user", content="Hello")]
    responses = []
    async for response in provider.stream_completion(messages):
        responses.append(response)

    assert len(responses) == 1
    assert responses[0].text == "Streaming response"
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] OpenAIProvider полностью реализован
- [x] MockLLMProvider полностью реализован
- [x] Все тесты в `test_llm_provider.py` проходят (без реального API)
- [x] `make check` проходит без ошибок
- [x] Код имеет docstrings и комментарии

---

### Фаза 3: Tool Registry и инструменты

#### Цель фазы

Реализовать реестр инструментов в соответствии с ACP протоколом:
- SimpleToolRegistry для описания доступных инструментов
- Разделение инструментов на server-side и client-side
- Интеграция с Permission System
- Базовые встроенные инструменты

#### Важное уточнение: Архитектура инструментов

Согласно [Agent Client Protocol](../doc/Agent%20Client%20Protocol/protocol/08-Tool%20Calls.md):
- **Server (Agent)** - мозг: генерирует tool calls через `session/update`
- **Client** - руки: может выполнять инструменты локально

**Инструменты делятся на:**
1. **Client-side инструменты** - файловая система, терминал, поиск (выполняются на клиенте)
2. **Server-side инструменты** - API вызовы, логика, обработка (выполняются на сервере)

**ToolRegistry на сервере:**
- Регистрирует доступные инструменты (определяет какие инструменты может использовать LLM)
- Server-side инструменты выполняются в `handle_tool_execution()`
- Client-side инструменты - клиент выполняет сам на основе `session/update` notifications
- Agent запрашивает разрешение через `session/request_permission` если нужно

#### Файлы для создания

**`acp-server/src/acp_server/tools/registry.py`**

```python
"""Реестр инструментов.

Согласно ACP протоколу, инструменты делятся на:
1. Server-side инструменты - выполняются сервером (API, логика, обработка данных)
2. Client-side инструменты - выполняются клиентом (файловая система, терминал, UI)

ToolRegistry регистрирует инструменты, которые LLM может использовать,
но реальное выполнение зависит от типа инструмента:
- Server-side: выполняются в execute_tool()
- Client-side: описываются в tool calls, клиент выполняет на основе session/update
"""

import logging
from typing import Any, Callable

from acp_server.protocol.state import SessionState
from acp_server.tools.base import ToolDefinition, ToolExecutionResult, ToolRegistry

logger = logging.getLogger(__name__)


class SimpleToolRegistry(ToolRegistry):
    """Простая реализация реестра инструментов.
    
    Хранит определения инструментов (как server-side, так и client-side),
    управляет доступом в зависимости от прав сессии.
    """

    def __init__(self):
        """Инициализация реестра."""
        # Инструменты: name -> (определение, executor или None для client-side)
        self._tools: dict[str, tuple[ToolDefinition, Callable | None]] = {}
        self._sessions: dict[str, SessionState] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        kind: str,
        executor: Callable | None = None,
        requires_permission: bool = True,
        is_client_side: bool = False,
    ) -> None:
        """Регистрация инструмента.
        
        Args:
            name: Уникальное имя инструмента
            description: Человеческое описание
            parameters: JSON Schema параметров
            kind: Категория (terminal, filesystem, read, edit, etc.)
            executor: Async callable для выполнения (None для client-side)
            requires_permission: Требуется ли разрешение
            is_client_side: Выполняется ли на клиенте
        """
        definition = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            kind=kind,
            requires_permission=requires_permission,
        )
        self._tools[name] = (definition, executor)
        
        tool_type = "client-side" if is_client_side else "server-side"
        logger.debug(f"Инструмент зарегистрирован: {name} ({tool_type})")

    def get_available_tools(
        self,
        session_id: str,
        include_permission_required: bool = True,
        server_only: bool = False,
    ) -> list[ToolDefinition]:
        """Получить доступные инструменты для сессии.
        
        Учитывает права доступа сессии.
        
        Args:
            session_id: ID сессии
            include_permission_required: Включать ли инструменты,
                требующие разрешения
            server_only: Включать только server-side инструменты
            
        Returns:
            Список доступных инструментов
        """
        available = []

        for definition, executor in self._tools.values():
            # Пропустить инструменты, требующие разрешения если их исключать
            if definition.requires_permission and not include_permission_required:
                continue
            
            # Пропустить client-side если нужны только server-side
            if server_only and executor is None:
                continue

            # TODO: Проверить права сессии через SessionState.permissions
            available.append(definition)

        return available

    def to_llm_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]:
        """Преобразовать определения инструментов в формат OpenAI.
        
        Включает как server-side, так и client-side инструменты.
        LLM может генерировать tool calls для всех типов.
        
        Args:
            tools: Список определений инструментов
            
        Returns:
            Список инструментов в формате OpenAI
        """
        llm_tools = []

        for tool in tools:
            llm_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            llm_tools.append(llm_tool)

        return llm_tools

    async def execute_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Выполнить server-side инструмент.
        
        Client-side инструменты (файловая система, терминал) не выполняются здесь.
        Они обрабатываются клиентом на основе session/update notifications.
        
        Args:
            session_id: ID сессии
            tool_name: Имя инструмента
            arguments: Аргументы для выполнения
            
        Returns:
            Результат выполнения (для server-side инструментов)
            или None (для client-side инструментов)
        """
        if tool_name not in self._tools:
            return ToolExecutionResult(
                success=False,
                error=f"Инструмент {tool_name} не найден",
            )

        definition, executor = self._tools[tool_name]

        # Если это client-side инструмент, не выполняем на сервере
        if executor is None:
            return ToolExecutionResult(
                success=True,
                output="Client-side tool - executed by client",
            )

        # TODO: Проверить разрешения через Permission System
        # если definition.requires_permission

        try:
            result = await executor(session_id, arguments)
            return result
        except Exception as e:
            logger.error(f"Ошибка при выполнении {tool_name}: {e}")
            return ToolExecutionResult(
                success=False,
                error=str(e),
            )
```

**`acp-server/src/acp_server/tools/builtin_tools.py`**

```python
"""Встроенные ACP инструменты.

Согласно ACP протоколу, инструменты делятся на:
1. Server-side инструменты - выполняются на сервере (есть executor)
2. Client-side инструменты - выполняются на клиенте (executor=None)

Примеры:
- Server-side: echo, info, API вызовы, обработка данных
- Client-side: read_file, write_file, execute_command, terminal/create
"""

from typing import Any

from acp_server.tools.base import ToolExecutionResult


# ============================================================================
# Server-side инструменты (выполняются на сервере)
# ============================================================================

async def echo_tool(session_id: str, arguments: dict[str, Any]) -> ToolExecutionResult:
    """Echo инструмент для тестирования (server-side)."""
    message = arguments.get("message", "")
    return ToolExecutionResult(
        success=True,
        output=f"Echo: {message}",
    )


async def info_tool(session_id: str, arguments: dict[str, Any]) -> ToolExecutionResult:
    """Информация о сессии (server-side)."""
    return ToolExecutionResult(
        success=True,
        output=f"Session ID: {session_id}",
    )


async def process_data_tool(
    session_id: str, arguments: dict[str, Any]
) -> ToolExecutionResult:
    """Обработка данных на сервере (server-side)."""
    data = arguments.get("data", "")
    # Здесь может быть сложная логика обработки
    result = f"Processed: {data.upper()}"
    return ToolExecutionResult(
        success=True,
        output=result,
    )


# ============================================================================
# Client-side инструменты (выполняются на клиенте)
# Примечание: executor=None, т.к. клиент выполняет сам
# ============================================================================

# Встроенные инструменты
BUILTIN_TOOLS = {
    # Server-side инструменты (с executor)
    "echo": {
        "name": "echo",
        "description": "Echo инструмент для тестирования",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Сообщение для эхо",
                }
            },
            "required": ["message"],
        },
        "kind": "other",
        "executor": echo_tool,
        "is_client_side": False,
    },
    "info": {
        "name": "info",
        "description": "Информация о сессии",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "kind": "other",
        "executor": info_tool,
        "is_client_side": False,
    },
    "process_data": {
        "name": "process_data",
        "description": "Обработать данные на сервере",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Данные для обработки",
                }
            },
            "required": ["data"],
        },
        "kind": "other",
        "executor": process_data_tool,
        "is_client_side": False,
    },
    
    # Client-side инструменты (executor=None)
    # Согласно ACP протоколу, эти методы вызываются агентом на клиенте:
    # - fs/read_text_file (09-File System.md)
    # - fs/write_text_file (09-File System.md)
    # - terminal/create (10-Terminal.md)
    # LLM может генерировать tool calls для них,
    # но реальное выполнение происходит на клиенте
    "fs/read_text_file": {
        "name": "fs/read_text_file",
        "description": "Прочитать текстовый файл из файловой системы клиента",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Абсолютный путь к файлу",
                },
                "line": {
                    "type": "integer",
                    "description": "Номер строки для начала чтения (опционально)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Максимальное количество строк (опционально)",
                },
            },
            "required": ["path"],
        },
        "kind": "read",
        "executor": None,  # Client-side - выполняется через fs/read_text_file RPC
        "is_client_side": True,
    },
    "fs/write_text_file": {
        "name": "fs/write_text_file",
        "description": "Записать текстовый файл в файловую систему клиента",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Абсолютный путь к файлу",
                },
                "content": {
                    "type": "string",
                    "description": "Содержимое для записи в файл",
                },
            },
            "required": ["path", "content"],
        },
        "kind": "edit",
        "executor": None,  # Client-side - выполняется через fs/write_text_file RPC
        "is_client_side": True,
    },
    "terminal/create": {
        "name": "terminal/create",
        "description": "Создать терминал и выполнить команду в окружении клиента",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Команда для выполнения",
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Аргументы команды",
                },
                "cwd": {
                    "type": "string",
                    "description": "Рабочая директория (абсолютный путь)",
                },
                "env": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                        },
                    },
                    "description": "Переменные окружения",
                },
            },
            "required": ["command"],
        },
        "kind": "execute",
        "executor": None,  # Client-side - выполняется через terminal/create RPC
        "is_client_side": True,
    },
}
```

#### Файлы для модификации

- `acp-server/src/acp_server/tools/__init__.py` - экспорт SimpleToolRegistry
- `acp-server/src/acp_server/tools/executor.py` - вспомогательные функции (пусто или минимум)

#### Тесты для фазы

```python
# tests/test_tool_registry.py
import pytest
from acp_server.tools.registry import SimpleToolRegistry
from acp_server.tools.base import ToolExecutionResult


def test_tool_registration():
    """Проверить регистрацию инструмента."""
    registry = SimpleToolRegistry()

    async def dummy_executor(session_id: str, args: dict):
        return ToolExecutionResult(success=True, output="OK")

    registry.register_tool(
        name="test",
        description="Test tool",
        parameters={},
        kind="other",
        executor=dummy_executor,
    )

    tools = registry.get_available_tools("session1")
    assert len(tools) == 1
    assert tools[0].name == "test"


def test_to_llm_tools():
    """Проверить преобразование в формат OpenAI."""
    registry = SimpleToolRegistry()

    async def dummy_executor(session_id: str, args: dict):
        return ToolExecutionResult(success=True)

    registry.register_tool(
        name="test",
        description="Test tool",
        parameters={"type": "object", "properties": {}},
        kind="other",
        executor=dummy_executor,
    )

    tools = registry.get_available_tools("session1")
    llm_tools = registry.to_llm_tools(tools)

    assert len(llm_tools) == 1
    assert llm_tools[0]["type"] == "function"
    assert llm_tools[0]["function"]["name"] == "test"


@pytest.mark.asyncio
async def test_execute_tool():
    """Проверить выполнение инструмента."""
    registry = SimpleToolRegistry()

    async def dummy_executor(session_id: str, args: dict):
        return ToolExecutionResult(success=True, output="Executed")

    registry.register_tool(
        name="test",
        description="Test",
        parameters={},
        kind="other",
        executor=dummy_executor,
    )

    result = await registry.execute_tool("session1", "test", {})
    assert result.success is True
    assert result.output == "Executed"
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] SimpleToolRegistry полностью реализован
- [x] Встроенные инструменты определены в builtin_tools.py
- [x] Все тесты проходят
- [x] `make check` без ошибок

---

### Фаза 4: Naive Agent

#### Цель фазы

Реализовать наивного LLM-агента:
- Хранение истории сообщений в памяти
- Базовая обработка prompt turns
- Интеграция с LLM провайдером и Tool Registry

#### Файлы для создания

**`acp-server/src/acp_server/agent/naive_agent.py`**

```python
"""Наивная реализация LLM-агента."""

import logging
from typing import Any

from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.llm.base import LLMMessage, LLMProvider
from acp_server.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


class NaiveAgent(LLMAgent):
    """Наивная реализация LLM-агента.
    
    Основные особенности:
    - История сообщений хранится в памяти (dict[session_id -> list])
    - Прямой однопроходный вызов LLM
    - Простая обработка tool calls без сложной логики
    - Нет retry-логики, кэширования, потокового обновления
    """

    def __init__(self):
        """Инициализация пустого агента."""
        self._llm_provider: LLMProvider | None = None
        self._tool_registry: ToolRegistry | None = None
        self._conversation_history: dict[str, list[LLMMessage]] = {}
        self._system_prompt: str = ""

    async def initialize(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
    ) -> None:
        """Инициализация агента.
        
        Args:
            llm_provider: Провайдер LLM
            tool_registry: Реестр инструментов
            config: Конфигурация (может содержать system_prompt)
        """
        self._llm_provider = llm_provider
        self._tool_registry = tool_registry

        # Получить системный prompt из конфига или использовать дефолт
        self._system_prompt = config.get(
            "system_prompt",
            "You are a helpful assistant. You have access to tools to help the user.",
        )

        logger.info("NaiveAgent инициализирован")

    async def process_prompt(self, context: AgentContext) -> AgentResponse:
        """Обработать prompt и вернуть ответ.
        
        Основной метод обработки пользовательского запроса.
        
        Args:
            context: Контекст выполнения с историей, инструментами, конфигом
            
        Returns:
            AgentResponse с текстом, tool calls и stop reason
        """
        if self._llm_provider is None:
            raise RuntimeError("Агент не инициализирован")

        session_id = context.session_id

        # Инициализировать историю если не существует
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = []

        # Получить текущую историю
        history = self._conversation_history[session_id]

        # Если история пуста, добавить системный prompt
        if not history:
            history.append(
                LLMMessage(role="system", content=self._system_prompt)
            )

        # Преобразовать prompt контент в сообщения
        # Простое преобразование: берем последний элемент как текст
        prompt_text = ""
        for item in context.prompt:
            if isinstance(item, dict) and "text" in item:
                prompt_text += item["text"]

        # Добавить пользовательское сообщение
        history.append(LLMMessage(role="user", content=prompt_text))

        # Подготовить инструменты для отправки в LLM
        llm_tools = None
        if context.available_tools:
            llm_tools = self._tool_registry.to_llm_tools(context.available_tools)

        try:
            # Получить ответ от LLM
            llm_response = await self._llm_provider.create_completion(
                messages=history,
                tools=llm_tools,
            )

            # Добавить ответ в историю
            if llm_response.text:
                history.append(LLMMessage(role="assistant", content=llm_response.text))

            # Создать AgentResponse
            response = AgentResponse(
                text=llm_response.text,
                tool_calls=llm_response.tool_calls,
                stop_reason=llm_response.stop_reason,
            )

            logger.debug(
                f"Prompt обработан для {session_id}: "
                f"text_len={len(llm_response.text)}, "
                f"tool_calls={len(llm_response.tool_calls)}"
            )

            return response

        except Exception as e:
            logger.error(f"Ошибка при обработке prompt для {session_id}: {e}")
            raise

    async def cancel_prompt(self, session_id: str) -> None:
        """Отменить текущую обработку prompt.
        
        В наивной реализации это просто no-op.
        """
        logger.debug(f"Отмена prompt для {session_id}")

    def add_to_history(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Добавить сообщение в историю сессии.
        
        Быстрый неблокирующий метод.
        """
        if session_id not in self._conversation_history:
            self._conversation_history[session_id] = [
                LLMMessage(role="system", content=self._system_prompt)
            ]

        self._conversation_history[session_id].append(
            LLMMessage(role=role, content=content)
        )

    def get_session_history(self, session_id: str) -> list[LLMMessage]:
        """Получить историю сообщений для сессии."""
        return self._conversation_history.get(session_id, [])

    async def end_session(self, session_id: str) -> None:
        """Завершить сессию и освободить ресурсы.
        
        Удалить историю сессии из памяти.
        """
        if session_id in self._conversation_history:
            del self._conversation_history[session_id]
            logger.debug(f"Сессия {session_id} завершена")
```

#### Файлы для модификации

- `acp-server/src/acp_server/agent/__init__.py` - экспорт NaiveAgent

#### Тесты для фазы

```python
# tests/test_naive_agent.py
import pytest
from acp_server.agent.naive_agent import NaiveAgent
from acp_server.agent.base import AgentContext, AgentResponse
from acp_server.llm.base import LLMMessage
from acp_server.llm.mock_provider import MockLLMProvider
from acp_server.tools.registry import SimpleToolRegistry
from acp_server.tools.base import ToolExecutionResult


@pytest.mark.asyncio
async def test_naive_agent_initialization():
    """Проверить инициализацию агента."""
    agent = NaiveAgent()
    provider = MockLLMProvider()
    registry = SimpleToolRegistry()

    await agent.initialize(provider, registry, {})

    assert agent._llm_provider is not None
    assert agent._tool_registry is not None


@pytest.mark.asyncio
async def test_naive_agent_process_prompt():
    """Проверить обработку prompt."""
    agent = NaiveAgent()
    provider = MockLLMProvider(response="Test response")
    registry = SimpleToolRegistry()

    await agent.initialize(provider, registry, {})

    context = AgentContext(
        session_id="session1",
        prompt=[{"text": "Hello"}],
        conversation_history=[],
        available_tools=[],
        config={},
    )

    response = await agent.process_prompt(context)

    assert isinstance(response, AgentResponse)
    assert response.text == "Test response"
    assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_naive_agent_history():
    """Проверить управление историей."""
    agent = NaiveAgent()
    provider = MockLLMProvider()
    registry = SimpleToolRegistry()

    await agent.initialize(provider, registry, {})

    # Добавить сообщение
    agent.add_to_history("session1", "user", "Hello")
    agent.add_to_history("session1", "assistant", "Hi there")

    # Получить историю
    history = agent.get_session_history("session1")

    assert len(history) >= 2
    assert history[-2].role == "user"
    assert history[-2].content == "Hello"
    assert history[-1].role == "assistant"
    assert history[-1].content == "Hi there"


@pytest.mark.asyncio
async def test_naive_agent_end_session():
    """Проверить завершение сессии."""
    agent = NaiveAgent()
    provider = MockLLMProvider()
    registry = SimpleToolRegistry()

    await agent.initialize(provider, registry, {})

    agent.add_to_history("session1", "user", "Hello")
    await agent.end_session("session1")

    history = agent.get_session_history("session1")
    assert len(history) == 0
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] NaiveAgent полностью реализован со всеми методами
- [x] История сообщений управляется корректно
- [x] Интеграция с LLMProvider и ToolRegistry работает
- [x] Все тесты проходят
- [x] `make check` без ошибок

---

### Фаза 5: Agent Orchestrator

#### Цель фазы

Реализовать оркестратор для координации всех компонентов:
- Интеграция всех компонентов (LLMProvider, Agent, ToolRegistry)
- Преобразование ACP контекста в AgentContext
- Управление tool execution и результатами

#### Файлы для создания

**`acp-server/src/acp_server/agent/orchestrator.py`**

```python
"""Оркестратор интеграции LLM-агента с ACP протоколом."""

import logging
from typing import Any

from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.agent.state import OrchestratorConfig
from acp_server.llm.base import LLMProvider
from acp_server.protocol.state import SessionState
from acp_server.tools.base import ToolRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Оркестратор интеграции LLM-агента с ACP протоколом.
    
    Точка интеграции между:
    - ACPProtocol (session_prompt)
    - LLMAgent (обработка)
    - ToolRegistry (выполнение инструментов)
    - SessionState (хранение состояния)
    
    Отвечает за:
    - Инициализацию провайдера и агента
    - Преобразование ACP контекста в AgentContext
    - Координацию обработки prompt turns
    - Управление историей и состоянием
    """

    def __init__(self, config: OrchestratorConfig):
        """Инициализация оркестратора.
        
        Args:
            config: Конфигурация оркестратора
        """
        self.config = config
        self._llm_provider: LLMProvider | None = None
        self._agent: LLMAgent | None = None
        self._tool_registry: ToolRegistry | None = None
        self._initialized = False

    async def initialize(
        self,
        llm_provider: LLMProvider,
        agent: LLMAgent,
        tool_registry: ToolRegistry,
    ) -> None:
        """Инициализировать оркестратор.
        
        Args:
            llm_provider: Провайдер LLM
            agent: Экземпляр агента
            tool_registry: Реестр инструментов
        """
        if not self.config.enabled:
            logger.info("Оркестратор отключен")
            return

        self._llm_provider = llm_provider
        self._agent = agent
        self._tool_registry = tool_registry

        # Инициализировать провайдер
        llm_config = self.config.llm_config or {}
        llm_config.setdefault("model", self.config.model)
        llm_config.setdefault("temperature", self.config.temperature)
        llm_config.setdefault("max_tokens", self.config.max_tokens)

        await self._llm_provider.initialize(llm_config)

        # Инициализировать агента
        await self._agent.initialize(
            self._llm_provider,
            self._tool_registry,
            llm_config,
        )

        self._initialized = True
        logger.info("AgentOrchestrator инициализирован")

    async def handle_prompt(
        self,
        session_state: SessionState,
        prompt_content: list[dict[str, Any]],
        session_config: dict[str, Any],
    ) -> AgentResponse:
        """Обработать prompt turn через агента.
        
        Преобразует ACP контекст в AgentContext, делегирует агенту,
        возвращает AgentResponse.
        
        Args:
            session_state: Состояние сессии из SessionState
            prompt_content: Содержимое prompt от пользователя
            session_config: Конфигурация сессии
            
        Returns:
            AgentResponse с текстом, tool calls, stop reason
            
        Raises:
            RuntimeError: Если оркестратор не инициализирован
        """
        if not self._initialized or self._agent is None:
            raise RuntimeError("Оркестратор не инициализирован")

        session_id = session_state.session_id

        # Получить доступные инструменты
        available_tools = []
        if self.config.enable_tools and self._tool_registry:
            available_tools = self._tool_registry.get_available_tools(session_id)

        # Получить историю из агента
        conversation_history = self._agent.get_session_history(session_id)

        # Создать контекст для агента
        context = AgentContext(
            session_id=session_id,
            prompt=prompt_content,
            conversation_history=conversation_history,
            available_tools=available_tools,
            config=session_config,
        )

        # Обработать prompt
        response = await self._agent.process_prompt(context)

        logger.debug(
            f"Prompt обработан для {session_id}: "
            f"stop_reason={response.stop_reason}"
        )

        return response

    async def handle_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Выполнить tool call через registry.
        
        Точка интеграции с Permission System.
        
        Args:
            session_id: ID сессии
            tool_name: Имя инструмента
            arguments: Аргументы для выполнения
            
        Returns:
            Результат выполнения инструмента
        """
        if self._tool_registry is None:
            raise RuntimeError("Tool registry не инициализирован")

        result = await self._tool_registry.execute_tool(
            session_id,
            tool_name,
            arguments,
        )

        # Добавить результат в историю агента
        if self._agent:
            result_text = result.output or result.error or "No output"
            self._agent.add_to_history(
                session_id,
                "user",  # В АСП результат инструмента обычно идет как user сообщение
                f"Tool {tool_name} result:\n{result_text}",
            )

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        }

    async def cancel_prompt(self, session_id: str) -> None:
        """Отменить текущую обработку prompt.
        
        Args:
            session_id: ID сессии для отмены
        """
        if self._agent:
            await self._agent.cancel_prompt(session_id)
            logger.debug(f"Prompt отменен для {session_id}")

    async def end_session(self, session_id: str) -> None:
        """Завершить сессию и освободить ресурсы.
        
        Args:
            session_id: ID сессии для завершения
        """
        if self._agent:
            await self._agent.end_session(session_id)
            logger.debug(f"Сессия {session_id} завершена в оркестраторе")

    def is_enabled(self) -> bool:
        """Проверить, включен ли оркестратор.
        
        Returns:
            True если оркестратор включен и инициализирован
        """
        return self.config.enabled and self._initialized
```

**`acp-server/src/acp_server/agent/config.py`**

```python
"""Конфигурация агента из переменных окружения."""

import os
from acp_server.agent.state import OrchestratorConfig


def load_config_from_env() -> OrchestratorConfig:
    """Загрузить конфигурацию из переменных окружения.
    
    Поддерживаемые переменные:
    - AGENT_ENABLED: "true"|"false" (по умолчанию "false")
    - AGENT_LLM_PROVIDER: "openai"|"mock" (по умолчанию "openai")
    - AGENT_LLMM_CLASS: "naive" (по умолчанию "naive")
    - OPENAI_API_KEY: API ключ для OpenAI
    - AGENT_MODEL: Модель (по умолчанию "gpt-4o")
    - AGENT_TEMPERATURE: Температура (по умолчанию 0.7)
    - AGENT_MAX_TOKENS: Макс токенов (по умолчанию 8192)
    
    Returns:
        OrchestratorConfig с загруженными параметрами
    """
    enabled = os.getenv("AGENT_ENABLED", "false").lower() == "true"
    llm_provider = os.getenv("AGENT_LLM_PROVIDER", "openai")
    agent_class = os.getenv("AGENT_CLASS", "naive")
    model = os.getenv("AGENT_MODEL", "gpt-4o")
    temperature = float(os.getenv("AGENT_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("AGENT_MAX_TOKENS", "8192"))

    llm_config = {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    return OrchestratorConfig(
        enabled=enabled,
        llm_provider_class=llm_provider,
        agent_class=agent_class,
        llm_config=llm_config,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
```

#### Файлы для модификации

- `acp-server/src/acp_server/agent/__init__.py` - экспорт AgentOrchestrator, OrchestratorConfig, load_config_from_env

#### Тесты для фазы

```python
# tests/test_orchestrator.py
import pytest
from acp_server.agent.orchestrator import AgentOrchestrator
from acp_server.agent.state import OrchestratorConfig
from acp_server.agent.naive_agent import NaiveAgent
from acp_server.llm.mock_provider import MockLLMProvider
from acp_server.tools.registry import SimpleToolRegistry
from acp_server.protocol.state import SessionState


@pytest.mark.asyncio
async def test_orchestrator_initialization():
    """Проверить инициализацию оркестратора."""
    config = OrchestratorConfig(enabled=True)
    orchestrator = AgentOrchestrator(config)

    provider = MockLLMProvider()
    agent = NaiveAgent()
    registry = SimpleToolRegistry()

    await orchestrator.initialize(provider, agent, registry)

    assert orchestrator.is_enabled() is True


@pytest.mark.asyncio
async def test_orchestrator_disabled():
    """Проверить отключенный оркестратор."""
    config = OrchestratorConfig(enabled=False)
    orchestrator = AgentOrchestrator(config)

    provider = MockLLMProvider()
    agent = NaiveAgent()
    registry = SimpleToolRegistry()

    await orchestrator.initialize(provider, agent, registry)

    assert orchestrator.is_enabled() is False


@pytest.mark.asyncio
async def test_orchestrator_handle_prompt():
    """Проверить обработку prompt через оркестратор."""
    config = OrchestratorConfig(enabled=True)
    orchestrator = AgentOrchestrator(config)

    provider = MockLLMProvider(response="Test response")
    agent = NaiveAgent()
    registry = SimpleToolRegistry()

    await orchestrator.initialize(provider, agent, registry)

    session_state = SessionState(
        session_id="session1",
        client_name="test",
        client_version="1.0",
    )

    response = await orchestrator.handle_prompt(
        session_state,
        [{"text": "Hello"}],
        {},
    )

    assert response.text == "Test response"
    assert response.stop_reason == "end_turn"
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] AgentOrchestrator полностью реализован
- [x] Преобразование ACP контекста в AgentContext работает
- [x] Integration тесты проходят
- [x] `make check` без ошибок

---

### Фаза 6: Интеграция с протоколом

#### Цель фазы

Интегрировать AgentOrchestrator в ACP протокол с корректной отправкой tool calls:
- Добавить инициализацию в ACPProtocol
- Модифицировать handler prompt.py для использования агента
- Отправлять tool calls клиенту через session/update (не в ответе)
- Обеспечить fallback при отключенном агенте

#### Важное: Tool Call Flow согласно ACP

Согласно [Agent Client Protocol](../doc/Agent%20Client%20Protocol/protocol/08-Tool%20Calls.md):

1. **Agent генерирует tool call** -> отправляет через `session/update` с `sessionUpdate: "tool_call"`
2. **Client получает notification** -> может выполнить инструмент локально
3. **Client отправляет результат** -> через `session/update` с `tool_call_update`
4. **Agent обрабатывает результат** -> добавляет в историю, продолжает обработку

**Инструменты:**
- **Client-side** (filesystem, terminal, search): Agent описывает в tool call, клиент выполняет
- **Server-side** (API, логика): Agent выполняет в `handle_tool_execution()`

#### Файлы для модификации

**`acp-server/src/acp_server/protocol/core.py`**

В методе `__init__`:
```python
async def __init__(self, storage: SessionStorage, ...):
    # ... существующий код ...
    
    # Инициализировать оркестратор (фаза 6)
    from acp_server.agent.orchestrator import AgentOrchestrator
    from acp_server.agent.config import load_config_from_env
    from acp_server.agent.naive_agent import NaiveAgent
    from acp_server.llm.openai_provider import OpenAIProvider
    from acp_server.tools.registry import SimpleToolRegistry

    orchestrator_config = load_config_from_env()
    self.agent_orchestrator = AgentOrchestrator(orchestrator_config)

    if orchestrator_config.enabled:
        provider = OpenAIProvider()
        agent = NaiveAgent()
        registry = SimpleToolRegistry()
        
        # Регистрировать встроенные инструменты (server-side)
        from acp_server.tools.builtin_tools import BUILTIN_TOOLS
        for tool_def in BUILTIN_TOOLS.values():
            registry.register_tool(
                name=tool_def["name"],
                description=tool_def["description"],
                parameters=tool_def["parameters"],
                kind=tool_def["kind"],
                executor=tool_def.get("executor"),  # None для client-side
                is_client_side=tool_def.get("is_client_side", False),
            )
        
        await self.agent_orchestrator.initialize(provider, agent, registry)
```

**`acp-server/src/acp_server/protocol/handlers/prompt.py`**

В функции `session_prompt()`:
```python
async def session_prompt(protocol: ACPProtocol, request: Request) -> ProtocolOutcome:
    """Обработать session/prompt с поддержкой LLM агента."""
    # ... получить session_state ...

    # Проверить если агент включен (фаза 6)
    if protocol.agent_orchestrator.is_enabled():
        agent_response = await protocol.agent_orchestrator.handle_prompt(
            session_state,
            request.params.get("prompt", []),
            session_state.config_values,
        )
        
        # Основной результат - текст от LLM
        result_content = [{"type": "text", "text": agent_response.text}]
        
        # Если есть tool calls, отправить их через session/update
        if agent_response.tool_calls:
            # Отправить каждый tool call клиенту через session/update
            for tool_call in agent_response.tool_calls:
                # Преобразовать в формат ACP tool call
                acp_tool_call = {
                    "toolCallId": tool_call.id,
                    "name": tool_call.name,
                    "input": tool_call.arguments,
                }
                
                # Отправить notification session/update
                # session/update -> sessionUpdate: "tool_call"
                # (реализуется в handler'е через WebSocket notification)
                await protocol.notify_tool_call(
                    session_id=session_state.session_id,
                    tool_call=acp_tool_call,
                )
    else:
        # Fallback на текущее поведение (без агента)
        result_content = [{"type": "text", "text": ""}]

    # Вернуть основной результат (текст)
    return ProtocolOutcome(
        success=True,
        data={
            "content": result_content,
        },
    )
```

#### Новый метод в ACPProtocol

```python
async def notify_tool_call(
    self,
    session_id: str,
    tool_call: dict[str, Any],
) -> None:
    """Отправить tool call клиенту через session/update notification.
    
    Согласно ACP протоколу, tool calls отправляются через session/update,
    а не в результате prompt.
    
    Args:
        session_id: ID сессии
        tool_call: Определение инструмента для выполнения на клиенте
    """
    # Создать session/update notification
    update_notification = {
        "jsonrpc": "2.0",
        "method": "session/update",
        "params": {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_call["toolCallId"],
                "title": f"Tool call: {tool_call['name']}",
                "kind": tool_call.get("kind", "other"),
                "status": "pending",
                "rawInput": tool_call["input"],
            },
        },
    }
    
    # Отправить WebSocket клиенту (реализуется в http_server.py)
    await self.send_notification(session_id, update_notification)
```

#### Тесты для фазы

```python
# tests/test_protocol_integration.py
import pytest
from acp_server.protocol.core import ACPProtocol
from acp_server.storage.memory import InMemoryStorage


@pytest.mark.asyncio
async def test_protocol_with_disabled_agent():
    """Проверить протокол с отключенным агентом."""
    # Убедиться что переменная окружения не включает агента
    import os
    os.environ["AGENT_ENABLED"] = "false"

    storage = InMemoryStorage()
    protocol = ACPProtocol(storage)

    assert protocol.agent_orchestrator.is_enabled() is False


@pytest.mark.asyncio
async def test_protocol_session_prompt():
    """Проверить обработку session_prompt через протокол."""
    import os
    os.environ["AGENT_ENABLED"] = "false"

    storage = InMemoryStorage()
    protocol = ACPProtocol(storage)

    # Создать сессию
    from acp_server.protocol.handlers.session import session_new
    from acp_server.messages import Request

    request = Request(
        method="session/new",
        params={
            "client_name": "test",
            "client_version": "1.0",
        },
    )

    result = await session_new(protocol, request)
    assert result.success

    # Отправить prompt
    request = Request(
        method="session/prompt",
        params={
            "session_id": result.data["session_id"],
            "prompt": [{"type": "text", "text": "Hello"}],
        },
    )

    result = await protocol.handlers["session/prompt"](protocol, request)
    assert result.success
```

#### Проверка фазы

```bash
make check
```

#### Критерии приемки

- [x] AgentOrchestrator инициализируется в ACPProtocol
- [x] session_prompt использует оркестратор если включен
- [x] Fallback на текущее поведение работает
- [x] Тесты интеграции проходят
- [x] `make check` без ошибок

---

### Фаза 7: Тестирование и документация

#### Цель фазы

Написать полное тестирование и документацию:
- Unit тесты для всех компонентов
- Integration тесты для взаимодействия
- E2E тесты для полного flow
- Документация и примеры

#### Файлы для создания

**`acp-server/tests/test_agent_e2e.py`**

```python
"""E2E тесты для LLM агента."""

import pytest
from acp_server.protocol.core import ACPProtocol
from acp_server.storage.memory import InMemoryStorage
from acp_server.agent.orchestrator import AgentOrchestrator
from acp_server.agent.state import OrchestratorConfig
from acp_server.agent.naive_agent import NaiveAgent
from acp_server.llm.mock_provider import MockLLMProvider
from acp_server.tools.registry import SimpleToolRegistry
from acp_server.tools.base import ToolExecutionResult


@pytest.mark.asyncio
async def test_agent_full_flow():
    """Проверить полный flow обработки prompt через агента."""
    # Подготовить оркестратор с mock провайдером
    config = OrchestratorConfig(enabled=True, enable_tools=True)
    orchestrator = AgentOrchestrator(config)

    provider = MockLLMProvider(response="I'll help you with that")
    agent = NaiveAgent()
    registry = SimpleToolRegistry()

    # Регистрировать тестовый инструмент
    async def test_executor(session_id: str, args: dict):
        return ToolExecutionResult(success=True, output="Tool executed")

    registry.register_tool(
        name="test_tool",
        description="Test tool",
        parameters={"type": "object", "properties": {}},
        kind="other",
        executor=test_executor,
    )

    await orchestrator.initialize(provider, agent, registry)

    # Создать session state
    from acp_server.protocol.state import SessionState

    session = SessionState(
        session_id="test-session-1",
        client_name="test",
        client_version="1.0",
    )

    # Обработать несколько prompts
    for i in range(3):
        response = await orchestrator.handle_prompt(
            session,
            [{"text": f"Message {i}"}],
            {},
        )

        assert response.text == "I'll help you with that"

        # Проверить что история растет
        history = agent.get_session_history("test-session-1")
        assert len(history) > i  # История должна расти

    # Завершить сессию
    await orchestrator.end_session("test-session-1")

    # История должна быть очищена
    history = agent.get_session_history("test-session-1")
    assert len(history) == 0
```

**`doc/AGENT_USAGE_GUIDE.md`**

```markdown
# Руководство по использованию LLM агента в ACP Server

## Включение агента

Агент включается через переменные окружения:

```bash
export AGENT_ENABLED=true
export OPENAI_API_KEY=sk-...
export AGENT_MODEL=gpt-4o
```

## Конфигурация

### Переменные окружения

- `AGENT_ENABLED` - включить агента (true/false)
- `AGENT_LLM_PROVIDER` - провайдер (openai, mock)
- `AGENT_CLASS` - класс агента (naive)
- `OPENAI_API_KEY` - API ключ для OpenAI
- `AGENT_MODEL` - модель (gpt-4o, gpt-4-turbo, и т.д.)
- `AGENT_TEMPERATURE` - температура (0.0-1.0)
- `AGENT_MAX_TOKENS` - максимум токенов

### Примеры

```bash
# Разработка с mock провайдером
export AGENT_ENABLED=true
export AGENT_LLM_PROVIDER=mock

# Production с OpenAI
export AGENT_ENABLED=true
export AGENT_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export AGENT_MODEL=gpt-4o
export AGENT_TEMPERATURE=0.7
```

## Использование

При включении агента, все `session/prompt` запросы будут обработаны через LLM агента.

Если агент отключен, протокол работает как обычно (без LLM).

## Инструменты

Агент может использовать зарегистрированные инструменты для выполнения действий.

Встроенные инструменты:
- `echo` - echo инструмент для тестирования
- `info` - информация о сессии

## Отладка

Включить debug логирование:

```bash
export LOG_LEVEL=DEBUG
```
```

#### Файлы для модификации

- `acp-server/README.md` - добавить секцию про агента
- `README.md` (корневой) - добавить ссылку на документацию агента

#### Проверка фазы

```bash
make check
pytest acp-server/tests/test_agent_e2e.py -v
```

#### Критерии приемки

- [x] E2E тесты написаны и проходят
- [x] Документация по использованию написана
- [x] Примеры конфигурации предоставлены
- [x] `make check` без ошибок
- [x] Покрытие кода тестами >= 80% для agent/

---

### Фаза 8: Производство и мониторинг

#### Цель фазы

Подготовить агента к использованию в production:
- Обработка ошибок и edge cases
- Логирование и мониторинг
- Performance optimization
- Миграция существующих сессий

#### Важные файлы

**`acp-server/src/acp_server/agent/orchestrator.py`**

Добавить в handle_prompt:
- Timeout для обработки
- Retry логика при сбоях API
- Graceful fallback при ошибках

#### Тесты для фазы

```python
# tests/test_agent_error_handling.py
@pytest.mark.asyncio
async def test_orchestrator_api_failure():
    """Проверить обработку ошибок API."""
    from acp_server.llm.base import LLMProvider, LLMResponse

    class FailingProvider(LLMProvider):
        async def initialize(self, config):
            pass

        async def create_completion(self, messages, tools=None, **kwargs):
            raise Exception("API Error")

        async def stream_completion(self, messages, tools=None, **kwargs):
            raise Exception("API Error")
            yield  # Pylint

    # Провайдер должен логировать ошибку и вернуть fallback
```

#### Критерии приемки

- [x] Обработка ошибок API
- [x] Timeout обработка
- [x] Логирование всех операций
- [x] Performance метрики собираются
- [x] `make check` без ошибок

---

## Детализация кода

### Сигнатуры основных классов

#### LLMProvider

```python
class LLMProvider(ABC):
    async def initialize(self, config: dict[str, Any]) -> None: ...
    async def create_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse: ...
    async def stream_completion(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]: ...
```

#### LLMAgent

```python
class LLMAgent(ABC):
    async def initialize(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
    ) -> None: ...
    async def process_prompt(self, context: AgentContext) -> AgentResponse: ...
    async def cancel_prompt(self, session_id: str) -> None: ...
    def add_to_history(self, session_id: str, role: str, content: str) -> None: ...
    def get_session_history(self, session_id: str) -> list[LLMMessage]: ...
    async def end_session(self, session_id: str) -> None: ...
```

#### ToolRegistry

```python
class ToolRegistry(ABC):
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        kind: str,
        executor: Callable,
        requires_permission: bool = True,
    ) -> None: ...
    def get_available_tools(
        self,
        session_id: str,
        include_permission_required: bool = True,
    ) -> list[ToolDefinition]: ...
    def to_llm_tools(self, tools: list[ToolDefinition]) -> list[dict[str, Any]]: ...
    async def execute_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult: ...
```

#### AgentOrchestrator

```python
class AgentOrchestrator:
    def __init__(self, config: OrchestratorConfig): ...
    async def initialize(
        self,
        llm_provider: LLMProvider,
        agent: LLMAgent,
        tool_registry: ToolRegistry,
    ) -> None: ...
    async def handle_prompt(
        self,
        session_state: SessionState,
        prompt_content: list[dict[str, Any]],
        session_config: dict[str, Any],
    ) -> AgentResponse: ...
    async def handle_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]: ...
    async def cancel_prompt(self, session_id: str) -> None: ...
    async def end_session(self, session_id: str) -> None: ...
    def is_enabled(self) -> bool: ...
```

### Примеры использования

#### Инициализация агента в коде

```python
from acp_server.agent.orchestrator import AgentOrchestrator
from acp_server.agent.state import OrchestratorConfig
from acp_server.agent.naive_agent import NaiveAgent
from acp_server.llm.openai_provider import OpenAIProvider
from acp_server.tools.registry import SimpleToolRegistry

# Создать конфиг
config = OrchestratorConfig(
    enabled=True,
    model="gpt-4o",
    temperature=0.7,
)

# Создать компоненты
orchestrator = AgentOrchestrator(config)
provider = OpenAIProvider()
agent = NaiveAgent()
registry = SimpleToolRegistry()

# Инициализировать
await orchestrator.initialize(provider, agent, registry)

# Использовать
response = await orchestrator.handle_prompt(session_state, prompt, config)
```

#### Регистрация инструмента

```python
async def my_tool_executor(session_id: str, args: dict) -> ToolExecutionResult:
    """Выполнить мой инструмент."""
    result = args.get("param1")
    return ToolExecutionResult(success=True, output=f"Result: {result}")

registry.register_tool(
    name="my_tool",
    description="My custom tool",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter 1"},
        },
        "required": ["param1"],
    },
    kind="other",
    executor=my_tool_executor,
)
```

---

## План тестирования

### Unit тесты

**Per модуль:**
- `test_llm_base.py` - базовые типы данных
- `test_llm_openai_provider.py` - OpenAI провайдер (с mock API)
- `test_llm_mock_provider.py` - Mock провайдер
- `test_tool_registry.py` - Tool Registry
- `test_agent_base.py` - базовые типы AgentContext, AgentResponse
- `test_naive_agent.py` - NaiveAgent основной функционал
- `test_orchestrator.py` - AgentOrchestrator компоненты

**Структура:**
```
acp-server/tests/
├── test_agent_setup.py              # Фаза 0
├── test_agent_base.py               # Фаза 1
├── test_llm_provider.py             # Фаза 2
├── test_tool_registry.py            # Фаза 3
├── test_naive_agent.py              # Фаза 4
├── test_orchestrator.py             # Фаза 5
├── test_protocol_integration.py     # Фаза 6
├── test_agent_e2e.py                # Фаза 7
└── test_agent_error_handling.py     # Фаза 8
```

### Integration тесты

- Полная инициализация системы (provider + agent + registry)
- Обработка нескольких prompts в одной сессии
- Выполнение инструментов через оркестратор
- Управление историей при multiple turns

### E2E тесты

- Полный flow через ACPProtocol
- Несколько concurrent сессий
- Cancellation и error recovery
- Tool execution с результатами

### Test fixtures

```python
# tests/conftest.py
@pytest.fixture
async def orchestrator():
    """Готовый к использованию оркестратор."""
    config = OrchestratorConfig(enabled=True)
    orchestrator = AgentOrchestrator(config)
    
    provider = MockLLMProvider()
    agent = NaiveAgent()
    registry = SimpleToolRegistry()
    
    await orchestrator.initialize(provider, agent, registry)
    return orchestrator

@pytest.fixture
def session_state():
    """Пример SessionState."""
    from acp_server.protocol.state import SessionState
    return SessionState(
        session_id="test-1",
        client_name="test",
        client_version="1.0",
    )
```

### Coverage требования

- **Minimum coverage:** 80% для `agent/` модулей
- **Critical paths:** 100% для LLMAgent, AgentOrchestrator
- **Tools:** 90% для Tool Registry

---

## Миграционная стратегия

### Включение агента

**Способ 1: Переменная окружения**
```bash
export AGENT_ENABLED=true
```

**Способ 2: Конфигурационный файл**
```python
config = OrchestratorConfig(enabled=True, ...)
```

**Способ 3: Фича флаг (future)**
```python
if feature_flags.is_enabled("use_agent"):
    orchestrator.initialize(...)
```

### Отключение агента

Если возникли проблемы, агент быстро отключается:
```bash
export AGENT_ENABLED=false
```

Протокол автоматически fallback на текущее поведение.

### Переключение между провайдерами

```bash
# Разработка с Mock
export AGENT_LLM_PROVIDER=mock

# Production с OpenAI
export AGENT_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Будущее: добавить Anthropic, LLama, и т.д.
export AGENT_LLM_PROVIDER=anthropic
```

### Миграция существующих сессий

При обновлении с агентом:
1. Старые сессии продолжают работать без агента
2. Новые сессии автоматически используют агента
3. История старых сессий не теряется
4. `session/cancel` работает как для старых, так и новых

---

## Чеклист для разработчика

### Фаза 0: Подготовка

```bash
# Добавить зависимости
[ ] cd /Users/sergey/Projects/OpenIdeaLab/CodeLab/acp-protocol
[ ] uv add openai>=1.50.0 --directory acp-server
[ ] uv add python-dotenv>=1.0.0 --directory acp-server

# Создать структуру папок
[ ] mkdir -p acp-server/src/acp_server/agent
[ ] mkdir -p acp-server/src/acp_server/llm
[ ] mkdir -p acp-server/src/acp_server/tools

# Создать пустые файлы
[ ] touch acp-server/src/acp_server/agent/__init__.py
[ ] touch acp-server/src/acp_server/agent/base.py
[ ] touch acp-server/src/acp_server/agent/state.py
[ ] touch acp-server/src/acp_server/agent/naive_agent.py
[ ] touch acp-server/src/acp_server/agent/orchestrator.py
[ ] touch acp-server/src/acp_server/agent/config.py
[ ] touch acp-server/src/acp_server/llm/__init__.py
[ ] touch acp-server/src/acp_server/llm/base.py
[ ] touch acp-server/src/acp_server/llm/openai_provider.py
[ ] touch acp-server/src/acp_server/llm/mock_provider.py
[ ] touch acp-server/src/acp_server/tools/__init__.py
[ ] touch acp-server/src/acp_server/tools/base.py
[ ] touch acp-server/src/acp_server/tools/registry.py
[ ] touch acp-server/src/acp_server/tools/builtin_tools.py
[ ] touch acp-server/src/acp_server/tools/executor.py

# Проверка
[ ] make check
```

### Фаза 1: Интерфейсы

```bash
[ ] Реализовать llm/base.py (LLMProvider ABC)
[ ] Реализовать tools/base.py (ToolRegistry ABC)
[ ] Реализовать agent/base.py (LLMAgent ABC)
[ ] Реализовать agent/state.py (OrchestratorConfig)
[ ] Добавить экспорты в __init__.py
[ ] Написать unit тесты
[ ] make check
```

### Фаза 2: LLM провайдер

```bash
[ ] Реализовать llm/openai_provider.py
[ ] Реализовать llm/mock_provider.py
[ ] Написать unit тесты
[ ] Проверить что тесты не требуют реального API
[ ] make check
```

### Фаза 3: Tool Registry

```bash
[ ] Реализовать tools/registry.py (SimpleToolRegistry)
[ ] Реализовать tools/builtin_tools.py
[ ] Написать unit тесты
[ ] make check
```

### Фаза 4: Naive Agent

```bash
[ ] Реализовать agent/naive_agent.py
[ ] Написать unit тесты
[ ] Проверить управление историей
[ ] make check
```

### Фаза 5: Orchestrator

```bash
[ ] Реализовать agent/orchestrator.py
[ ] Реализовать agent/config.py
[ ] Написать unit и integration тесты
[ ] make check
```

### Фаза 6: Интеграция с протоколом

```bash
[ ] Модифицировать protocol/core.py (инициализация)
[ ] Модифицировать protocol/handlers/prompt.py (использование)
[ ] Добавить fallback при отключенном агенте
[ ] Написать integration тесты
[ ] make check
```

### Фаза 7: Тестирование и документация

```bash
[ ] Написать E2E тесты (test_agent_e2e.py)
[ ] Написать документацию (AGENT_USAGE_GUIDE.md)
[ ] Обновить README.md
[ ] Проверить покрытие кода (>=80%)
[ ] make check
[ ] pytest --cov=acp_server/agent acp-server/tests/
```

### Фаза 8: Производство

```bash
[ ] Добавить обработку ошибок (retry, timeout)
[ ] Добавить логирование
[ ] Написать тесты обработки ошибок
[ ] Оптимизировать performance
[ ] make check
```

---

## Возможные проблемы и решения

### 1. Конфликты зависимостей

**Проблема:** `openai>=1.50.0` конфликтует с существующей зависимостью

**Решение:**
```bash
# Проверить текущие зависимости
grep openai acp-server/pyproject.toml

# Обновить версию если нужно
uv sync --directory acp-server
```

### 2. Асинхронность и deadlocks

**Проблема:** При вызове `await` внутри non-async функции

**Решение:**
- Все методы взаимодействия с LLM/Registry должны быть `async`
- Использовать `asyncio.create_task()` для background работ
- Использовать `pytest.mark.asyncio` для async тестов

### 3. Tool Calls: Server-side vs Client-side

**Проблема:** Неправильное выполнение инструментов (сервер выполняет то что должен клиент)

**Решение (согласно ACP протоколу):**
```python
# Проверить тип инструмента
if executor is None:
    # Client-side инструмент - отправить session/update
    await protocol.notify_tool_call(session_id, tool_call)
else:
    # Server-side инструмент - выполнить на сервере
    result = await registry.execute_tool(session_id, tool_name, args)
```

**Client-side инструменты** (согласно ACP протоколу):
- `fs/read_text_file` - чтение файлов (09-File System.md)
- `fs/write_text_file` - запись файлов (09-File System.md)
- `terminal/create` - создание терминалов и выполнение команд (10-Terminal.md)
- Клиент вызывает соответствующие RPC методы на основе tool calls от LLM

**Server-side инструменты:**
- `echo`, `info`, `process_data` - логика на сервере
- Обращения к API, обработка данных, бизнес-логика

### 4. Управление состоянием

**Проблема:** История сообщений растет бесконечно

**Решение:**
```python
# Фиксировать лимит истории
if len(history) > config.history_limit:
    history = history[-config.history_limit:]
```

### 5. Обработка ошибок API

**Проблема:** OpenAI API может быть недоступен

**Решение:**
```python
try:
    response = await provider.create_completion(...)
except Exception as e:
    logger.error(f"API error: {e}")
    # Fallback на текущее поведение
    return AgentResponse(text="", tool_calls=[], stop_reason="error")
```

### 6. Разрешения на инструменты

**Проблема:** Пользователь не должен иметь доступ ко всем инструментам

**Решение (интеграция с Permission System):**
```python
# Проверить разрешения перед выполнением
if definition.requires_permission:
    # Запросить разрешение у клиента
    outcome = await protocol.request_permission(
        session_id,
        tool_name,
        arguments,
    )
    
    if outcome == "rejected":
        return ToolExecutionResult(success=False, error="Permission denied")
    
    # Выполнить инструмент если разрешено
    result = await registry.execute_tool(...)
```

### 7. Производительность

**Проблема:** Большая история замедляет обработку

**Решение:**
```python
# Ограничить историю по размеру/токенам
max_history = config.history_limit
if len(history) > max_history:
    # Сохранить system prompt + последние N сообщений
    history = [history[0]] + history[-(max_history-1):]
```

### 8. Синхронизация состояния между server и client

**Проблема:** Client выполнил инструмент, но сервер не знает результат

**Решение (session/update flow):**
```
1. Server отправляет tool_call через session/update (status: pending)
2. Client выполняет инструмент локально
3. Client отправляет tool_call_update (status: completed + output)
4. Server получает результат в session/update handler
5. Server добавляет результат в историю агента
6. Server может выполнить follow-up prompt если нужно
```

---

## Метрики успеха

### Критерии успешной реализации

#### 1. Корректность

- [x] Все unit тесты проходят (`make check`)
- [x] Покрытие кода >= 80% для `agent/`, `llm/`, `tools/`
- [x] Integration тесты проходят
- [x] E2E тесты проходят
- [x] Нет критических ошибок в лог-файлах

#### 2. Совместимость

- [x] Обратная совместимость сохранена (старый код работает без изменений)
- [x] Protocol работает без агента (fallback работает)
- [x] Существующие сессии не затронуты
- [x] Тесты из `acp-server/tests/` все еще проходят

#### 3. Производительность

- [x] Время ответа при отключенном агенте <= 10ms (как было)
- [x] Время ответа с агентом <= 2s (зависит от OpenAI)
- [x] Память на одну сессию <= 1MB (с историей)
- [x] Нет утечек памяти при long-running серверах

#### 4. Документация

- [x] NAIVE_AGENT_IMPLEMENTATION_PLAN.md полный и актуальный
- [x] AGENT_USAGE_GUIDE.md содержит примеры конфигурации
- [x] README.md обновлен со ссылкой на агента
- [x] Все docstrings имеют осмысленное содержание
- [x] Примеры использования работают

#### 5. DevOps

- [x] `make check` проходит без ошибок
- [x] `uv sync` работает корректно
- [x] `uv run pytest` все тесты проходят
- [x] Docker image собирается успешно (если используется)
- [x] Логирование struktured и информативное

---

## Диаграммы взаимодействия

### Архитектура системы

```
┌─────────────────────────────────────────────────────────────┐
│                    ACP Client                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ session/prompt request
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   HTTP/WebSocket                             │
│                 Transport Layer                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              ACPProtocol (core.py)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         AgentOrchestrator (опциональный)               │ │
│  │                                                        │ │
│  │  ┌──────────────┐  ┌────────────┐  ┌────────────────┐ │ │
│  │  │ LLMProvider  │  │ LLMAgent   │  │ ToolRegistry   │ │ │
│  │  │              │  │            │  │                │ │ │
│  │  │ OpenAI       │  │ Naive      │  │ Simple         │ │ │
│  │  │ Mock         │  │            │  │ (builtin tools)│ │ │
│  │  └──────────────┘  └────────────┘  └────────────────┘ │ │
│  │         │                 │                  │          │ │
│  │         └─────────────────┴──────────────────┘          │ │
│  │              Communication Flow                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Session/Prompt Handler                         │ │
│  │  1. Преобразовать ACP контекст в AgentContext         │ │
│  │  2. Вызвать orchestrator.handle_prompt()              │ │
│  │  3. Преобразовать AgentResponse в ACP результат      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  SessionState & Storage                      │
│             (保存历史, 权限, 配置)                           │
└─────────────────────────────────────────────────────────────┘
```

### Flow диаграмма обработки prompt с tool calls (согласно ACP)

```
User sends session/prompt
        │
        ▼
┌──────────────────────────────────────────┐
│ session_prompt() handler                 │
│ (protocol/handlers/prompt.py)            │
└──────────────────────────────────────────┘
        │
        ├─ Agent disabled?
        │  ├─ YES: fallback to default behavior
        │  └─ NO: continue
        │
        ▼
┌──────────────────────────────────────────┐
│ orchestrator.handle_prompt()             │
│ - Get available tools (server + client)  │
│ - Get session history                    │
│ - Create AgentContext                    │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ agent.process_prompt(context)            │
│ (NaiveAgent)                             │
│ - Add user message to history            │
│ - Prepare LLM tools (server + client)    │
└──────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│ llm_provider.create_completion()         │
│ (OpenAIProvider)                         │
│ - Send messages to OpenAI API            │
│ - Parse response (text + tool_calls)     │
└──────────────────────────────────────────┘
        │
        ├─ Has text response?
        │  └─ YES: Return in result content
        │
        ├─ Has tool calls?
        │  ├─ YES for server-side tool:
        │  │   └─ execute_tool() immediately
        │  │   └─ Add result to history
        │  │
        │  └─ YES for client-side tool:
        │      └─ Send session/update notification
        │      └─ Client executes locally
        │      └─ Client sends tool_call_update
        │      └─ Server receives in next prompt
        │
        ▼
┌──────────────────────────────────────────┐
│ Return response to client                │
│ - Text content (main result)             │
│ - session/update notif (tool_calls)      │
└──────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│ Client receives response                    │
│ ┌────────────────────────────────────────┐ │
│ │ Text result from LLM                   │ │
│ └────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────┐ │
│ │ session/update notifications:          │ │
│ │ - For each client-side tool call      │ │
│ │ - Client displays progress             │ │
│ │ - Client executes tool locally         │ │
│ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

### Sequence диаграмма tool execution (Server vs Client)

```
┌─────────────────┐        ┌──────────────┐    ┌─────────────┐    ┌────────────┐
│   ACP Client    │        │ ACPProtocol  │    │Orchestrator │    │Tool Registry
└─────────────────┘        └──────────────┘    └─────────────┘    └────────────┘
      │                           │                    │                 │
      │─ session/prompt ────────>│                    │                 │
      │                           │                    │                 │
      │                           │─ handle_prompt  ──>│                 │
      │                           │                    │                 │
      │                           │                    │─ get_available_tools
      │                           │                    │                ─>│
      │                           │                    │<─ tools ────────│
      │                           │                    │                 │
      │                           │                    │─ process_prompt │
      │                           │                    │  (LLM call)     │
      │                           │                    │                 │
      │                           │ Server-side tool?  │                 │
      │                           │ YES: execute_tool──>│                 │
      │                           │                    │─ execute_tool──>│
      │                           │                    │<─ result────────│
      │                           │<─ response─────────│                 │
      │<─ session/update────────│ (with tool_calls)  │                 │
      │ (client-side tools)     │                    │                 │
      │                           │                    │                 │
      │ Client executes          │                    │                 │
      │ tool locally             │                    │                 │
      │                           │                    │                 │
      │─ session/update────────>│ (tool_call_update) │                 │
      │ (tool result)            │                    │                 │
      │                           │                    │                 │
      │<─ session/update────────│ (status change)    │                 │
      │                           │                    │                 │
```

### Класс диаграмма основных компонентов

```
┌─────────────────────────────────────────────────────────────┐
│                      LLMProvider (ABC)                       │
├─────────────────────────────────────────────────────────────┤
│ + initialize(config)                                        │
│ + create_completion(messages, tools) -> LLMResponse        │
│ + stream_completion(messages, tools) -> AsyncIterator      │
└─────────────────────────────────────────────────────────────┘
         △                           △
         │                           │
         │                           │
    ┌────┴──────────┐         ┌──────┴─────────┐
    │ OpenAIProvider│         │ MockLLMProvider│
    └───────────────┘         └────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      LLMAgent (ABC)                          │
├─────────────────────────────────────────────────────────────┤
│ + initialize(provider, registry, config)                   │
│ + process_prompt(context) -> AgentResponse                │
│ + add_to_history(session_id, role, content)              │
│ + get_session_history(session_id) -> [LLMMessage]        │
│ + cancel_prompt(session_id)                              │
│ + end_session(session_id)                                │
└─────────────────────────────────────────────────────────────┘
         △
         │
    ┌────┴──────────┐
    │  NaiveAgent   │
    └───────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ToolRegistry (ABC)                        │
├─────────────────────────────────────────────────────────────┤
│ + register_tool(...)                                       │
│ + get_available_tools(session_id) -> [ToolDefinition]    │
│ + to_llm_tools(tools) -> [dict]                          │
│ + execute_tool(session_id, name, args) -> Result        │
└─────────────────────────────────────────────────────────────┘
         △
         │
    ┌────┴──────────────┐
    │ SimpleToolRegistry│
    └───────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   AgentOrchestrator                          │
├─────────────────────────────────────────────────────────────┤
│ - config: OrchestratorConfig                               │
│ - _llm_provider: LLMProvider                               │
│ - _agent: LLMAgent                                         │
│ - _tool_registry: ToolRegistry                             │
├─────────────────────────────────────────────────────────────┤
│ + initialize(provider, agent, registry)                   │
│ + handle_prompt(session, prompt, config) -> AgentResponse│
│ + handle_tool_execution(session_id, name, args) -> dict │
│ + is_enabled() -> bool                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Примеры конфигурации

### Разработка (с Mock провайдером)

```bash
#!/bin/bash
# .env.development

export AGENT_ENABLED=true
export AGENT_LLM_PROVIDER=mock
export AGENT_CLASS=naive
export AGENT_MODEL=gpt-4o
export AGENT_TEMPERATURE=0.7
export LOG_LEVEL=DEBUG
```

```bash
# Запуск
source .env.development
acp-server
```

### Production (с OpenAI)

```bash
#!/bin/bash
# .env.production

export AGENT_ENABLED=true
export AGENT_LLM_PROVIDER=openai
export AGENT_CLASS=naive
export OPENAI_API_KEY=sk-YOUR_KEY_HERE
export AGENT_MODEL=gpt-4o
export AGENT_TEMPERATURE=0.7
export AGENT_MAX_TOKENS=8192
export LOG_LEVEL=INFO
```

### Отключенный агент (fallback)

```bash
#!/bin/bash
# .env.disabled

export AGENT_ENABLED=false
```

---

## Ссылки и ресурсы

### Архитектура

- [`doc/NAIVE_AGENT_ARCHITECTURE.md`](../doc/NAIVE_AGENT_ARCHITECTURE.md) - Детальная архитектура
- [`AGENTS.md`](../AGENTS.md) - Правила для агентов
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) - Общая архитектура проекта

### OpenAI SDK

- [OpenAI Python SDK](https://github.com/openai/openai-python) - Документация и примеры
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference) - Справка по API

### Testing

- [pytest документация](https://docs.pytest.org/) - Framework для тестирования
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) - Поддержка async тестов

### Протокол

- [`doc/Agent Client Protocol/`](../doc/Agent%20Client%20Protocol/) - Спецификация ACP
- [`acp-server/README.md`](../acp-server/README.md) - Документация сервера

---

## История версий

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2026-04-09 | Architect | Начальный план |

---

## Заключение

Этот план реализации предоставляет четкий путь для интеграции LLM-агента в ACP Server с минимальной связанностью, полной обратной совместимостью и всесторонним тестированием.

Ключевые моменты:

1. **Модульность** - каждый компонент независим и тестируемый
2. **Простота** - NaiveAgent легко понять и модифицировать
3. **Безопасность** - fallback при ошибках, отключение через переменную окружения
4. **Расширяемость** - легко добавить новые LLM провайдеры и фреймворки
5. **Production-ready** - включает обработку ошибок, логирование, мониторинг

После завершения этого плана система будет готова к:
- Использованию в production
- Интеграции с другими сервисами
- Масштабированию и оптимизации
- Добавлению advanced функций (retry, caching, streaming и т.д.)
