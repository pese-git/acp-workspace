"""Use Cases - бизнес-сценарии Application Layer.

Use Cases инкапсулируют бизнес-логику использования системы и оркестрируют
взаимодействие между Domain слоем и Infrastructure слоем.

Каждый Use Case отвечает за один бизнес-сценарий (Single Responsibility).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from acp_client.domain import Session, SessionRepository, TransportService

from .dto import (
    CreateSessionRequest,
    CreateSessionResponse,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionRequest,
    LoadSessionResponse,
    SendPromptRequest,
    SendPromptResponse,
)


class UseCase(ABC):
    """Базовый класс для всех Use Cases.
    
    Определяет общий интерфейс для выполнения use cases.
    """
    
    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Выполняет use case.
        
        Аргументы зависят от конкретного use case.
        """
        ...


class InitializeUseCase(UseCase):
    """Use Case для инициализации соединения с сервером.
    
    Отправляет метод 'initialize' и получает информацию о сервере.
    """
    
    def __init__(self, transport: TransportService) -> None:
        """Инициализирует use case.
        
        Аргументы:
            transport: TransportService для коммуникации
        """
        self._transport = transport
        self._logger = structlog.get_logger("initialize_use_case")
    
    async def execute(self) -> InitializeResponse:
        """Инициализирует соединение с сервером.
        
        Возвращает:
            InitializeResponse с информацией о сервере
        """
        # Подключаемся к серверу
        await self._transport.connect()
        self._logger.info("connected_to_server")
        
        # Отправляем initialize запрос
        # TODO: Реализовать через transport.send/receive
        # когда будет готова инфраструктура
        
        return InitializeResponse(
            server_capabilities={},
            available_auth_methods=[],
            protocol_version="1.0",
        )


class CreateSessionUseCase(UseCase):
    """Use Case для создания новой сессии.
    
    Создает новую сессию на сервере и сохраняет её в repository.
    """
    
    def __init__(
        self,
        transport: TransportService,
        session_repo: SessionRepository,
    ) -> None:
        """Инициализирует use case.
        
        Аргументы:
            transport: TransportService для коммуникации
            session_repo: SessionRepository для сохранения
        """
        self._transport = transport
        self._session_repo = session_repo
        self._logger = structlog.get_logger("create_session_use_case")
    
    async def execute(self, request: CreateSessionRequest) -> CreateSessionResponse:
        """Создает новую сессию.
        
        Аргументы:
            request: CreateSessionRequest с параметрами
        
        Возвращает:
            CreateSessionResponse с созданной сессией
        
        Raises:
            UseCaseError: При ошибке создания
        """
        self._logger.info(
            "creating_session",
            host=request.server_host,
            port=request.server_port,
        )
        
        # Создаем Session сущность
        session = Session.create(
            server_host=request.server_host,
            server_port=request.server_port,
            client_capabilities=request.client_capabilities or {},
            server_capabilities={},
        )
        
        # Сохраняем в repository
        await self._session_repo.save(session)
        
        self._logger.info("session_created", session_id=session.id)
        
        return CreateSessionResponse(
            session_id=session.id,
            server_capabilities=session.server_capabilities,
            is_authenticated=session.is_authenticated,
        )


class LoadSessionUseCase(UseCase):
    """Use Case для загрузки существующей сессии.
    
    Загружает сессию из repository и восстанавливает её состояние.
    """
    
    def __init__(
        self,
        transport: TransportService,
        session_repo: SessionRepository,
    ) -> None:
        """Инициализирует use case.
        
        Аргументы:
            transport: TransportService для коммуникации
            session_repo: SessionRepository для загрузки
        """
        self._transport = transport
        self._session_repo = session_repo
        self._logger = structlog.get_logger("load_session_use_case")
    
    async def execute(self, request: LoadSessionRequest) -> LoadSessionResponse:
        """Загружает существующую сессию.
        
        Аргументы:
            request: LoadSessionRequest с ID сессии
        
        Возвращает:
            LoadSessionResponse с загруженной сессией
        
        Raises:
            UseCaseError: При ошибке загрузки
        """
        self._logger.info("loading_session", session_id=request.session_id)
        
        # Загружаем из repository
        session = await self._session_repo.load(request.session_id)
        if session is None:
            self._logger.error("session_not_found", session_id=request.session_id)
            msg = f"Session {request.session_id} not found"
            raise ValueError(msg)
        
        self._logger.info("session_loaded", session_id=session.id)
        
        return LoadSessionResponse(
            session_id=session.id,
            server_capabilities=session.server_capabilities,
            is_authenticated=session.is_authenticated,
            replay_updates=[],
        )


class SendPromptUseCase(UseCase):
    """Use Case для отправки prompt в активную сессию.
    
    Отправляет prompt на сервер и обрабатывает ответ.
    """
    
    def __init__(
        self,
        transport: TransportService,
        session_repo: SessionRepository,
    ) -> None:
        """Инициализирует use case.
        
        Аргументы:
            transport: TransportService для коммуникации
            session_repo: SessionRepository для доступа к сессии
        """
        self._transport = transport
        self._session_repo = session_repo
        self._logger = structlog.get_logger("send_prompt_use_case")
    
    async def execute(self, request: SendPromptRequest) -> SendPromptResponse:
        """Отправляет prompt в сессию.
        
        Аргументы:
            request: SendPromptRequest с prompt и callbacks
        
        Возвращает:
            SendPromptResponse с результатом
        
        Raises:
            UseCaseError: При ошибке отправки
        """
        self._logger.info(
            "sending_prompt",
            session_id=request.session_id,
            prompt_length=len(request.prompt_text),
        )
        
        # Проверяем что сессия существует
        session = await self._session_repo.load(request.session_id)
        if session is None:
            self._logger.error("session_not_found", session_id=request.session_id)
            msg = f"Session {request.session_id} not found"
            raise ValueError(msg)
        
        # TODO: Реализовать отправку prompt через transport
        # когда будет готова инфраструктура
        
        self._logger.info("prompt_sent", session_id=request.session_id)
        
        return SendPromptResponse(
            session_id=request.session_id,
            prompt_result={},
            updates=[],
        )


class ListSessionsUseCase(UseCase):
    """Use Case для получения списка доступных сессий.
    
    Загружает список всех сессий из repository.
    """
    
    def __init__(self, session_repo: SessionRepository) -> None:
        """Инициализирует use case.
        
        Аргументы:
            session_repo: SessionRepository для доступа
        """
        self._session_repo = session_repo
        self._logger = structlog.get_logger("list_sessions_use_case")
    
    async def execute(self) -> ListSessionsResponse:
        """Получает список сессий.
        
        Возвращает:
            ListSessionsResponse со списком сессий
        """
        self._logger.info("listing_sessions")
        
        sessions = await self._session_repo.list_all()
        
        sessions_data = [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat(),
                "is_authenticated": s.is_authenticated,
                "server": f"{s.server_host}:{s.server_port}",
            }
            for s in sessions
        ]
        
        self._logger.info("sessions_listed", count=len(sessions_data))
        
        return ListSessionsResponse(sessions=sessions_data)
