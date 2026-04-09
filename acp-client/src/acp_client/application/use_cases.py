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
        
        ВАЖНО: Соединение остается открытым после выполнения для последующих операций.
        Закрытие соединения должно происходить явно через disconnect().
        
        Отправляет метод 'initialize' и получает информацию о сервере.
        
        Возвращает:
            InitializeResponse с информацией о сервере
        
        Raises:
            RuntimeError: При ошибке подключения или инициализации
        """
        self._logger.info("initialize_started")
        
        try:
            # Открываем соединение БЕЗ context manager - оно остается открытым
            await self._transport.connect()
            self._logger.info("connected_to_server")
            
            # Отправляем initialize запрос к серверу согласно протоколу ACP
            from acp_client.messages import ACPMessage
            
            # Формируем параметры инициализации согласно требованиям протокола ACP
            # protocolVersion - обязательный параметр
            # clientCapabilities и clientInfo - рекомендуемые параметры
            init_request = ACPMessage.request(
                method="initialize",
                params={
                    "protocolVersion": 1,  # Обязательный параметр протокола ACP
                    "clientCapabilities": {},  # Возможности клиента (пока пусто)
                    "clientInfo": {
                        "name": "acp-client",  # Идентификатор клиента
                        "version": "1.0.0"  # Версия клиента
                    }
                },
            )
            await self._transport.send(init_request.to_dict())
            self._logger.debug("initialize_request_sent", request_id=init_request.id)
            
            # Получаем ответ с информацией о сервере
            response_data = await self._transport.receive()
            response = ACPMessage.from_dict(response_data)
            
            # Обработка ошибок от сервера
            if response.error is not None:
                error_msg = f"Initialize failed: {response.error.message}"
                self._logger.error(
                    "initialize_error",
                    error_code=response.error.code,
                    error_message=response.error.message,
                )
                # При ошибке инициализации закрываем соединение
                await self._transport.disconnect()
                raise RuntimeError(error_msg)
            
            # Извлекаем capabilities и методы аутентификации из результата
            result = response.result or {}
            server_capabilities = result.get("serverCapabilities", {})
            available_auth_methods = result.get("authMethods", [])
            protocol_version = result.get("protocolVersion", "1.0")
            
            # Сохраняем capabilities в transport service для последующего использования
            self._transport.set_server_capabilities(server_capabilities)
            
            self._logger.info(
                "initialize_success",
                protocol_version=protocol_version,
                auth_methods_count=len(available_auth_methods),
            )
            
            return InitializeResponse(
                server_capabilities=server_capabilities,
                available_auth_methods=available_auth_methods,
                protocol_version=str(protocol_version),
            )
        
        except RuntimeError as e:
            self._logger.error("initialize_runtime_error", error=str(e))
            raise
        except Exception as e:
            # Обработка неожиданных ошибок подключения/сети
            error_msg = f"Failed to initialize: {e}"
            self._logger.error("initialize_unexpected_error", error=str(e))
            # При ошибке подключения закрываем соединение
            await self._transport.disconnect()
            raise RuntimeError(error_msg) from e


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
        
        Использует результаты инициализации, выполненной в InitializeUseCase.
        Полный жизненный цикл:
        1. Проверка инициализации сервера
        2. Аутентификация (если требуется)
        3. Создание сессии через session/new
        4. Сохранение в repository
        
        Аргументы:
            request: CreateSessionRequest с параметрами подключения и credentials
        
        Возвращает:
            CreateSessionResponse с созданной сессией
        
        Raises:
            RuntimeError: При ошибке подключения, аутентификации или создания сессии
        """
        self._logger.info(
            "creating_session",
            host=request.server_host,
            port=request.server_port,
        )
        
        try:
            from acp_client.messages import ACPMessage
            
            # Проверка инициализации транспорта
            if not self._transport.is_initialized():
                error_msg = "Transport not initialized. Call InitializeUseCase first."
                self._logger.error("transport_not_initialized")
                raise RuntimeError(error_msg)
            
            # Проверка соединения
            if not self._transport.is_connected():
                error_msg = "Transport not connected."
                self._logger.error("transport_not_connected")
                raise RuntimeError(error_msg)
            
            # Получить сохраненные capabilities из transport service
            server_capabilities = self._transport.get_server_capabilities()
            self._logger.debug("server_capabilities_received")
            
            # Шаг 2: Аутентификация (если требуется)
            if request.auth_method and request.auth_credentials:
                auth_request = ACPMessage.request(
                    "authenticate",
                    {
                        "authMethod": request.auth_method,
                        **request.auth_credentials,
                    },
                )
                await self._transport.send(auth_request.to_dict())
                auth_response_data = await self._transport.receive()
                auth_response = ACPMessage.from_dict(auth_response_data)
                
                if auth_response.error is not None:
                    error_msg = f"Authentication failed: {auth_response.error.message}"
                    self._logger.error(
                        "authentication_failed",
                        auth_method=request.auth_method,
                        error=error_msg,
                    )
                    raise RuntimeError(error_msg)
                
                self._logger.info("authenticated", auth_method=request.auth_method)
            
            # Шаг 3: Создание сессии через session/new
            session_request = ACPMessage.request(
                "session/new",
                {
                    "clientCapabilities": request.client_capabilities or {},
                },
            )
            await self._transport.send(session_request.to_dict())
            
            session_response_data = await self._transport.receive()
            session_response = ACPMessage.from_dict(session_response_data)
            
            if session_response.error is not None:
                error_msg = f"Session creation failed: {session_response.error.message}"
                self._logger.error("session_creation_failed", error=error_msg)
                raise RuntimeError(error_msg)
            
            # Шаг 4: Создание Domain сущности из ответа
            result = session_response.result or {}
            session_id = result.get("sessionId")
            
            if not session_id:
                error_msg = "Server response missing sessionId"
                self._logger.error("missing_session_id_in_response")
                raise RuntimeError(error_msg)
            
            session = Session.create(
                server_host=request.server_host,
                server_port=request.server_port,
                client_capabilities=request.client_capabilities or {},
                server_capabilities=server_capabilities,
                session_id=session_id,
            )
            
            # Отмечаем аутентификацию если была
            if request.auth_method:
                session.is_authenticated = True
            
            # Шаг 5: Сохранение в repository
            await self._session_repo.save(session)
            
            self._logger.info(
                "session_created_and_saved",
                session_id=session.id,
                is_authenticated=session.is_authenticated,
            )
            
            return CreateSessionResponse(
                session_id=session.id,
                server_capabilities=session.server_capabilities,
                is_authenticated=session.is_authenticated,
            )
        
        except RuntimeError as e:
            self._logger.error("create_session_runtime_error", error=str(e))
            raise
        except Exception as e:
            # Обработка неожиданных ошибок
            error_msg = f"Failed to create session: {e}"
            self._logger.error("create_session_unexpected_error", error=str(e))
            raise RuntimeError(error_msg) from e


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
        """Отправляет prompt в сессию с обработкой событий.
        
        Полный процесс:
        1. Проверка сессии в repository
        2. Отправка session/prompt запроса с вложенными файлами
        3. Обработка промежуточных событий (session/update, permission, и т.д.)
        4. Получение финального результата
        5. Сохранение обновлений сессии
        
        Аргументы:
            request: SendPromptRequest с:
                - session_id: ID активной сессии
                - prompt_text: Текст запроса
                - callbacks: Callbacks для обработки событий
        
        Возвращает:
            SendPromptResponse с:
                - session_id: ID сессии
                - prompt_result: Финальный результат выполнения
                - updates: Список обновлений, полученных во время выполнения
        
        Raises:
            ValueError: Если сессия не найдена
            RuntimeError: При ошибке транспорта или протокола
        """
        self._logger.info(
            "sending_prompt",
            session_id=request.session_id,
            prompt_length=len(request.prompt_text),
        )
        
        try:
            # Проверяем что сессия существует
            session = await self._session_repo.load(request.session_id)
            if session is None:
                self._logger.error("session_not_found", session_id=request.session_id)
                msg = f"Session {request.session_id} not found"
                raise ValueError(msg)
            
            # Сохраняем полученные обновления для возврата в response
            collected_updates: list[dict[str, Any]] = []
            
            # Обработчик для session/update - собираем обновления
            def handle_update(update_data: dict[str, Any]) -> None:
                """Обработчик обновлений сессии."""
                self._logger.debug("session_update_received", update_data=update_data)
                collected_updates.append(update_data)
                
                # Передаем в пользовательский callback если есть
                if request.callbacks and request.callbacks.on_update:
                    try:
                        request.callbacks.on_update(update_data)
                    except Exception as e:
                        self._logger.warning(
                            "user_update_callback_error",
                            error=str(e),
                        )
            
            # Обработчик для permission - обрабатываем через callback
            def handle_permission(perm_data: dict[str, Any]) -> str | None:
                """Обработчик запроса разрешения."""
                self._logger.debug("permission_request_received", perm_data=perm_data)
                
                if request.callbacks and request.callbacks.on_permission:
                    try:
                        result = request.callbacks.on_permission(perm_data)
                        self._logger.info("permission_handled", result=result)
                        return result
                    except Exception as e:
                        self._logger.warning(
                            "user_permission_callback_error",
                            error=str(e),
                        )
                        return None
                
                return None
            
            # Подготовляем callbacks для транспорта
            transport_callbacks = {
                "on_update": handle_update,
                "on_permission": handle_permission,
            }
            
            # Добавляем остальные callbacks если предоставлены
            if request.callbacks:
                if request.callbacks.on_fs_read:
                    transport_callbacks["on_fs_read"] = request.callbacks.on_fs_read
                if request.callbacks.on_fs_write:
                    transport_callbacks["on_fs_write"] = request.callbacks.on_fs_write
                if request.callbacks.on_terminal_create:
                    transport_callbacks["on_terminal_create"] = request.callbacks.on_terminal_create
                if request.callbacks.on_terminal_output:
                    transport_callbacks["on_terminal_output"] = (
                        request.callbacks.on_terminal_output
                    )
                if request.callbacks.on_terminal_wait_for_exit:
                    transport_callbacks["on_terminal_wait"] = (
                        request.callbacks.on_terminal_wait_for_exit
                    )
                if request.callbacks.on_terminal_release:
                    transport_callbacks["on_terminal_release"] = (
                        request.callbacks.on_terminal_release
                    )
                if request.callbacks.on_terminal_kill:
                    transport_callbacks["on_terminal_kill"] = (
                        request.callbacks.on_terminal_kill
                    )
            
            # Отправляем prompt через transport с обработкой callbacks
            prompt_response = await self._transport.request_with_callbacks(
                method="session/prompt",
                params={
                    "sessionId": request.session_id,
                    "prompt": request.prompt_text,
                },
                **transport_callbacks,
            )
            
            # Проверяем ошибки в ответе
            from acp_client.messages import ACPMessage
            response = ACPMessage.from_dict(prompt_response)
            
            if response.error is not None:
                error_msg = f"Prompt failed: {response.error.message}"
                self._logger.error(
                    "prompt_failed",
                    session_id=request.session_id,
                    error=error_msg,
                )
                raise RuntimeError(error_msg)
            
            prompt_result = response.result or {}
            
            # Обновляем сессию в repository
            session.is_authenticated = True  # После успешного prompt считаем аутентифицированной
            await self._session_repo.save(session)
            
            self._logger.info(
                "prompt_completed",
                session_id=request.session_id,
                updates_count=len(collected_updates),
            )
            
            return SendPromptResponse(
                session_id=request.session_id,
                prompt_result=prompt_result,
                updates=collected_updates,
            )
        
        except ValueError as e:
            # Ошибка валидации (не найдена сессия)
            self._logger.error("send_prompt_validation_error", error=str(e))
            raise
        except RuntimeError as e:
            # Ошибка транспорта или протокола
            self._logger.error("send_prompt_runtime_error", error=str(e))
            raise
        except Exception as e:
            # Неожиданные ошибки
            error_msg = f"Failed to send prompt: {e}"
            self._logger.error("send_prompt_unexpected_error", error=str(e))
            raise RuntimeError(error_msg) from e


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
