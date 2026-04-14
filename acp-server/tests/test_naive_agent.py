"""Unit-тесты для NaiveAgent."""

import pytest

from acp_server.agent.base import AgentContext
from acp_server.agent.naive import NaiveAgent
from acp_server.llm.base import LLMMessage, LLMToolCall
from acp_server.llm.mock_provider import MockLLMProvider
from acp_server.tools.base import ToolDefinition
from acp_server.tools.registry import SimpleToolRegistry

# ============================================================================
# Фикстуры с тестовыми инструментами
# ============================================================================


def simple_calculator(operation: str, a: float, b: float) -> float:
    """Простой калькулятор для тестирования."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Деление на ноль")
        return a / b
    else:
        raise ValueError(f"Неизвестная операция: {operation}")


def echo_tool(text: str) -> str:
    """Echo инструмент для тестирования."""
    return f"Echo: {text}"


def error_tool() -> None:
    """Инструмент, который всегда выбрасывает ошибку."""
    raise RuntimeError("Это тестовая ошибка")


@pytest.fixture
def tool_registry() -> SimpleToolRegistry:
    """Создать реестр с тестовыми инструментами."""
    registry = SimpleToolRegistry()

    # Регистрация калькулятора
    calc_tool = ToolDefinition(
        name="calculator",
        description="Выполняет базовые математические операции",
        parameters={
            "type": "object",
            "properties": {
                "operation": {"type": "string"},
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
        },
        kind="math",
    )
    registry.register(calc_tool, simple_calculator)

    # Регистрация echo инструмента
    echo_def = ToolDefinition(
        name="echo",
        description="Возвращает переданный текст",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        kind="other",
    )
    registry.register(echo_def, echo_tool)

    # Регистрация error инструмента
    error_def = ToolDefinition(
        name="error_tool",
        description="Инструмент, который выбрасывает ошибку",
        parameters={"type": "object", "properties": {}},
        kind="other",
    )
    registry.register(error_def, error_tool)

    return registry


@pytest.fixture
def naive_agent(tool_registry: SimpleToolRegistry) -> NaiveAgent:
    """Создать NaiveAgent с mock LLM провайдером."""
    llm = MockLLMProvider(response="Test response")
    return NaiveAgent(llm=llm, tools=tool_registry, max_iterations=5)


# ============================================================================
# Базовые тесты
# ============================================================================


@pytest.mark.asyncio
async def test_simple_response_without_tool_calls(
    naive_agent: NaiveAgent,
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест простого ответа без tool calls."""
    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Hello, agent!"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await naive_agent.process_prompt(context)

    assert response.text == "Test response"
    assert response.tool_calls == []
    assert response.stop_reason == "end_turn"


