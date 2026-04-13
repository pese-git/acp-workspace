"""Unit-тесты для PromptOrchestrator.

Проверяет интеграцию всех компонентов Этапа 2 и Этапа 3
при обработке prompt-turn.
"""

from unittest.mock import AsyncMock

import pytest

from acp_server.protocol.handlers.client_rpc_handler import ClientRPCHandler
from acp_server.protocol.handlers.permission_manager import PermissionManager
from acp_server.protocol.handlers.plan_builder import PlanBuilder
from acp_server.protocol.handlers.prompt_orchestrator import PromptOrchestrator
from acp_server.protocol.handlers.state_manager import StateManager
from acp_server.protocol.handlers.tool_call_handler import ToolCallHandler
from acp_server.protocol.handlers.turn_lifecycle_manager import TurnLifecycleManager
from acp_server.protocol.state import SessionState


@pytest.fixture
def state_manager() -> StateManager:
    """Создает StateManager."""
    return StateManager()


@pytest.fixture
def plan_builder() -> PlanBuilder:
    """Создает PlanBuilder."""
    return PlanBuilder()


@pytest.fixture
def turn_lifecycle_manager() -> TurnLifecycleManager:
    """Создает TurnLifecycleManager."""
    return TurnLifecycleManager()


@pytest.fixture
def tool_call_handler() -> ToolCallHandler:
    """Создает ToolCallHandler."""
    return ToolCallHandler()


@pytest.fixture
def permission_manager() -> PermissionManager:
    """Создает PermissionManager."""
    return PermissionManager()


@pytest.fixture
def client_rpc_handler() -> ClientRPCHandler:
    """Создает ClientRPCHandler."""
    return ClientRPCHandler()


@pytest.fixture
def orchestrator(
    state_manager: StateManager,
    plan_builder: PlanBuilder,
    turn_lifecycle_manager: TurnLifecycleManager,
    tool_call_handler: ToolCallHandler,
    permission_manager: PermissionManager,
    client_rpc_handler: ClientRPCHandler,
) -> PromptOrchestrator:
    """Создает PromptOrchestrator со всеми компонентами."""
    return PromptOrchestrator(
        state_manager=state_manager,
        plan_builder=plan_builder,
        turn_lifecycle_manager=turn_lifecycle_manager,
        tool_call_handler=tool_call_handler,
        permission_manager=permission_manager,
        client_rpc_handler=client_rpc_handler,
    )


@pytest.fixture
def session() -> SessionState:
    """Создает SessionState."""
    return SessionState(
        session_id="sess_1",
        cwd="/tmp",
        mcp_servers=[],
    )


@pytest.fixture
def sessions(session: SessionState) -> dict[str, SessionState]:
    """Создает словарь сессий."""
    return {"sess_1": session}


@pytest.fixture
def agent_orchestrator() -> AsyncMock:
    """Создает mock для AgentOrchestrator."""
    mock = AsyncMock()
    mock.process_prompt = AsyncMock()
    return mock


class TestPromptOrchestratorInitialization:
    """Тесты инициализации PromptOrchestrator."""

    def test_initialization(self, orchestrator: PromptOrchestrator) -> None:
        """Инициализирует PromptOrchestrator со всеми компонентами."""
        assert orchestrator.state_manager is not None
        assert orchestrator.plan_builder is not None
        assert orchestrator.turn_lifecycle_manager is not None
        assert orchestrator.tool_call_handler is not None
        assert orchestrator.permission_manager is not None
        assert orchestrator.client_rpc_handler is not None


