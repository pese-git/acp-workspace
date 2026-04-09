"""ACPTransportService - инфраструктурная реализация низкоуровневой коммуникации.

Инкапсулирует WebSocket транспорт и предоставляет interface TransportService
для остальной системы. Обрабатывает:
- Подключение/отключение
- Отправку сообщений
- Получение ответов
- Обработку асинхронных уведомлений
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from acp_client.domain import TransportService
from acp_client.infrastructure.message_parser import MessageParser
from acp_client.infrastructure.transport import WebSocketTransport
from acp_client.messages import ACPMessage


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
        # Инициализируем транспорт для соединения
        self._transport: WebSocketTransport | None = None
        self._logger = structlog.get_logger("acp_transport_service")
    
    async def connect(self) -> None:
        """Устанавливает соединение с сервером.
        
        Создает WebSocket транспорт и открывает соединение.
        
        Raises:
            RuntimeError: При ошибке подключения
        """
        if self.is_connected():
            self._logger.warning("connection_already_exists", host=self.host, port=self.port)
            return
        
        try:
            # Создаем новый транспорт с заданными параметрами
            self._transport = WebSocketTransport(host=self.host, port=self.port)
            # Открываем соединение через context manager
            self._transport = await self._transport.__aenter__()
            self._logger.info("connected_to_server", host=self.host, port=self.port)
        except Exception as e:
            self._transport = None
            self._logger.error("connection_failed", host=self.host, port=self.port, error=str(e))
            msg = f"Failed to connect to {self.host}:{self.port}: {e}"
            raise RuntimeError(msg) from e
    
    async def disconnect(self) -> None:
        """Разрывает соединение с сервером.
        
        Закрывает WebSocket транспорт и освобождает ресурсы.
        """
        if not self.is_connected():
            return
        
        try:
            # Закрываем транспорт через __aexit__
            if self._transport is not None:
                await self._transport.__aexit__(None, None, None)
        except Exception as e:
            self._logger.warning("disconnect_error", error=str(e))
        finally:
            self._transport = None
            self._logger.info("disconnected_from_server")
    
    async def send(self, message: dict[str, Any]) -> None:
        """Отправляет сообщение на сервер.
        
        Аргументы:
            message: JSON-RPC сообщение для отправки
        
        Raises:
            RuntimeError: При ошибке отправки
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        message_id = message.get("id")
        self._logger.debug("sending_message", message_id=message_id)
        
        try:
            # Преобразуем сообщение в JSON и отправляем через транспорт
            json_message = json.dumps(message)
            assert self._transport is not None
            await self._transport.send_str(json_message)
            self._logger.debug("message_sent", message_id=message_id)
        except Exception as e:
            self._logger.error("send_failed", message_id=message_id, error=str(e))
            msg = f"Failed to send message: {e}"
            raise RuntimeError(msg) from e
    
    async def receive(self) -> dict[str, Any]:
        """Получает одно сообщение с сервера.
        
        Это блокирующая операция, ожидающая сообщение.
        
        Возвращает:
            JSON-RPC сообщение из сервера
        
        Raises:
            RuntimeError: При ошибке получения
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        self._logger.debug("waiting_for_message")
        
        try:
            # Получаем текстовое сообщение из транспорта и парсим JSON
            assert self._transport is not None
            json_message = await self._transport.receive_text()
            message = json.loads(json_message)
            self._logger.debug("message_received", message_id=message.get("id"))
            return message
        except Exception as e:
            self._logger.error("receive_failed", error=str(e))
            msg = f"Failed to receive message: {e}"
            raise RuntimeError(msg) from e
    
    async def listen(self) -> AsyncIterator[dict[str, Any]]:  # type: ignore[invalid-method-override]
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
        
        try:
            # Бесконечный цикл получения сообщений
            while self.is_connected():
                try:
                    message = await self.receive()
                    # Пропускаем пустые сообщения
                    if message:
                        yield message
                except RuntimeError as e:
                    self._logger.warning("receive_error_in_listen", error=str(e))
                    break
        except Exception as e:
            self._logger.error("listen_error", error=str(e))
            raise
        finally:
            self._logger.info("stopped_listening")
    
    def is_connected(self) -> bool:
        """Проверяет наличие активного соединения.
        
        Возвращает:
            True если соединение активно и готово к использованию
        """
        return self._transport is not None and self._transport.is_connected()
    
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
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)
        
        self._logger.info(
            "request_with_callbacks_start",
            method=method,
            has_callbacks=any([on_update, on_permission, on_fs_read, on_fs_write]),
        )
        
        try:
            # Создаем JSON-RPC запрос
            request = ACPMessage.request(method=method, params=params)
            request_data = request.to_dict()
            
            # Отправляем запрос
            await self.send(request_data)
            
            # Получаем ответы, обрабатывая промежуточные события
            while True:
                response_data = await self.receive()
                response = ACPMessage.from_dict(response_data)
                
                # Если это session/update - обрабатываем callback
                if response.method == "session/update" and on_update is not None:
                    on_update(response_data)
                    continue
                
                # Если это session/request_permission - обрабатываем callback
                if response.method == "session/request_permission" and on_permission is not None:
                    permission_response = on_permission(response_data)
                    # Отправляем ответ на permission запрос
                    permission_reply = ACPMessage.response(
                        response.id,
                        {"permission": permission_response} if permission_response else {},
                    )
                    await self.send(permission_reply.to_dict())
                    continue
                
                # Если это ответ на наш запрос - возвращаем результат
                if response.id == request.id:
                    if response.error is not None:
                        self._logger.error(
                            "request_error",
                            method=method,
                            error_code=response.error.code,
                            error_message=response.error.message,
                        )
                    self._logger.info("request_completed", method=method)
                    return response_data
                
        except Exception as e:
            self._logger.error("request_failed", method=method, error=str(e))
            raise
