"""SessionCoordinator - оркестрация операций с сессиями.

Координирует взаимодействие между Application и Infrastructure слоями
для управления жизненным циклом сессии и выполнения операций.
"""

from __future__ import annotations

from typing import Any

import structlog

from acp_client.domain import SessionRepository, TransportService
from acp_client.infrastructure.logging_config import get_logger

from .use_cases import (
    CreateSessionUseCase,
    InitializeUseCase,
    ListSessionsUseCase,
    LoadSessionUseCase,
    SendPromptUseCase,
)


class SessionCoordinator:
    """Оркестратор для операций с сессиями.
    
    Предоставляет удобный интерфейс для работы с сессиями,
    инкапсулируя использование use cases и управление зависимостями.
    """
    
    def __init__(
        self,
        transport: TransportService,
        session_repo: SessionRepository,
    ) -> None:
        """Инициализирует координатор.
        
        Аргументы:
            transport: TransportService для коммуникации
            session_repo: SessionRepository для хранения
        """
        self.transport = transport
        self.session_repo = session_repo
        self._logger = get_logger("session_coordinator")
        
        # Инициализируем use cases
        self.initialize_use_case = InitializeUseCase(transport)
        self.create_session_use_case = CreateSessionUseCase(transport, session_repo)
        self.load_session_use_case = LoadSessionUseCase(transport, session_repo)
        self.send_prompt_use_case = SendPromptUseCase(transport, session_repo)
        self.list_sessions_use_case = ListSessionsUseCase(session_repo)
    
    async def initialize(self) -> dict[str, Any]:
        """Инициализирует соединение с сервером.
        
        Возвращает:
            Информацию о сервере и его capabilities
        """
        self._logger.info("initializing_connection")
        response = await self.initialize_use_case.execute()
        return {
            "server_capabilities": response.server_capabilities,
            "available_auth_methods": response.available_auth_methods,
            "protocol_version": response.protocol_version,
        }
    
    async def create_session(
        self,
        server_host: str,
        server_port: int,
        client_capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Создает новую сессию на сервере.
        
        Аргументы:
            server_host: Адрес сервера
            server_port: Порт сервера
            client_capabilities: Возможности клиента (опционально)
        
        Возвращает:
            Объект созданной сессии с ID и capabilities
        """
        from .dto import CreateSessionRequest
        
        request = CreateSessionRequest(
            server_host=server_host,
            server_port=server_port,
            client_capabilities=client_capabilities,
        )
        
        self._logger.info("creating_session", host=server_host, port=server_port)
        response = await self.create_session_use_case.execute(request)
        
        return {
            "session_id": response.session_id,
            "server_capabilities": response.server_capabilities,
            "is_authenticated": response.is_authenticated,
        }
    
    async def list_sessions(self) -> list[dict[str, Any]]:
        """Получает список всех доступных сессий.
        
        Возвращает:
            Список сессий с метаданными
        """
        self._logger.info("listing_sessions")
        response = await self.list_sessions_use_case.execute()
        return response.sessions