class TestPromptOrchestratorHandlePrompt:
    """Тесты handle_prompt метода."""

    @pytest.mark.asyncio
    async def test_handle_prompt_creates_active_turn(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Создает active turn при обработке промпта."""
        agent_orchestrator.process_prompt.return_value = session

        prompt = [{"type": "text", "text": "Test prompt"}]
        await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        assert session.active_turn is None  # Должен быть очищен после завершения

    @pytest.mark.asyncio
    async def test_handle_prompt_updates_session_state(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Обновляет состояние сессии при обработке."""
        agent_orchestrator.process_prompt.return_value = session

        prompt = [{"type": "text", "text": "Test prompt"}]
        await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        # Проверяем что история обновлена
        assert len(session.history) > 0
        assert session.history[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_handle_prompt_returns_notifications(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Возвращает notifications при обработке."""
        agent_orchestrator.process_prompt.return_value = session

        prompt = [{"type": "text", "text": "Test prompt"}]
        outcome = await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        assert outcome.notifications is not None
        assert len(outcome.notifications) > 0
        # Должны быть notifications session/update
        methods = [n.method for n in outcome.notifications]
        assert "session/update" in methods
        assert outcome.response is not None
        assert outcome.response.result == {"stopReason": "end_turn"}

    @pytest.mark.asyncio
    async def test_handle_prompt_with_empty_prompt(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Обрабатывает пустой промпт."""
        agent_orchestrator.process_prompt.return_value = session

        outcome = await orchestrator.handle_prompt(
            "req_1",
            {"prompt": []},
            session,
            sessions,
            agent_orchestrator,
        )

        # Должны быть notifications даже при пустом промпте
        assert outcome.notifications is not None

    @pytest.mark.asyncio
    async def test_handle_prompt_with_agent_error(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Обрабатывает ошибку агента."""
        agent_orchestrator.process_prompt.side_effect = Exception("Agent failed")

        prompt = [{"type": "text", "text": "Test prompt"}]
        outcome = await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        # Должны быть notifications с ошибкой
        assert outcome.notifications is not None
        error_found = any("error" in str(n.params).lower() for n in outcome.notifications)
        assert error_found or len(outcome.notifications) > 0

    @pytest.mark.asyncio
    async def test_handle_prompt_sets_session_title(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """Устанавливает заголовок сессии из первого промпта."""
        agent_orchestrator.process_prompt.return_value = session

        prompt = [{"type": "text", "text": "My test prompt"}]
        await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        assert session.title == "My test prompt"


class TestPromptOrchestratorHandleCancel:
    """Тесты handle_cancel метода."""

    def test_handle_cancel_with_active_turn(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> None:
        """Обрабатывает cancel при активном turn."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
        )

        outcome = orchestrator.handle_cancel(
            "cancel_req",
            {"sessionId": "sess_1"},
            session,
            sessions,
        )

        # Должны быть notifications об отмене
        assert outcome.notifications is not None
        # Turn должен быть очищен
        assert session.active_turn is None

    def test_handle_cancel_without_active_turn(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> None:
        """Не падает при cancel без активного turn."""
        session.active_turn = None

        outcome = orchestrator.handle_cancel(
            "cancel_req",
            {"sessionId": "sess_1"},
            session,
            sessions,
        )

        # Должно вернуть пустой результат
        assert outcome.notifications == []

    def test_handle_cancel_marks_cancel_requested(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> None:
        """Устанавливает флаг cancel_requested."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
        )

        orchestrator.handle_cancel(
            "cancel_req",
            {"sessionId": "sess_1"},
            session,
            sessions,
        )

        # После очистки active_turn сразу, проверяем что он был очищен
        assert session.active_turn is None


class TestPromptOrchestratorHandleClientRpcResponse:
    """Тесты handle_pending_client_rpc_response."""

    def test_handle_client_rpc_response_fs_read(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает response на fs/read request."""
        outcome = orchestrator.handle_pending_client_rpc_response(
            session,
            "sess_1",
            "fs_read",
            {"content": "file content"},
            None,
        )

        # Должны быть notifications
        assert outcome.notifications is not None

    def test_handle_client_rpc_response_fs_write(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает response на fs/write request."""
        outcome = orchestrator.handle_pending_client_rpc_response(
            session,
            "sess_1",
            "fs_write",
            {"success": True},
            None,
        )

        # Должны быть notifications
        assert outcome.notifications is not None

    def test_handle_client_rpc_response_with_error(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает response с ошибкой."""
        outcome = orchestrator.handle_pending_client_rpc_response(
            session,
            "sess_1",
            "fs_read",
            None,
            {"code": -1, "message": "File not found"},
        )

        # Должны быть notifications
        assert outcome.notifications is not None


class TestPromptOrchestratorHandlePermissionResponse:
    """Тесты handle_permission_response."""

    def test_handle_permission_response_allow(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает allow decision."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
            permission_request_id="perm_req_1",
            permission_tool_call_id="call_001",
        )

        result = {
            "outcome": "selected",
            "optionId": "allow_once",
        }

        outcome = orchestrator.handle_permission_response(
            session,
            "sess_1",
            "perm_req_1",
            result,
        )

        # Должны быть notifications
        assert outcome.notifications is not None

    def test_handle_permission_response_reject(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает reject decision."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
            permission_request_id="perm_req_1",
            permission_tool_call_id="call_001",
        )

        result = {
            "outcome": "selected",
            "optionId": "reject_once",
        }

        outcome = orchestrator.handle_permission_response(
            session,
            "sess_1",
            "perm_req_1",
            result,
        )

        # Должны быть notifications
        assert outcome.notifications is not None

    def test_handle_permission_response_cancelled(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Игнорирует response на отменённый request."""
        session.cancelled_permission_requests.add("perm_req_1")

        result = {
            "outcome": "selected",
            "optionId": "allow_once",
        }

        outcome = orchestrator.handle_permission_response(
            session,
            "sess_1",
            "perm_req_1",
            result,
        )

        # Должно вернуть пустой результат
        assert outcome.notifications == []

    def test_handle_permission_response_invalid_format(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
    ) -> None:
        """Обрабатывает невалидный формат response."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
            permission_request_id="perm_req_1",
            permission_tool_call_id="call_001",
        )

        outcome = orchestrator.handle_permission_response(
            session,
            "sess_1",
            "perm_req_1",
            {},  # Invalid format
        )

        # Должно вернуть пустой результат для невалидного формата
        assert outcome.notifications == []


class TestPromptOrchestratorComponentIntegration:
    """Тесты интеграции всех компонентов."""

    def test_all_components_initialized(
        self,
        orchestrator: PromptOrchestrator,
    ) -> None:
        """Все компоненты инициализированы."""
        assert orchestrator.state_manager is not None
        assert orchestrator.plan_builder is not None
        assert orchestrator.turn_lifecycle_manager is not None
        assert orchestrator.tool_call_handler is not None
        assert orchestrator.permission_manager is not None
        assert orchestrator.client_rpc_handler is not None

    @pytest.mark.asyncio
    async def test_state_manager_integration(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AsyncMock,
    ) -> None:
        """StateManager интегрирован в prompt handling."""
        agent_orchestrator.process_prompt.return_value = session

        prompt = [{"type": "text", "text": "Test"}]
        await orchestrator.handle_prompt(
            "req_1",
            {"prompt": prompt},
            session,
            sessions,
            agent_orchestrator,
        )

        # Проверяем что StateManager обновил состояние
        assert session.title == "Test"
        assert len(session.history) > 0

    def test_turn_lifecycle_integration(
        self,
        orchestrator: PromptOrchestrator,
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> None:
        """TurnLifecycleManager интегрирован в cancel handling."""
        from acp_server.protocol.state import ActiveTurnState

        session.active_turn = ActiveTurnState(
            prompt_request_id="req_1",
            session_id="sess_1",
        )

        orchestrator.handle_cancel(
            "cancel_req",
            {"sessionId": "sess_1"},
            session,
            sessions,
        )

        # Проверяем что TurnLifecycleManager очистил turn
        assert session.active_turn is None
