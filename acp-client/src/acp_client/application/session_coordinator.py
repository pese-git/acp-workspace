"""SessionCoordinator - оркестрация операций с сессиями.

Координирует взаимодействие между Application и Infrastructure слоями
для управления жизненным циклом сессии и выполнения операций.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from acp_client.domain import SessionRepository, TransportService
from acp_client.infrastructure.logging_config import get_logger

from .dto import CreateSessionRequest, PromptCallbacks, SendPromptRequest
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
        cwd: str | None = None,
        client_capabilities: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Создает новую сессию на сервере.
        
        Аргументы:
            server_host: Адрес сервера
            server_port: Порт сервера
            cwd: Абсолютный путь рабочей директории (если None, используется текущая директория)
            client_capabilities: Возможности клиента (опционально)
        
        Возвращает:
            Объект созданной сессии с ID и capabilities
        """
        # Используем текущую директорию как default, если cwd не указана
        session_cwd = cwd or str(Path.cwd())
        
        # DEBUG: Логируем входные параметры coordinator
        self._logger.debug(
            "session_coordinator_create_session_called",
            server_host=server_host,
            server_port=server_port,
            cwd=session_cwd,
            client_capabilities=client_capabilities,
        )
        
        request = CreateSessionRequest(
            server_host=server_host,
            server_port=server_port,
            cwd=session_cwd,
            client_capabilities=client_capabilities,
        )
        
        # DEBUG: Логируем созданный DTO
        self._logger.debug(
            "create_session_request_dto_created",
            dto_server_host=request.server_host,
            dto_server_port=request.server_port,
            dto_client_capabilities=request.client_capabilities,
            dto_auth_method=request.auth_method,
            dto_auth_credentials=request.auth_credentials,
        )
        
        self._logger.info("creating_session", host=server_host, port=server_port)  # type: ignore[unknown-argument]
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
    
    async def send_prompt(
        self,
        session_id: str,
        prompt_text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Отправить prompt в активную сессию.
        
        Аргументы:
            session_id: ID сессии
            prompt_text: Текст промпта
            **kwargs: Дополнительные параметры (callbacks и т.д.)
        
        Возвращает:
            Результат выполнения промпта
        """
        # DEBUG: Проверяем что пришло в kwargs
        self._logger.debug(
            "send_prompt - received kwargs",
            has_kwargs=bool(kwargs),
            kwargs_keys=list(kwargs.keys()) if kwargs else [],
        )
        
        # Извлекаем callbacks если переданы
        callbacks = kwargs.get('callbacks')
        if callbacks is None and any(k.startswith('on_') for k in kwargs):
            # Создаем PromptCallbacks из kwargs
            callbacks = PromptCallbacks(
                on_update=kwargs.get('on_update'),
                on_permission=kwargs.get('on_permission'),
                on_fs_read=kwargs.get('on_fs_read'),
                on_fs_write=kwargs.get('on_fs_write'),
                on_terminal_create=kwargs.get('on_terminal_create'),
                on_terminal_output=kwargs.get('on_terminal_output'),
                on_terminal_wait_for_exit=kwargs.get('on_terminal_wait_for_exit'),
                on_terminal_release=kwargs.get('on_terminal_release'),
                on_terminal_kill=kwargs.get('on_terminal_kill'),
            )
        
        # Trace логи после извлечения callbacks
        self._logger.info(
            "SessionCoordinator.send_prompt callbacks extracted",
            has_callbacks=callbacks is not None,
            has_on_update=callbacks.on_update is not None if callbacks else False,
        )
        
        # DEBUG: Проверяем что получилось с callbacks
        self._logger.debug(
            "send_prompt - callbacks extracted",
            has_callbacks=callbacks is not None,
            has_on_update=callbacks.on_update is not None if callbacks else False,
        )
        
        request = SendPromptRequest(
            session_id=session_id,
            prompt_text=prompt_text,
            callbacks=callbacks,
        )
        
        self._logger.info("sending_prompt", session_id=session_id, prompt_length=len(prompt_text))
        response = await self.send_prompt_use_case.execute(request)
        
        return {
            "session_id": response.session_id,
            "prompt_result": response.prompt_result,
            "updates": response.updates,
        }
