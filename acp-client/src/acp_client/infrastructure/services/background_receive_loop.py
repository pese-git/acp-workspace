"""BackgroundReceiveLoop - фоновая задача приёма сообщений с маршрутизацией.

Решает race condition при конкурентном доступе к WebSocket.receive():
- Единственный вызов receive() на WebSocket (в background loop)
- Распределение сообщений по очередям на основе маршрутизации
- Обработка lifecycle (start, stop, error handling)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from acp_client.infrastructure.services.message_router import MessageRouter
from acp_client.infrastructure.services.routing_queues import RoutingQueues
from acp_client.infrastructure.transport import WebSocketTransport


class BackgroundReceiveLoop:
    """Фоновая задача для единственного вызова receive() на WebSocket.

    Архитектура:
    1. Запускается как asyncio.Task при подключении
    2. Непрерывно получает сообщения: message = await transport.receive()
    3. Маршрутизирует сообщение в нужную очередь:
       - response[id] → для RPC ответов
       - notification → для асинхронных уведомлений
       - permission → для запросов разрешения
    4. Обрабатывает ошибки и graceful shutdown

    Ключевое преимущество:
    - Все конкурентные запросы (request_with_callbacks) получают из очередей
    - Не вызывают receive() напрямую, избегая RuntimeError
    - Истинная конкурентность вместо блокировок
    """

    def __init__(
        self,
        transport: WebSocketTransport,
        router: MessageRouter,
        queues: RoutingQueues,
    ) -> None:
        """Инициализирует background loop.

        Args:
            transport: WebSocket транспорт для receive()
            router: MessageRouter для маршрутизации сообщений
            queues: RoutingQueues для хранения сообщений
        """
        self._transport = transport
        self._router = router
        self._queues = queues
        self._logger = structlog.get_logger("background_receive_loop")

        # Текущая фоновая задача
        self._task: asyncio.Task[None] | None = None

        # Флаг для graceful shutdown
        self._should_stop = False

        # Счетчики для диагностики
        self._messages_received = 0
        self._messages_routed = 0
        self._errors_count = 0

    async def start(self) -> None:
        """Запускает фоновый loop приёма сообщений.

        Создает asyncio.Task, которая работает в фоне.
        Можно вызвать несколько раз - будет игнорировано если уже запущена.

        Raises:
            RuntimeError: Если loop уже запущена
        """
        if self._task is not None and not self._task.done():
            self._logger.warning("background_loop_already_running")
            return

        self._should_stop = False
        self._task = asyncio.create_task(self._receive_loop())
        self._logger.info(
            "background_receive_loop_started",
            task_id=id(self._task),
        )

    async def stop(self) -> None:
        """Останавливает фоновый loop и дожидается его завершения.

        Graceful shutdown:
        1. Устанавливает флаг _should_stop = True
        2. Дожидается завершения задачи с таймаутом (5 сек)
        3. Если таймаут истек, отменяет задачу
        4. Логирует результат

        Note:
            Безопасно вызвать несколько раз
        """
        if self._task is None or self._task.done():
            self._logger.debug("background_loop_not_running")
            return

        self._logger.info(
            "stopping_background_receive_loop",
            task_id=id(self._task),
        )

        # Сигнализируем loop'у остановиться
        self._should_stop = True

        try:
            # Даем loop время на graceful завершение
            await asyncio.wait_for(self._task, timeout=5.0)
            self._logger.info(
                "background_receive_loop_stopped_gracefully",
                messages_received=self._messages_received,
                messages_routed=self._messages_routed,
            )
        except TimeoutError:
            # Если не завершилась, отменяем
            self._logger.warning(
                "background_receive_loop_timeout_cancelling_task"
            )
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self._logger.info("background_receive_loop_task_cancelled")

    async def _receive_loop(self) -> None:
        """Основной цикл приёма сообщений.

        КРИТИЧНО: Это единственное место, где вызывается transport.receive_text()

        Цикл:
        1. while not self._should_stop:
        2.   json_message = await self._transport.receive_text()
        3.   message = json.loads(json_message)
        4.   routing_key = self._router.route(message)
        5.   Положить сообщение в нужную очередь
        6. Обработка ошибок и graceful shutdown
        """
        self._logger.info("receive_loop_starting")

        try:
            while not self._should_stop:
                try:
                    # Получаем сообщение из WebSocket
                    # КРИТИЧНО: Это единственный receive_text() на всё соединение!
                    json_message = await self._transport.receive_text()
                    message = json.loads(json_message)
                    self._messages_received += 1

                    self._logger.debug(
                        "message_received",
                        message_has_id=("id" in message),
                        message_has_method=("method" in message),
                        messages_total=self._messages_received,
                    )

                    # Определяем маршрут сообщения
                    routing_key = self._router.route(message)

                    # Распределяем по очередям в зависимости от маршрута
                    if routing_key.queue_type == "response":
                        # RPC ответ на конкретный запрос
                        request_id = routing_key.request_id
                        if request_id is not None:
                            await self._queues.put_response(request_id, message)
                            self._messages_routed += 1
                        else:
                            self._logger.error(
                                "response_routing_missing_request_id"
                            )

                    elif routing_key.queue_type == "notification":
                        # Асинхронное уведомление
                        await self._queues.put_notification(message)
                        self._messages_routed += 1

                    elif routing_key.queue_type == "permission":
                        # Запрос разрешения
                        await self._queues.put_permission_request(message)
                        self._messages_routed += 1

                    else:
                        # Неизвестный тип - логируем и игнорируем
                        self._logger.warning(
                            "unknown_message_type_skipped",
                            message_keys=list(message.keys()),
                        )

                except asyncio.CancelledError:
                    self._logger.info("receive_loop_cancelled")
                    break

                except ConnectionError as e:
                    # Соединение потеряно
                    self._errors_count += 1
                    self._logger.warning(
                        "connection_lost_in_receive_loop",
                        error=str(e),
                        errors_count=self._errors_count,
                    )

                    # Уведомляем все pending очереди об ошибке
                    await self._queues.broadcast_connection_error(e)
                    break

                except Exception as e:
                    # Другая ошибка
                    self._errors_count += 1
                    self._logger.error(
                        "receive_loop_error",
                        error=str(e),
                        error_type=type(e).__name__,
                        errors_count=self._errors_count,
                    )

                    # При критической ошибке выходим из loop
                    break

        finally:
            # Graceful cleanup
            self._logger.info(
                "receive_loop_stopped",
                messages_received=self._messages_received,
                messages_routed=self._messages_routed,
                errors_count=self._errors_count,
            )

    def is_running(self) -> bool:
        """Проверить, работает ли background loop.

        Returns:
            True если задача создана и еще работает
        """
        return self._task is not None and not self._task.done()

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику работы loop'а.

        Returns:
            Словарь со статистикой (сообщения, ошибки и т.д.)
        """
        return {
            "running": self.is_running(),
            "messages_received": self._messages_received,
            "messages_routed": self._messages_routed,
            "errors_count": self._errors_count,
        }
