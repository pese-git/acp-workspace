"""ACPTransportService - инфраструктурная реализация низкоуровневой коммуникации.

Инкапсулирует WebSocket транспорт и предоставляет interface TransportService
для остальной системы. Обрабатывает:
- Подключение/отключение
- Отправку сообщений
- Получение ответов
- Обработку асинхронных уведомлений

Архитектура:
- Background Receive Loop: единственный вызов receive() на WebSocket
- Message Router: маршрутизация по типам сообщений
- Routing Queues: распределение по очередям для конкурентных запросов
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

from acp_client.domain import TransportService
from acp_client.infrastructure.message_parser import MessageParser
from acp_client.infrastructure.services.background_receive_loop import (
    BackgroundReceiveLoop,
)
from acp_client.infrastructure.services.message_router import MessageRouter
from acp_client.infrastructure.services.routing_queues import RoutingQueues
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

        # Infrastructure для управления конкурентными вызовами receive()
        # Background Receive Loop: единственный вызов receive() на WebSocket
        self._background_loop: BackgroundReceiveLoop | None = None
        # Message Router: маршрутизация по типам сообщений
        self._router: MessageRouter | None = None
        # Routing Queues: распределение по очередям
        self._queues: RoutingQueues | None = None
        # Глобальная блокировка для request_with_callbacks.
        # Нужна, чтобы разные callback-запросы не конкурировали за
        # общую notification_queue и не теряли session/update события.
        self._callbacks_request_lock = asyncio.Lock()

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
        """Устанавливает соединение с сервером и запускает background receive loop.

        Создает WebSocket транспорт (если его еще нет) и открывает соединение.
        Инициализирует routing infrastructure и запускает background loop для
        единственного вызова receive() на WebSocket.

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

            # Инициализируем routing infrastructure
            self._router = MessageRouter()
            self._queues = RoutingQueues()
            self._background_loop = BackgroundReceiveLoop(
                self._transport,
                self._router,
                self._queues,
            )

            # Запускаем background loop - единственный вызов receive() на WebSocket
            await self._background_loop.start()

            self._logger.info(
                "connected_to_server",
                host=self.host,
                port=self.port,
                background_loop_running=self._background_loop.is_running(),
            )
        except Exception as e:
            # При ошибке очищаем ресурсы
            self._transport = None
            self._background_loop = None
            self._queues = None
            self._router = None
            self._logger.error("connection_failed", host=self.host, port=self.port, error=str(e))
            msg = f"Failed to connect to {self.host}:{self.port}: {e}"
            raise RuntimeError(msg) from e

    async def disconnect(self) -> None:
        """Разрывает соединение с сервером.

        Graceful shutdown:
        1. Останавливает background receive loop
        2. Очищает routing infrastructure
        3. Закрывает WebSocket транспорт
        4. Освобождает все ресурсы
        """
        if not self.is_connected():
            self._logger.debug("not_connected", host=self.host, port=self.port)
            return

        try:
            self._logger.debug("closing_connection", host=self.host, port=self.port)

            # Сначала останавливаем background loop - это главное
            # Иначе он будет пытаться читать из закрытого транспорта
            if self._background_loop is not None:
                self._logger.debug("stopping_background_loop")
                await self._background_loop.stop()

            # Очищаем очереди чтобы разбудить все ждущие операции
            if self._queues is not None:
                await self._queues.clear_all()

            # Потом закрываем транспорт
            # Правильно вызываем __aexit__ для корректного закрытия соединения
            # Это завершает context manager и освобождает все ресурсы
            if self._transport is not None:
                await self._transport.__aexit__(None, None, None)

            self._logger.info("connection_closed", host=self.host, port=self.port)
        except Exception as e:
            self._logger.warning("disconnect_error", error=str(e), host=self.host, port=self.port)
        finally:
            # Окончательная очистка ресурсов
            self._transport = None
            self._background_loop = None
            self._queues = None
            self._router = None

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

    async def receive(self, request_id: str | None = None) -> dict[str, Any]:
        """Получает одно сообщение с сервера из очереди RPC ответов.

        Архитектура:
        - Background loop единственный получает из transport.receive_text()
        - Маршрутизирует в очереди на основе Message Router
        - receive() получает из соответствующей очереди

        Поддерживает две режима:
        1. С request_id: получает RPC ответ на конкретный запрос из response_queues[request_id]
        2. Без request_id: получает асинхронное уведомление из notification_queue

        Использует Message Router и Routing Queues для распределения
        конкурентных запросов на одном WebSocket соединении.

        Аргументы:
            request_id: ID конкретного RPC запроса (опционально)

        Возвращает:
            JSON-RPC сообщение из сервера

        Raises:
            RuntimeError: При ошибке получения или потере соединения
        """
        if not self.is_connected():
            msg = "Not connected to server"
            self._logger.error("not_connected")
            raise RuntimeError(msg)

        if self._queues is None:
            msg = "Routing queues not initialized"
            self._logger.error("queues_not_initialized")
            raise RuntimeError(msg)

        try:
            # Выбираем очередь в зависимости от request_id
            if request_id is not None:
                # Получаем ответ на конкретный RPC запрос
                self._logger.debug("waiting_for_rpc_response", request_id=request_id)
                # Получаем или создаем очередь для этого request_id
                response_queue = await self._queues.get_or_create_response_queue(request_id)
                message = await asyncio.wait_for(
                    response_queue.get(),
                    timeout=300.0,
                )
            else:
                # Получаем асинхронное уведомление
                self._logger.debug("waiting_for_notification")
                message = await asyncio.wait_for(
                    self._queues.notification_queue.get(),
                    timeout=300.0,
                )

            message_id = message.get("id")
            self._logger.debug(
                "message_received_from_queue",
                message_id=message_id,
                request_id=request_id,
                has_result="result" in message,
                has_error="error" in message,
            )
            return message
        except TimeoutError:
            self._logger.error("receive_timeout", request_id=request_id)
            msg = "Timeout waiting for message from server"
            raise RuntimeError(msg) from None
        except Exception as e:
            self._logger.error(
                "receive_failed",
                error=str(e),
                error_type=type(e).__name__,
                request_id=request_id,
            )
            msg = f"Failed to receive message: {e}"
            raise RuntimeError(msg) from e

    def listen(self) -> AsyncIterator[dict[str, Any]]:
        """Слушает входящие сообщения с сервера.

        Возвращает асинхронный итератор, который выдает
        сообщения по мере их поступления с сервера.

        Yields:
            JSON-RPC сообщения из сервера
        """

        async def _message_stream() -> AsyncIterator[dict[str, Any]]:
            if not self.is_connected():
                msg = "Not connected to server"
                self._logger.error("not_connected")
                raise RuntimeError(msg)

            self._logger.info("listening_for_messages")

            try:
                while self.is_connected():
                    try:
                        message = await self.receive()
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

        return _message_stream()

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
        """Выполняет request с обработкой callbacks используя routing queues.

        Архитектура:
        1. Создает очередь для этого request_id (или использует существующую)
        2. Отправляет request
        3. Ждет ответа из очереди для этого request_id
        4. Обрабатывает асинхронные события (updates, permissions)
        5. Несколько конкурентных запросов могут работать параллельно

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

        if self._queues is None:
            msg = "Routing queues not initialized"
            self._logger.error("queues_not_initialized")
            raise RuntimeError(msg)

        async with self._callbacks_request_lock:
            # Слушаем incoming server->client RPC всегда: даже без пользовательских
            # callbacks нужно отправить корректный response, иначе сервер зависнет
            # в ожидании и финальный ответ на запрос не придет.
            should_listen_notifications = True
            self._logger.info(
                "request_with_callbacks_start",
                method=method,
                has_callbacks=should_listen_notifications,
            )

            request: ACPMessage | None = None
            request_id: str | int | None = None
            try:
                # Создаем JSON-RPC запрос
                request = ACPMessage.request(method=method, params=params)
                if not isinstance(request.id, str | int):
                    raise RuntimeError("Generated request without valid id")
                request_id = request.id
                request_data = request.to_dict()

                # Создаем очередь для этого request_id.
                # Background loop будет класть ответы в эту очередь.
                response_queue = await self._queues.get_or_create_response_queue(request_id)

                # Отправляем запрос (через send с защитой переподключения).
                await self.send(request_data)

                self._logger.debug(
                    "request_sent",
                    method=method,
                    request_id=request_id,
                )

                # Получаем ответы, обрабатывая промежуточные события.
                # Используем asyncio.wait для ожидания нескольких очередей одновременно.
                while True:
                    # Создаем задачи для ожидания из разных очередей.
                    response_task = asyncio.create_task(
                        asyncio.wait_for(response_queue.get(), timeout=300.0)
                    )
                    notification_task: asyncio.Task[dict[str, Any]] | None = None
                    permission_task: asyncio.Task[dict[str, Any]] | None = None
                    if should_listen_notifications:
                        notification_task = asyncio.create_task(
                            asyncio.wait_for(self._queues.notification_queue.get(), timeout=0.1)
                        )
                        permission_task = asyncio.create_task(
                            asyncio.wait_for(self._queues.permission_queue.get(), timeout=0.1)
                        )

                    # Ждем первого результата.
                    done, pending = await asyncio.wait(
                        [response_task]
                        if notification_task is None or permission_task is None
                        else [response_task, notification_task, permission_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Отменяем оставшиеся задачи.
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                    # Сначала обрабатываем notification, если она уже получена.
                    # Это предотвращает потерю события в кейсе, когда response
                    # и notification завершаются одновременно.
                    if permission_task is not None and permission_task in done:
                        try:
                            permission_data = permission_task.result()
                            await self._handle_permission_request(
                                permission_data=permission_data,
                                on_permission=on_permission,
                            )
                        except TimeoutError:
                            # Таймаут при ожидании уведомления — нормально.
                            pass
                        except Exception:
                            # Игнорируем ошибки обработки уведомлений.
                            pass

                    if notification_task is not None and notification_task in done:
                        try:
                            notification_data = notification_task.result()
                            await self._handle_notification_or_client_rpc(
                                method=method,
                                request_id=request_id,
                                notification_data=notification_data,
                                on_update=on_update,
                                on_fs_read=on_fs_read,
                                on_fs_write=on_fs_write,
                                on_terminal_create=on_terminal_create,
                                on_terminal_output=on_terminal_output,
                                on_terminal_wait=on_terminal_wait,
                                on_terminal_release=on_terminal_release,
                                on_terminal_kill=on_terminal_kill,
                            )
                        except TimeoutError:
                            # Таймаут при ожидании уведомления — нормально.
                            pass
                        except Exception:
                            # Игнорируем ошибки обработки уведомлений.
                            pass

                    # Проверяем результат от response queue.
                    if response_task in done:
                        try:
                            response_data = response_task.result()
                            # Сравниваем id по raw payload, чтобы не терять корректный
                            # ответ из-за излишне строгого разбора в ACPMessage.
                            if response_data.get("id") == request_id:
                                if isinstance(response_data.get("error"), dict):
                                    error_payload = response_data["error"]
                                    self._logger.error(
                                        "request_error",
                                        method=method,
                                        error_code=error_payload.get("code"),
                                        error_message=error_payload.get("message"),
                                    )

                                # Обрабатываем уведомления после финального ответа.
                                # Небольшой grace period нужен, чтобы забрать события,
                                # которые могли прийти сразу после response и попасть
                                # в очередь чуть позже этой проверки.
                                remaining_notifications = 0
                                while True:
                                    try:
                                        notification_data = await asyncio.wait_for(
                                            self._queues.notification_queue.get(),
                                            timeout=0.2,
                                        )
                                        notification = ACPMessage.from_dict(notification_data)
                                        remaining_notifications += 1

                                        if (
                                            notification.method == "session/update"
                                            and on_update is not None
                                        ):
                                            self._logger.debug(
                                                "handling_remaining_session_update",
                                                method=method,
                                                request_id=request_id,
                                                remaining_count=remaining_notifications,
                                            )
                                            on_update(notification_data)
                                    except TimeoutError:
                                        break
                                    except Exception as e:
                                        self._logger.warning(
                                            "error_processing_remaining_notification",
                                            error=str(e),
                                        )

                                if remaining_notifications > 0:
                                    self._logger.info(
                                        "processed_remaining_notifications",
                                        method=method,
                                        request_id=request_id,
                                        count=remaining_notifications,
                                    )

                                self._logger.info(
                                    "request_completed",
                                    method=method,
                                    request_id=request_id,
                                )
                                return response_data
                        except TimeoutError:
                            self._logger.error(
                                "request_timeout",
                                method=method,
                                request_id=request_id,
                            )
                            raise RuntimeError(f"Request {request_id} timed out") from None
                        except Exception:
                            # Продолжаем если была ошибка.
                            pass

            except Exception as e:
                self._logger.error(
                    "request_failed",
                    method=method,
                    request_id=request_id,
                    error=str(e),
                )
                raise
            finally:
                # Очищаем очередь ответов после использования.
                if request_id is not None and self._queues is not None:
                    cleanup_request_id: str | int = request_id
                    await self._queues.cleanup_response_queue(cleanup_request_id)

    async def _handle_permission_request(
        self,
        *,
        permission_data: dict[str, Any],
        on_permission: Callable[[dict[str, Any]], str | None] | None,
    ) -> None:
        """Обрабатывает server->client `session/request_permission` и отправляет response."""
        permission = ACPMessage.from_dict(permission_data)
        if permission.method != "session/request_permission":
            return

        permission_result = on_permission(permission_data) if on_permission is not None else None
        permission_reply = ACPMessage.response(
            permission.id,
            {
                "outcome": (
                    {
                        "outcome": "selected",
                        "optionId": permission_result,
                    }
                    if permission_result
                    else {"outcome": "cancelled"}
                )
            },
        )
        await self.send(permission_reply.to_dict())

    async def _handle_notification_or_client_rpc(
        self,
        *,
        method: str,
        request_id: str | int,
        notification_data: dict[str, Any],
        on_update: Callable[[dict[str, Any]], None] | None,
        on_fs_read: Callable[[str], str] | None,
        on_fs_write: Callable[[str, str], str | None] | None,
        on_terminal_create: Callable[[str], str] | None,
        on_terminal_output: Callable[[str], str] | None,
        on_terminal_wait: Callable[[str], int | tuple[int | None, str | None]] | None,
        on_terminal_release: Callable[[str], None] | None,
        on_terminal_kill: Callable[[str], bool] | None,
    ) -> None:
        """Обрабатывает `session/update` и incoming RPC (`fs/*`, `terminal/*`)."""
        notification = ACPMessage.from_dict(notification_data)

        if notification.method == "session/update":
            if on_update is not None:
                self._logger.debug(
                    "handling_session_update",
                    method=method,
                    request_id=request_id,
                    has_callback=on_update is not None,
                )
                on_update(notification_data)
            else:
                self._logger.warning(
                    "session_update_received_but_no_callback",
                    method=method,
                    request_id=request_id,
                )
            return

        rpc_method = notification.method
        if rpc_method is None or notification.id is None:
            return

        rpc_params = notification.params if isinstance(notification.params, dict) else {}

        if rpc_method == "fs/read_text_file":
            path = rpc_params.get("path")
            content = on_fs_read(path) if on_fs_read is not None and isinstance(path, str) else ""
            await self.send(ACPMessage.response(notification.id, {"content": content}).to_dict())
            return

        if rpc_method == "fs/write_text_file":
            path = rpc_params.get("path")
            text = rpc_params.get("content")
            if on_fs_write is not None and isinstance(path, str) and isinstance(text, str):
                on_fs_write(path, text)
            await self.send(ACPMessage.response(notification.id, {}).to_dict())
            return

        if rpc_method == "terminal/create":
            command = rpc_params.get("command")
            terminal_id = (
                on_terminal_create(command)
                if on_terminal_create is not None and isinstance(command, str)
                else None
            )
            await self.send(
                ACPMessage.response(
                    notification.id,
                    {"terminalId": terminal_id} if terminal_id else {},
                ).to_dict()
            )
            return

        if rpc_method == "terminal/output":
            terminal_id = rpc_params.get("terminalId")
            output = (
                on_terminal_output(terminal_id)
                if on_terminal_output is not None and isinstance(terminal_id, str)
                else None
            )
            await self.send(
                ACPMessage.response(notification.id, {"output": output} if output else {}).to_dict()
            )
            return

        if rpc_method == "terminal/wait_for_exit":
            terminal_id = rpc_params.get("terminalId")
            exit_code: int | None = None
            output: str | None = None
            if on_terminal_wait is not None and isinstance(terminal_id, str):
                wait_result = on_terminal_wait(terminal_id)
                if isinstance(wait_result, tuple):
                    candidate_exit_code, candidate_output = wait_result
                    exit_code = (
                        candidate_exit_code if isinstance(candidate_exit_code, int) else None
                    )
                    output = candidate_output if isinstance(candidate_output, str) else None
                elif isinstance(wait_result, int):
                    exit_code = wait_result

            result_payload: dict[str, Any] = {}
            if exit_code is not None:
                result_payload["exitCode"] = exit_code
            if output is not None:
                result_payload["output"] = output
            await self.send(ACPMessage.response(notification.id, result_payload).to_dict())
            return

        if rpc_method == "terminal/release":
            terminal_id = rpc_params.get("terminalId")
            if on_terminal_release is not None and isinstance(terminal_id, str):
                on_terminal_release(terminal_id)
            await self.send(ACPMessage.response(notification.id, {}).to_dict())
            return

        if rpc_method == "terminal/kill":
            terminal_id = rpc_params.get("terminalId")
            killed = (
                on_terminal_kill(terminal_id)
                if on_terminal_kill is not None and isinstance(terminal_id, str)
                else False
            )
            await self.send(ACPMessage.response(notification.id, {"killed": killed}).to_dict())
            return

        # Для неизвестных server->client RPC возвращаем пустой успешный response,
        # чтобы не блокировать prompt-turn на сервере.
        await self.send(ACPMessage.response(notification.id, {}).to_dict())

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
