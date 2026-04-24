"""Интеграционный тест для выполнения tool calls с SessionState."""

import pytest

from codelab.server.agent.base import AgentContext
from codelab.server.agent.naive import NaiveAgent
from codelab.server.llm.base import LLMResponse, LLMToolCall
from codelab.server.llm.mock_provider import MockLLMProvider
from codelab.server.protocol.state import SessionState
from codelab.server.tools.base import ToolDefinition
from codelab.server.tools.registry import SimpleToolRegistry


def echo_tool(text: str) -> str:
    """Echo инструмент для тестирования."""
    return f"Echo: {text}"


@pytest.fixture
def tool_registry() -> SimpleToolRegistry:
    """Создать реестр с тестовым инструментом."""
    registry = SimpleToolRegistry()
    
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
    
    return registry


@pytest.fixture
def session_state() -> SessionState:
    """Создать SessionState для интеграционного теста."""
    return SessionState(
        session_id="integration-test-session",
        cwd="/tmp",
        mcp_servers=[],
        title="Integration Test Session",
    )


@pytest.mark.asyncio
async def test_tool_execution_with_session_state(
    tool_registry: SimpleToolRegistry,
    session_state: SessionState,
) -> None:
    """Интеграционный тест передачи SessionState в AgentContext.
    
    Проверяет что:
    1. SessionState корректно передается в AgentContext
    2. AgentContext передается в process_prompt
    3. Агент делегирует tool calls в PromptOrchestrator (не выполняет их сам)
    """
    tool_call = LLMToolCall(
        id="call_1",
        name="echo",
        arguments={"text": "Hello from integration test"},
    )

    llm = MockLLMProvider(
        response="I'll echo the message",
        tool_calls=[tool_call],
    )
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    # Создать context с SessionState
    context = AgentContext(
        session_id="integration-test-session",
        session=session_state,  # Критически важно - SessionState передается
        prompt=[{"type": "text", "text": "Echo something"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    # Проверить что context содержит session
    assert context.session is session_state
    assert context.session.session_id == "integration-test-session"

    # Выполнить prompt с контекстом
    response = await agent.process_prompt(context)

    # Проверить результаты - агент делегирует tool calls в PromptOrchestrator
    assert response is not None
    assert response.text == "I'll echo the message"
    assert response.stop_reason == "tool_use"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "echo"
    assert response.metadata["iterations"] == 1


@pytest.mark.asyncio
async def test_multiple_tools_with_session_context(
    tool_registry: SimpleToolRegistry,
    session_state: SessionState,
) -> None:
    """Тест выполнения нескольких tool calls с SessionState в контексте."""
    
    tool_calls = [
        LLMToolCall(
            id="call_1",
            name="echo",
            arguments={"text": "First"},
        ),
        LLMToolCall(
            id="call_2",
            name="echo",
            arguments={"text": "Second"},
        ),
    ]

    llm = MockLLMProvider(
        response="Executed both tools",
        tool_calls=tool_calls,
    )

    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="integration-test-session",
        session=session_state,  # SessionState передается в context
        prompt=[{"type": "text", "text": "Execute multiple tools"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    # Проверить что session передан корректно
    assert context.session is session_state
    
    response = await agent.process_prompt(context)

    # Оба tool call должны быть обработаны
    assert response is not None
    assert response.metadata["iterations"] >= 1


@pytest.mark.asyncio
async def test_session_state_persistence_across_tool_calls(
    tool_registry: SimpleToolRegistry,
    session_state: SessionState,
) -> None:
    """Тест что SessionState остается одинаковым во время выполнения tool calls."""
    
    original_session_id = session_state.session_id
    original_cwd = session_state.cwd

    # Провайдер, который выполняет tool call
    class MultiCallProvider(MockLLMProvider):
        def __init__(self):
            super().__init__(response="Done")
            self.call_count = 0

        async def create_completion(self, messages, tools=None, **kwargs):
            self.call_count += 1
            if self.call_count == 1:
                tool_call = LLMToolCall(
                    id="call_1",
                    name="echo",
                    arguments={"text": "test"},
                )
                return LLMResponse(
                    text="Calling tool",
                    tool_calls=[tool_call],
                    stop_reason="tool_use",
                )
            else:
                return LLMResponse(
                    text="Finished",
                    tool_calls=[],
                    stop_reason="end_turn",
                )

    llm = MultiCallProvider()
    agent = NaiveAgent(llm=llm, tools=tool_registry)

    context = AgentContext(
        session_id="integration-test-session",
        session=session_state,
        prompt=[{"type": "text", "text": "Test"}],
        conversation_history=[],
        available_tools=tool_registry.list_tools(),
        config={},
    )

    response = await agent.process_prompt(context)

    # Проверить что SessionState остался неизменным
    assert context.session.session_id == original_session_id
    assert context.session.cwd == original_cwd
    assert response is not None
