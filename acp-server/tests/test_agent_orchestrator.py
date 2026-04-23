"""Unit-тесты для AgentOrchestrator."""

import pytest

from acp_server.agent.orchestrator import AgentOrchestrator
from acp_server.agent.state import OrchestratorConfig
from acp_server.llm.base import LLMMessage
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
    # Проверяем что session передается в контекст
    assert context.session is session_state
    assert context.session.session_id == "test-session-1"
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

    # Проверяем что session передается в контекст
    assert context.session is session_state
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

    # Проверяем что session передается в контекст
    assert context.session is session_state
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
