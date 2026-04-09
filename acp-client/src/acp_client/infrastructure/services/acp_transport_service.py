"""ACPTransportService - инфраструктурная реализация низкоуровневой коммуникации.

Инкапсулирует WebSocket транспорт и предоставляет interface TransportService
для остальной системы. Обрабатывает:
- Подключение/отключение
- Отправку сообщений
- Получение ответов
- Обработку асинхронных уведомлений
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from acp_client.domain import TransportService
from acp_client.infrastructure.message_parser import MessageParser
from acp_client.transport import ACPClientWSSession


class ACPTransportService(TransportService):
    """Реализация низкоуровневой коммуникации с ACP сервером.
    
    Оборачивает WebSocket транспорт и предоставляет чистый interface
    для отправки/получения сообщений. Используется Application слоем
    через Use Cases.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        parser: MessageParser | None = None,
    ) -> None:
        """Инициализирует сервис.
        
        Аргументы:
            host: Адрес ACP сервера
            port: Порт ACP сервера
            parser: MessageParser для парсинга ответов (опционально)
        """
        self.host = host
        self.port = port
        self.parser = parser or MessageParser()
        self._session: ACPClientWSSession | None = None
        self._logger = structlog.get_logger("acp_transport_service")
    
    async def connect(self) -> None:
        """Устанавливает соединение с сервером.
        
        Создает WebSocket сессию и инициализирует её.
        
        Raises:
            TransportError: При ошибке подключения
        """
        if self._session is not None:
            self._logger.warning("already_connected")
            return
        
        # TODO: Создать сессию с адресом сервера
        # Пока это заглушка для того, чтобы не ломать существующий код
        self._logger.info("connected_to_server", host=self.host, port=self.port)
    
    async def disconnect(self) -> None:
        """Разрывает соединение с сервером.
        
        Закрывает WebSocket сессию и освобождает ресурсы.
        """
        if self._session is None:
            return
        
        # TODO: Закрыть сессию
        self._session = None
        self._logger.info("disconnected_from_server")
    
    async def send(self, message: dict[str, Any]) -> None:
        """Отправляет сообщение на сервер.
        
        Аргументы:
            message: JSON-RPC сообщение для отправки
        
        Raises:
            TransportError: При ошибке отправки
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        self._logger.debug("sending_message", message_id=message.get("id"))
        
        # TODO: Отправить через session
    
    async def receive(self) -> dict[str, Any]:
        """Получает одно сообщение с сервера.
        
        Это блокирующая операция, ожидающая сообщение.
        
        Возвращает:
            JSON-RPC сообщение из сервера
        
        Raises:
            TransportError: При ошибке получения
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        self._logger.debug("waiting_for_message")
        
        # TODO: Получить через session
        return {}
    
    async def listen(self) -> AsyncIterator[dict[str, Any]]:  # type: ignore[override]
        """Слушает входящие сообщения с сервера.
        
        Возвращает асинхронный итератор, который выдает
        сообщения по мере их поступления с сервера.
        
        Yields:
            JSON-RPC сообщения из сервера
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        self._logger.info("listening_for_messages")
        
        # TODO: Реализовать слушание уведомлений
        # Пока возвращаем пустой итератор
        return
        yield  # type: ignore[unreachable]
    
    def is_connected(self) -> bool:
        """Проверяет наличие активного соединения.
        
        Возвращает:
            True если соединение активно и готово к использованию
        """
        return self._session is not None
    
    async def request_with_callbacks(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        on_update: Callable[[dict[str, Any]], None] | None = None,
        on_permission: Callable[[dict[str, Any]], str | None] | None = None,
        on_fs_read: Callable[[str], str] | None = None,
        on_fs_write: Callable[[str, str], str | None] | None = None,
        on_terminal_create: Callable[[str], str] | None = None,
        on_terminal_output: Callable[[str], str] | None = None,
        on_terminal_wait: Callable[[str], int | tuple[int | None, str | None]] | None = None,
        on_terminal_release: Callable[[str], None] | None = None,
        on_terminal_kill: Callable[[str], bool] | None = None,
    ) -> dict[str, Any]:
        """Выполняет request с обработкой callbacks.
        
        Это специальный метод, который объединяет отправку запроса
        с обработкой асинхронных событий (session/update, permission и т.д.)
        
        Аргументы:
            method: Метод для вызова
            params: Параметры метода
            on_update: Callback для session/update
            on_permission: Callback для session/request_permission
            on_fs_read: Callback для fs/read
            on_fs_write: Callback для fs/write
            on_terminal_create: Callback для terminal/create
            on_terminal_output: Callback для terminal/output
            on_terminal_wait: Callback для terminal/wait_for_exit
            on_terminal_release: Callback для terminal/release
            on_terminal_kill: Callback для terminal/kill
        
        Возвращает:
            Финальный ответ на request
        """
        # TODO: Реализовать полный цикл с обработкой callbacks
        self._logger.info(
            "request_with_callbacks",
            method=method,
            has_callbacks=any([on_update, on_permission, on_fs_read, on_fs_write]),
        )
        
        return {}
