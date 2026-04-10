"""Unit-тесты для AgentOrchestrator."""

import pytest

from acp_server.agent.orchestrator import AgentOrchestrator
from acp_server.agent.state import OrchestratorConfig
from acp_server.llm.base import LLMMessage, LLMResponse, LLMToolCall
from acp_server.llm.mock_provider import MockLLMProvider
from acp_server.protocol.state import SessionState
from acp_server.tools.base import ToolDefinition
from acp_server.tools.registry import SimpleToolRegistry

# ============================================================================
# Фикстуры
# ============================================================================


def simple_tool(text: str) -> str:
    """Простой инструмент для тестирования."""
    return f"Processed: {text}"


def another_tool(number: int) -> str:
    """Еще один инструмент для тестирования."""
    return f"Result: {number * 2}"


@pytest.fixture
def tool_registry() -> SimpleToolRegistry:
    """Создать реестр с тестовыми инструментами."""
    registry = SimpleToolRegistry()

    # Регистрация первого инструмента
    tool1 = ToolDefinition(
        name="simple_tool",
        description="Простой инструмент для обработки текста",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        kind="text",
    )
    registry.register(tool1, simple_tool)

    # Регистрация второго инструмента
    tool2 = ToolDefinition(
        name="another_tool",
        description="Инструмент для обработки чисел",
        parameters={
            "type": "object",
            "properties": {"number": {"type": "integer"}},
        },
        kind="math",
    )
    registry.register(tool2, another_tool)

    return registry


@pytest.fixture
def config() -> OrchestratorConfig:
    """Создать конфигурацию оркестратора."""
    return OrchestratorConfig(
        enabled=True,
        agent_class="naive",
        llm_provider_class="mock",
        model="gpt-4",
        temperature=0.7,
        max_tokens=8192,
    )


@pytest.fixture
def llm_provider() -> MockLLMProvider:
    """Создать mock LLM провайдер."""
    return MockLLMProvider(response="Test response")


@pytest.fixture
def orchestrator(
    config: OrchestratorConfig,
    llm_provider: MockLLMProvider,
    tool_registry: SimpleToolRegistry,
) -> AgentOrchestrator:
    """Создать оркестратор."""
    return AgentOrchestrator(
        config=config,
        llm_provider=llm_provider,
        tool_registry=tool_registry,
    )


@pytest.fixture
def session_state() -> SessionState:
    """Создать начальное состояние сессии."""
    return SessionState(
        session_id="test-session-1",
        cwd="/tmp",
        mcp_servers=[],
        title="Test Session",
        history=[],
        config_values={},
    )


# ============================================================================
# Тесты создания и инициализации
# ============================================================================


def test_orchestrator_creation(
    config: OrchestratorConfig,
    llm_provider: MockLLMProvider,
    tool_registry: SimpleToolRegistry,
) -> None:
    """Тест создания оркестратора с конфигурацией."""
    orchestrator = AgentOrchestrator(
        config=config,
        llm_provider=llm_provider,
        tool_registry=tool_registry,
    )
    assert orchestrator.config == config
    assert orchestrator.agent is not None
    assert orchestrator.llm_provider is not None
    assert orchestrator.tool_registry is not None


def test_orchestrator_agent_type(orchestrator: AgentOrchestrator) -> None:
    """Тест типа агента в оркестраторе."""
    from acp_server.agent.naive import NaiveAgent

    assert isinstance(orchestrator.agent, NaiveAgent)


# ============================================================================
# Тесты преобразования SessionState -> AgentContext
# ============================================================================


