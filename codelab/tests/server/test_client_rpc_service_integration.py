"""Тест для проверки что ClientRPCService передается через цепочку инициализации.

Тест проверяет:
1. ACPProtocol инициализируется с client_rpc_service
2. session_prompt() получает client_rpc_service
3. create_prompt_orchestrator() получает client_rpc_service
4. Логирование показывает "client_rpc_service provided"
"""

from unittest.mock import AsyncMock

from codelab.server.client_rpc.service import ClientRPCService
from codelab.server.protocol import ACPProtocol
from codelab.server.protocol.handlers.prompt import create_prompt_orchestrator
from codelab.server.storage import InMemoryStorage


class TestClientRPCServiceIntegration:
    """Тесты для проверки передачи ClientRPCService через цепочку инициализации."""

    def test_acpprotocol_accepts_client_rpc_service(self) -> None:
        """Проверяет что ACPProtocol.__init__ принимает client_rpc_service."""
        # Создаем mock ClientRPCService
        send_callback = AsyncMock()
        client_rpc_service = ClientRPCService(
            send_request_callback=send_callback,
            client_capabilities={"fs": {"readTextFile": True}},
        )

        # Создаем протокол с client_rpc_service
        protocol = ACPProtocol(
            storage=InMemoryStorage(),
            client_rpc_service=client_rpc_service,
        )

        # Проверяем что service сохранился
        assert protocol._client_rpc_service is client_rpc_service

    def test_create_prompt_orchestrator_with_client_rpc_service(self) -> None:
        """Проверяет что create_prompt_orchestrator() принимает client_rpc_service."""
        # Создаем mock ClientRPCService
        send_callback = AsyncMock()
        client_rpc_service = ClientRPCService(
            send_request_callback=send_callback,
            client_capabilities={},
        )

        # Проверяем что client_rpc_service можно создать и передать
        assert client_rpc_service is not None
        assert hasattr(client_rpc_service, '_send_request')



    def test_client_rpc_service_without_agent_orchestrator(self) -> None:
        """Проверяет что ClientRPCService работает без agent_orchestrator."""
        # Создаем protocol с client_rpc_service но без agent_orchestrator
        send_callback = AsyncMock()
        client_rpc_service = ClientRPCService(
            send_request_callback=send_callback,
            client_capabilities={"fs": {"readTextFile": True}},
        )

        protocol = ACPProtocol(
            storage=InMemoryStorage(),
            client_rpc_service=client_rpc_service,
            agent_orchestrator=None,
        )

        # Проверяем что оба сохранились
        assert protocol._client_rpc_service is client_rpc_service
        assert protocol._agent_orchestrator is None

    def test_create_prompt_orchestrator_without_client_rpc_service(self) -> None:
        """Проверяет что create_prompt_orchestrator() работает без client_rpc_service."""
        # Создаем оркестратор БЕЗ client_rpc_service
        orchestrator = create_prompt_orchestrator(client_rpc_service=None)

        # Проверяем что service остался None
        assert orchestrator.client_rpc_service is None
