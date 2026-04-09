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
    
    Поддерживает async context manager для правильного управления жизненным циклом:
        async with ACPTransportService(host, port) as service:
            await service.connect()
            await service.send(message)
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
        # Сохраняем server capabilities после инициализации
        self._server_capabilities: dict[str, Any] | None = None
        self._logger = structlog.get_logger("acp_transport_service")
    
    async def __aenter__(self) -> ACPTransportService:
        """Входит в контекст manager для управления жизненным циклом.
        
        Возвращает:
            Текущий экземпляр ACPTransportService (self)
        """
        self._logger.debug("service_context_entering")
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Выходит из контекста manager и закрывает соединение.
        
        Гарантирует очистку ресурсов при выходе из контекста,
        даже если произошло исключение.
        
        Args:
            exc_type: Тип исключения (если оно возникло)
            exc_val: Значение исключения
            exc_tb: Traceback исключения
        """
        self._logger.debug("service_context_exiting")
        try:
            await self.disconnect()
        except Exception as e:
            self._logger.warning("error_in_context_exit", error=str(e))
    
    async def connect(self) -> None:
        """Устанавливает соединение с сервером.
        
        Создает WebSocket транспорт (если его еще нет) и открывает соединение.
        Переиспользует существующий транспорт для переподключения.
        Соединение остается открытым и должно быть закрыто явно через disconnect().
        
        Raises:
            RuntimeError: При ошибке подключения
        """
        if self.is_connected():
            self._logger.debug("already_connected", host=self.host, port=self.port)
            return
        
        try:
            # Создаем транспорт ТОЛЬКО если его еще нет
            # Это позволяет переиспользовать транспорт при переподключении
            # и избежать утечек ресурсов
            if self._transport is None:
                self._logger.debug("creating_new_transport", host=self.host, port=self.port)
                self._transport = WebSocketTransport(host=self.host, port=self.port)
            
            # Входим в context manager для открытия соединения
            # Вызов __aenter__() устанавливает _ws и _http_session
            # При переподключении это переиспользует существующий объект
            await self._transport.__aenter__()
            self._logger.info("connected_to_server", host=self.host, port=self.port)
        except Exception as e:
            # При ошибке очищаем ссылку на транспорт чтобы создать новый при следующей попытке
            self._transport = None
            self._logger.error("connection_failed", host=self.host, port=self.port, error=str(e))
            msg = f"Failed to connect to {self.host}:{self.port}: {e}"
            raise RuntimeError(msg) from e
    
    async def disconnect(self) -> None:
        """Разрывает соединение с сервером.
        
        Закрывает WebSocket транспорт и освобождает ресурсы.
        """
        if not self.is_connected():
            self._logger.debug("not_connected", host=self.host, port=self.port)
            return
        
        try:
            self._logger.debug("closing_connection", host=self.host, port=self.port)
            # Правильно вызываем __aexit__ для корректного закрытия соединения
            # Это завершает context manager и освобождает все ресурсы
            if self._transport is not None:
                await self._transport.__aexit__(None, None, None)
            self._logger.info("connection_closed", host=self.host, port=self.port)
        except Exception as e:
            self._logger.warning("disconnect_error", error=str(e), host=self.host, port=self.port)
        finally:
            self._transport = None
    
    async def send(self, message: dict[str, Any]) -> None:
        """Отправляет сообщение на сервер.
        
        Если соединение потеряно, автоматически переподключается.
        
        Аргументы:
            message: JSON-RPC сообщение для отправки
        
        Raises:
            RuntimeError: При ошибке отправки или переподключения
        """
        # Проверяем и восстанавливаем соединение если оно потеряно
        if not self.is_connected():
            self._logger.warning("send_connection_lost_reconnecting")
            try:
                await self.connect()
            except Exception as e:
                msg = f"Failed to reconnect to server: {e}"
                self._logger.error("send_reconnect_failed", error=str(e))
                raise RuntimeError(msg) from e
        
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
        Если соединение потеряно, генерирует ошибку (переподключение должно
        происходить на более высоком уровне через send()).
        
        Возвращает:
            JSON-RPC сообщение из сервера
        
        Raises:
            RuntimeError: При ошибке получения или потере соединения
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
            # Отмечаем что соединение потеряно при ошибке приема
            self._transport = None
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
        
        Проверяет:
        1. Существует ли ссылка на транспорт
        2. Открыто ли WebSocket соединение (не закрыто и имеет валидный _ws объект)
        
        Возвращает:
            True если соединение активно и готово к использованию
        """
        if self._transport is None:
            return False
        
        # Проверяем реальное состояние WebSocket
        connected = self._transport.is_connected()
        
        # Логируем состояние для отладки
        if not connected and self._transport is not None:
            self._logger.debug(
                "websocket_connection_lost",
                host=self.host,
                port=self.port,
                has_transport=self._transport is not None,
            )
        
        return connected
    
    def set_server_capabilities(self, capabilities: dict[str, Any]) -> None:
        """Сохраняет capabilities сервера после инициализации.
        
        Аргументы:
            capabilities: Словарь с возможностями сервера
        """
        self._server_capabilities = capabilities
        self._logger.info("server_capabilities_saved", capabilities=capabilities)
    
    def get_server_capabilities(self) -> dict[str, Any]:
        """Возвращает сохраненные capabilities сервера.
        
        Возвращает:
            Словарь с возможностями сервера
        
        Raises:
            RuntimeError: Если сервер не инициализирован
        """
        if self._server_capabilities is None:
            msg = "Server not initialized. Call InitializeUseCase first."
            raise RuntimeError(msg)
        return self._server_capabilities
    
    def is_initialized(self) -> bool:
        """Проверяет, была ли выполнена инициализация.
        
        Возвращает:
            True если сервер инициализирован и capabilities сохранены
        """
        return self._server_capabilities is not None
    
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
        # Проверяем и восстанавливаем соединение если оно потеряно
        if not self.is_connected():
            self._logger.warning("request_with_callbacks_connection_lost_reconnecting")
            try:
                await self.connect()
            except Exception as e:
                msg = f"Failed to reconnect to server: {e}"
                self._logger.error("request_with_callbacks_reconnect_failed", error=str(e))
                raise RuntimeError(msg) from e
        
        self._logger.info(
            "request_with_callbacks_start",
            method=method,
            has_callbacks=any([on_update, on_permission, on_fs_read, on_fs_write]),
        )
        
        try:
            # Создаем JSON-RPC запрос
            request = ACPMessage.request(method=method, params=params)
            request_data = request.to_dict()
            
            # Отправляем запрос (через send который имеет собственную защиту переподключения)
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
    
    def cleanup(self) -> None:
        """Очищает ресурсы синхронно (вызывается DI контейнером).
        
        Это вспомогательный метод для синхронной очистки.
        Для асинхронной очистки используйте disconnect().
        """
        self._logger.debug("cleanup_called")
        # Синхронная очистка - просто отмечаем что ресурсы больше не используются
        # Асинхронное закрытие соединения должно происходить через disconnect()
    
    def close(self) -> None:
        """Закрывает ресурсы синхронно (вызывается DI контейнером).
        
        Это вспомогательный метод для синхронного закрытия.
        Для асинхронного закрытия используйте disconnect().
        """
        self._logger.debug("close_called")
        # Синхронное закрытие - просто отмечаем что ресурсы больше не используются
        # Асинхронное закрытие соединения должно происходить через disconnect()