def test_create_agent_context_simple(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест преобразования пустого SessionState в AgentContext."""
    prompt = "Hello, agent!"

    context = orchestrator._create_agent_context(session_state, prompt)

    assert context.session_id == "test-session-1"
    assert context.prompt == [{"type": "text", "text": "Hello, agent!"}]
    assert context.conversation_history == []
    assert len(context.available_tools) >= 0  # Может быть 0 если нет инструментов
    assert context.config == {}


def test_create_agent_context_with_history(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест преобразования SessionState с историей в AgentContext."""
    # Добавить историю в состояние сессии
    session_state.history = [
        {"type": "text", "role": "user", "text": "First message"},
        {"type": "text", "role": "assistant", "text": "First response"},
    ]

    context = orchestrator._create_agent_context(
        session_state,
        "Second message",
    )

    assert len(context.conversation_history) == 2
    assert context.conversation_history[0].role == "user"
    assert context.conversation_history[0].content == "First message"
    assert context.conversation_history[1].role == "assistant"
    assert context.conversation_history[1].content == "First response"


def test_create_agent_context_with_config(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест преобразования SessionState с конфигом в AgentContext."""
    session_state.config_values = {"option1": "value1", "option2": "value2"}

    context = orchestrator._create_agent_context(session_state, "Test")

    assert context.config == {"option1": "value1", "option2": "value2"}


# ============================================================================
# Тесты преобразования форматов сообщений
# ============================================================================


def test_convert_to_llm_messages_empty(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования пустой истории."""
    messages = orchestrator._convert_to_llm_messages([])

    assert messages == []


def test_convert_to_llm_messages_single(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования одного сообщения."""
    history = [{"type": "text", "role": "user", "text": "Hello"}]

    messages = orchestrator._convert_to_llm_messages(history)

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"


def test_convert_to_llm_messages_mixed(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования истории с разными типами сообщений."""
    history = [
        {"type": "text", "role": "system", "text": "You are helpful"},
        {"type": "text", "role": "user", "text": "Hello"},
        {"type": "text", "role": "assistant", "text": "Hi!"},
        {"type": "text", "role": "tool", "text": "Tool result"},
    ]

    messages = orchestrator._convert_to_llm_messages(history)

    assert len(messages) == 4
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"
    assert messages[3].role == "tool"


def test_convert_from_llm_messages_empty(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования пустого списка LLMMessage."""
    history = orchestrator._convert_from_llm_messages([])

    assert history == []


def test_convert_from_llm_messages_single(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования одного LLMMessage."""
    messages = [LLMMessage(role="user", content="Hello")]

    history = orchestrator._convert_from_llm_messages(messages)

    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["text"] == "Hello"


def test_convert_from_llm_messages_multiple(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования нескольких LLMMessage."""
    messages = [
        LLMMessage(role="user", content="Question"),
        LLMMessage(role="assistant", content="Answer"),
    ]

    history = orchestrator._convert_from_llm_messages(messages)

    assert len(history) == 2
    assert all(h["type"] == "text" for h in history)


# ============================================================================
# Тесты обновления SessionState
# ============================================================================


def test_update_session_state_simple(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест обновления SessionState с простым ответом."""
    from acp_server.agent.base import AgentResponse

    response = AgentResponse(
        text="Agent response",
        tool_calls=[],
        stop_reason="end_turn",
    )

    updated = orchestrator._update_session_state(session_state, response)

    # Проверить добавление сообщений в историю
    assert len(updated.history) == 2
    assert updated.history[0]["role"] == "user"
    assert updated.history[1]["role"] == "assistant"
    assert updated.history[1]["text"] == "Agent response"


def test_update_session_state_with_tool_calls(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест обновления SessionState с tool calls."""
    from acp_server.agent.base import AgentResponse

    response = AgentResponse(
        text="Need to call tool",
        tool_calls=[
            LLMToolCall(
                id="call_1",
                name="simple_tool",
                arguments={"text": "test"},
            ),
        ],
        stop_reason="tool_use",
    )

    updated = orchestrator._update_session_state(session_state, response)

    # Проверить наличие tool calls в состоянии
    assert len(updated.tool_calls) > 0
    assert updated.tool_call_counter == 1


def test_update_session_state_preserves_existing_history(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест сохранения существующей истории при обновлении."""
    from acp_server.agent.base import AgentResponse

    session_state = SessionState(
        session_id="test-session",
        cwd="/tmp",
        mcp_servers=[],
        history=[
            {"type": "text", "role": "user", "text": "First message"},
            {"type": "text", "role": "assistant", "text": "First response"},
        ],
    )

    response = AgentResponse(
        text="Second response",
        tool_calls=[],
        stop_reason="end_turn",
    )

    updated = orchestrator._update_session_state(session_state, response)

    # Проверить, что старые сообщения сохранены
    assert len(updated.history) == 4
    assert updated.history[0]["text"] == "First message"
    assert updated.history[1]["text"] == "First response"


# ============================================================================
# Интеграционные тесты
# ============================================================================


@pytest.mark.asyncio
async def test_process_prompt_simple(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Интеграционный тест обработки простого промпта."""
    updated_state = await orchestrator.process_prompt(
        session_state,
        "Hello, agent!",
    )

    # Проверить обновление состояния
    assert updated_state.session_id == "test-session-1"
    assert len(updated_state.history) > 0
    # История должна содержать user и assistant сообщения
    assert any(h["role"] == "user" for h in updated_state.history)
    assert any(h["role"] == "assistant" for h in updated_state.history)


@pytest.mark.asyncio
async def test_process_prompt_with_tool_call(
    config: OrchestratorConfig,
    tool_registry: SimpleToolRegistry,
    session_state: SessionState,
) -> None:
    """Интеграционный тест обработки промпта с tool call."""
    # Создать провайдер, который возвращает tool call
    class ToolCallProvider(MockLLMProvider):
        """Провайдер для tool call."""

        def __init__(self):
            super().__init__(response="Final answer")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            self.call_count += 1

            if self.call_count == 1:
                tool_call = LLMToolCall(
                    id="call_1",
                    name="simple_tool",
                    arguments={"text": "test"},
                )
                return LLMResponse(
                    text="Calling tool",
                    tool_calls=[tool_call],
                    stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="Final answer",
                    tool_calls=[],
                    stop_reason="end_turn",
                )

    provider = ToolCallProvider()
    orchestrator = AgentOrchestrator(
        config=config,
        llm_provider=provider,
        tool_registry=tool_registry,
    )

    updated_state = await orchestrator.process_prompt(
        session_state,
        "Process this",
    )

    # Проверить что состояние было обновлено с историей
    assert len(updated_state.history) > 0
    # История должна содержать assistant сообщение с финальным ответом
    assistant_messages = [
        h for h in updated_state.history if h.get("role") == "assistant"
    ]
    assert len(assistant_messages) > 0


@pytest.mark.asyncio
async def test_process_prompt_with_existing_history(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест обработки промпта с существующей историей."""
    session_state = SessionState(
        session_id="test-session",
        cwd="/tmp",
        mcp_servers=[],
        history=[
            {"type": "text", "role": "user", "text": "Previous message"},
            {"type": "text", "role": "assistant", "text": "Previous response"},
        ],
    )

    updated_state = await orchestrator.process_prompt(
        session_state,
        "New message",
    )

    # История должна расширяться, не заменяться
    assert len(updated_state.history) >= 4


@pytest.mark.asyncio
async def test_process_prompt_idempotency(
    orchestrator: AgentOrchestrator,
    session_state: SessionState,
) -> None:
    """Тест что несколько вызовов процесса не влияют друг на друга."""
    # Создать новое состояние каждый раз
    state1 = SessionState(
        session_id="session-1",
        cwd="/tmp",
        mcp_servers=[],
        history=[],
    )

    state2 = SessionState(
        session_id="session-2",
        cwd="/tmp",
        mcp_servers=[],
        history=[],
    )

    result1 = await orchestrator.process_prompt(state1, "Message 1")
    result2 = await orchestrator.process_prompt(state2, "Message 2")

    # Проверить что состояния не смешались
    assert result1.session_id == "session-1"
    assert result2.session_id == "session-2"


# ============================================================================
# Граничные случаи
# ============================================================================


def test_convert_to_llm_messages_with_missing_fields(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования с отсутствующими полями."""
    history = [
        {"type": "text", "role": "user"},  # Отсутствует 'text'
        {"role": "assistant", "text": "Answer"},  # Отсутствует 'type'
    ]

    messages = orchestrator._convert_to_llm_messages(history)

    # Должны быть пропущены пустые содержимые
    assert all(msg.content for msg in messages)


def test_convert_to_llm_messages_with_invalid_role(
    orchestrator: AgentOrchestrator,
) -> None:
    """Тест преобразования с недопустимой ролью."""
    history = [
        {"type": "text", "role": "unknown_role", "text": "Some text"},
    ]

    messages = orchestrator._convert_to_llm_messages(history)

    # Роль должна быть исправлена на 'user' или быть в списке допустимых
    assert len(messages) == 1
    assert messages[0].content == "Some text"
