"""MessageRouter - маршрутизация сообщений по типам.

Анализирует входящие сообщения и определяет их маршрут на основе:
- message.id (для RPC ответов)
- message.method (для асинхронных уведомлений и запросов разрешения)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog


@dataclass(frozen=True)
class RoutingKey:
    """Ключ маршрутизации для сообщения."""

    queue_type: str  # "response", "notification", "permission", "unknown"
    request_id: int | None = None  # Для response сообщений


class MessageRouter:
    """Маршрутизирует сообщения в нужные очереди.

    Правила маршрутизации:
    1. Если message.id есть → RPC Response (в response_queue[id])
    2. Если message.method == "session/update" → Notification Queue
    3. Если message.method == "session/request_permission" → Permission Queue
    4. Если message.method == "session/cancel" → Notification Queue
    5. Остальные → Unknown (логируем ошибку)
    """

    def __init__(self) -> None:
        """Инициализирует маршрутизатор."""
        self._logger = structlog.get_logger("message_router")

    def route(self, message: dict[str, Any]) -> RoutingKey:
        """Определяет маршрут сообщения.

        Args:
            message: Сообщение от сервера (JSON-RPC или ACP уведомление)

        Returns:
            RoutingKey с информацией о маршруте
        """
        # Проверяем, это ответ на запрос (есть id)
        message_id = message.get("id")
        if message_id is not None:
            # Это RPC ответ
            self._logger.debug(
                "route_response_message",
                message_id=message_id,
                method=message.get("method"),
            )
            return RoutingKey(queue_type="response", request_id=message_id)

        # Проверяем метод (для уведомлений и запросов)
        method = message.get("method")

        if method == "session/update":
            # Асинхронное уведомление об обновлении сессии
            self._logger.debug("route_notification_update", method=method)
            return RoutingKey(queue_type="notification")

        if method == "session/request_permission":
            # Запрос разрешения (требует ответа)
            self._logger.debug("route_permission_request", method=method)
            return RoutingKey(queue_type="permission")

        if method == "session/cancel":
            # Отмена запроса (асинхронное уведомление)
            self._logger.debug("route_cancel_notification", method=method)
            return RoutingKey(queue_type="notification")

        # Неизвестный тип сообщения
        self._logger.warning(
            "route_unknown_message",
            method=method,
            has_id=message_id is not None,
        )
        return RoutingKey(queue_type="unknown")

    def is_response(self, message: dict[str, Any]) -> bool:
        """Проверяет, это ответ на запрос (есть id)."""
        return message.get("id") is not None

    def is_notification(self, message: dict[str, Any]) -> bool:
        """Проверяет, это асинхронное уведомление (нет id, есть method)."""
        method = message.get("method")
        return (
            message.get("id") is None
            and method in ("session/update", "session/cancel")
        )

    def is_permission_request(self, message: dict[str, Any]) -> bool:
        """Проверяет, это запрос разрешения."""
        return (
            message.get("id") is None
            and message.get("method") == "session/request_permission"
        )