@pytest.mark.asyncio
async def test_single_tool_call_success(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест успешного выполнения одного tool call."""

    # Создать провайдер, который возвращает tool call в первый раз,
    # потом финальный ответ
    class SingleToolCallProvider(MockLLMProvider):
        """Провайдер для одного tool call."""

        def __init__(self):
            super().__init__(response="Final answer")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            from acp_server.llm.base import LLMResponse

            self.call_count += 1

            if self.call_count == 1:
                tool_call = LLMToolCall(
                    id="call_1",
                    name="calculator",
                    arguments={"operation": "add", "a": 2, "b": 3},
                )
                return LLMResponse(
                    text="I need to calculate 2 + 3",
                    tool_calls=[tool_call],
                    stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="The result is 5",
                    tool_calls=[],
                    stop_reason="end_turn",
                )

    llm = SingleToolCallProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Calculate 2 + 3"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # После выполнения tool, агент должен вернуть финальный ответ
    assert response.stop_reason == "end_turn"
    assert response.text == "The result is 5"
    assert response.metadata["iterations"] >= 2


@pytest.mark.asyncio
async def test_multiple_tool_calls_in_single_response(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест нескольких tool calls в одном ответе."""
    tool_calls = [
        LLMToolCall(
            id="call_1",
            name="echo",
            arguments={"text": "Hello"},
        ),
        LLMToolCall(
            id="call_2",
            name="echo",
            arguments={"text": "World"},
        ),
    ]

    llm = MockLLMProvider(
        response="I'll echo both texts",
        tool_calls=tool_calls,
    )

    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Echo hello and world"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # Агент должен обработать оба tool calls
    assert response is not None
    assert response.metadata["iterations"] >= 1


# ============================================================================
# Тесты с цепочками tool calls
# ============================================================================


@pytest.mark.asyncio
async def test_tool_call_chain(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест цепочки tool calls (tool -> response -> tool -> response)."""

    # После выполнения первого tool, LLM должен вернуть второй
    # Для этого создаем специальный провайдер, который ведет себя по-разному
    # при повторных вызовах
    class ChainedMockLLMProvider(MockLLMProvider):
        """Mock провайдер для тестирования цепочек."""

        def __init__(self) -> None:
            super().__init__(response="Final answer")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            """Вернуть разные ответы в зависимости от количества вызовов."""
            self.call_count += 1

            if self.call_count == 1:
                # Первый вызов - вернуть tool call
                return self._get_response_with_tool_call()
            else:
                # Последующие вызовы - вернуть финальный ответ
                return self._get_final_response()

        def _get_response_with_tool_call(self):
            """Вернуть ответ с tool call."""
            from acp_server.llm.base import LLMResponse

            tool_call = LLMToolCall(
                id="call_1",
                name="calculator",
                arguments={"operation": "add", "a": 5, "b": 3},
            )
            return LLMResponse(
                text="I'll calculate 5 + 3",
                tool_calls=[tool_call],
                stop_reason="tool_use",
            )

        def _get_final_response(self):
            """Вернуть финальный ответ."""
            from acp_server.llm.base import LLMResponse

            return LLMResponse(
                text="The result is 8",
                tool_calls=[],
                stop_reason="end_turn",
            )

    llm = ChainedMockLLMProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Calculate 5 + 3 and tell me the result"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # Агент должен выполнить tool и вернуть финальный ответ
    assert response.text == "The result is 8"
    assert response.metadata["iterations"] >= 2


# ============================================================================
# Тесты обработки ошибок
# ============================================================================


@pytest.mark.asyncio
async def test_max_iterations_exceeded(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест достижения максимума итераций."""

    # Создать провайдер, который всегда возвращает tool calls
    class InfiniteToolCallProvider(MockLLMProvider):
        """Провайдер, который бесконечно возвращает tool calls."""

        async def create_completion(self, messages, tools=None, **kwargs):
            from acp_server.llm.base import LLMResponse

            tool_call = LLMToolCall(
                id="call_1",
                name="echo",
                arguments={"text": "loop"},
            )
            return LLMResponse(
                text="Continuing...",
                tool_calls=[tool_call],
                stop_reason="tool_use",
            )

    llm = InfiniteToolCallProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry, max_iterations=3)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Loop forever"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # Должен вернуть ошибку max_iterations
    assert response.stop_reason == "max_iterations"
    assert response.metadata["iterations"] == 3


@pytest.mark.asyncio
async def test_tool_not_found(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест вызова несуществующего инструмента."""
    tool_call = LLMToolCall(
        id="call_1",
        name="nonexistent_tool",
        arguments={},
    )

    llm = MockLLMProvider(
        response="Using nonexistent tool",
        tool_calls=[tool_call],
    )

    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Use nonexistent tool"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # Агент должен обработать ошибку и вернуть ответ
    assert response is not None


@pytest.mark.asyncio
async def test_tool_execution_error(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест обработки исключения при выполнении инструмента."""

    # После выполнения tool с ошибкой, LLM должен вернуть финальный ответ
    class ErrorHandlingProvider(MockLLMProvider):
        """Провайдер для обработки ошибок."""

        def __init__(self):
            super().__init__(response="Final answer")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            from acp_server.llm.base import LLMResponse

            self.call_count += 1

            if self.call_count == 1:
                tool_call = LLMToolCall(
                    id="call_1",
                    name="error_tool",
                    arguments={},
                )
                return LLMResponse(
                    text="Calling error tool",
                    tool_calls=[tool_call],
                    stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="Tool failed, but I'll continue",
                    tool_calls=[],
                    stop_reason="end_turn",
                )

    llm = ErrorHandlingProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Call error tool"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    assert response is not None
    assert response.metadata["iterations"] >= 2


# ============================================================================
# Тесты с историей и контекстом
# ============================================================================


@pytest.mark.asyncio
async def test_empty_prompt(
    naive_agent: NaiveAgent,
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест с пустым промптом."""
    context = AgentContext(
        session_id="test-session",
        prompt=[],  # Пустой промпт
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await naive_agent.process_prompt(context)

    assert response is not None
    assert response.text == "Test response"


@pytest.mark.asyncio
async def test_with_conversation_history(
    naive_agent: NaiveAgent,
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест с историей предыдущих сообщений."""
    history = [
        LLMMessage(role="user", content="First message"),
        LLMMessage(role="assistant", content="First response"),
    ]

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "Second message"}],
        conversation_history=history,
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await naive_agent.process_prompt(context)

    assert response is not None
    assert response.text == "Test response"


# ============================================================================
# Тесты управления историей сессии
# ============================================================================


@pytest.mark.asyncio
async def test_add_to_history(
    naive_agent: NaiveAgent,
) -> None:
    """Тест добавления сообщений в историю."""
    session_id = "test-session"

    naive_agent.add_to_history(session_id, "user", "Hello")
    naive_agent.add_to_history(session_id, "assistant", "Hi there")

    history = naive_agent.get_session_history(session_id)

    assert len(history) == 2
    assert history[0].role == "user"
    assert history[0].content == "Hello"
    assert history[1].role == "assistant"
    assert history[1].content == "Hi there"


@pytest.mark.asyncio
async def test_end_session(
    naive_agent: NaiveAgent,
) -> None:
    """Тест завершения сессии и очистки истории."""
    session_id = "test-session"

    # Добавить сообщения
    naive_agent.add_to_history(session_id, "user", "Hello")
    assert len(naive_agent.get_session_history(session_id)) == 1

    # Завершить сессию
    await naive_agent.end_session(session_id)

    # История должна быть пустой
    assert len(naive_agent.get_session_history(session_id)) == 0


# ============================================================================
# Тесты инициализации
# ============================================================================


@pytest.mark.asyncio
async def test_initialize_agent(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест инициализации агента."""
    llm = MockLLMProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    new_llm = MockLLMProvider(response="New response")
    new_tools = SimpleToolRegistry()

    await agent.initialize(new_llm, new_tools, {})

    # Убедиться, что зависимости обновлены
    assert agent.llm is new_llm
    assert agent.tools is new_tools


# ============================================================================
# Тесты форматирования промпта
# ============================================================================


@pytest.mark.asyncio
async def test_format_prompt_with_multiple_blocks(
    naive_agent: NaiveAgent,
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест форматирования промпта с несколькими блоками."""
    context = AgentContext(
        session_id="test-session",
        prompt=[
            {"type": "text", "text": "Hello "},
            {"type": "text", "text": "World"},
        ],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await naive_agent.process_prompt(context)

    assert response is not None
    # Проверить, что промпт был правильно объединен
    assert response.text == "Test response"


# ============================================================================
# Интеграционные тесты
# ============================================================================


@pytest.mark.asyncio
async def test_integration_with_mock_provider(
    tool_registry: SimpleToolRegistry,
) -> None:
    """Интеграционный тест с MockLLMProvider."""

    # Создать провайдер, который выполняет две операции
    class IntegrationMockProvider(MockLLMProvider):
        """Mock провайдер для интеграционного теста."""

        def __init__(self):
            super().__init__(response="Calculation complete")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            from acp_server.llm.base import LLMResponse

            self.call_count += 1

            if self.call_count == 1:
                # Первый вызов - запрос калькулятора
                tool_call = LLMToolCall(
                    id="call_1",
                    name="calculator",
                    arguments={"operation": "multiply", "a": 7, "b": 6},
                )
                return LLMResponse(
                    text="I need to calculate 7 * 6",
                    tool_calls=[tool_call],
                    stop_reason="tool_use",
                )
            else:
                # Второй вызов - финальный ответ
                return LLMResponse(
                    text="The answer is 42",
                    tool_calls=[],
                    stop_reason="end_turn",
                )

    llm = IntegrationMockProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="test-session",
        prompt=[{"type": "text", "text": "What is 7 * 6?"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    assert response.text == "The answer is 42"
    assert response.stop_reason == "end_turn"
    assert response.metadata["iterations"] >= 2
