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
        session_cwd = cwd or str(Path.cwd())

        request = CreateSessionRequest(
            server_host=server_host,
            server_port=server_port,
            cwd=session_cwd,
            client_capabilities=client_capabilities,
        )

        self._logger.info("creating_session")
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

    async def delete_session(self, session_id: str) -> None:
        """Удаляет сессию из локального репозитория."""

        self._logger.info("deleting_session")
        await self.session_repo.delete(session_id)

    async def cancel_prompt(self, session_id: str) -> None:
        """Отменяет текущий prompt на сервере для указанной сессии."""

        self._logger.info("cancelling_prompt")
        await self.transport.request_with_callbacks(
            method="session/cancel",
            params={"sessionId": session_id},
        )

    async def handle_permission(
        self,
        session_id: str,
        permission_id: str,
        *,
        approved: bool,
        **_: Any,
    ) -> None:
        """Локально фиксирует решение по permission-запросу.

        В текущем клиенте решение по permission отправляется в рамках
        request/response-цикла транспорта. Этот метод оставлен как
        совместимый контракт для существующих ViewModel-команд.
        """

        self._logger.info(
            "permission_decision_recorded",
            session_id=session_id,
            permission_id=permission_id,
            approved=approved,
        )

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
        # Извлекаем callbacks если переданы
        callbacks = kwargs.get("callbacks")
        if callbacks is None and any(k.startswith("on_") for k in kwargs):
            # Создаем PromptCallbacks из kwargs
            callbacks = PromptCallbacks(
                on_update=kwargs.get("on_update"),
                on_permission=kwargs.get("on_permission"),
                on_fs_read=kwargs.get("on_fs_read"),
                on_fs_write=kwargs.get("on_fs_write"),
                on_terminal_create=kwargs.get("on_terminal_create"),
                on_terminal_output=kwargs.get("on_terminal_output"),
                on_terminal_wait_for_exit=kwargs.get("on_terminal_wait_for_exit"),
                on_terminal_release=kwargs.get("on_terminal_release"),
                on_terminal_kill=kwargs.get("on_terminal_kill"),
            )

        request = SendPromptRequest(
            session_id=session_id,
            prompt_text=prompt_text,
            callbacks=callbacks,
        )

        self._logger.info("sending_prompt")
        response = await self.send_prompt_use_case.execute(request)

        return {
            "session_id": response.session_id,
            "prompt_result": response.prompt_result,
            "updates": response.updates,
        }
