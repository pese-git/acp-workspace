"""Infrastructure events для слабосвязанной коммуникации между сервисами.

Эти события используются для разрыва циклических зависимостей
между ACPTransportService, PermissionHandler и SessionCoordinator.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from codelab.client.domain.events import DomainEvent


@dataclass(frozen=True)
class PermissionRequestReceivedEvent(DomainEvent):
    """Событие: получен session/request_permission от сервера.

    Публикуется ACPTransportService когда получает permission request.
    Подписывается PermissionHandler для обработки запроса.
    """

    request_id: str | int
    tool_call: Any
    options: list[Any]
    raw_message: dict[str, Any]

    def __init__(
        self,
        request_id: str | int,
        session_id: str,
        tool_call: Any,
        options: list[Any],
        raw_message: dict[str, Any],
    ):
        object.__setattr__(self, 'request_id', request_id)
        object.__setattr__(self, 'tool_call', tool_call)
        object.__setattr__(self, 'options', options)
        object.__setattr__(self, 'raw_message', raw_message)
        object.__setattr__(self, 'aggregate_id', session_id)
        object.__setattr__(self, 'occurred_at', datetime.now(UTC))


@dataclass(frozen=True)
class PermissionResponseReadyEvent(DomainEvent):
    """Событие: permission response готов к отправке.

    Публикуется PermissionHandler после обработки запроса.
    Подписывается ACPTransportService для отправки response на сервер.
    """

    request_id: str | int
    response_message: dict[str, Any]

    def __init__(
        self,
        request_id: str | int,
        response_message: dict[str, Any],
    ):
        object.__setattr__(self, 'request_id', request_id)
        object.__setattr__(self, 'response_message', response_message)
        object.__setattr__(self, 'aggregate_id', 'permission')
        object.__setattr__(self, 'occurred_at', datetime.now(UTC))


@dataclass
class PermissionCallbackRegistry:
    """Реестр callback для permission handling.

    Хранит callback для показа UI modal и permission handler reference.
    Используется для связи между слоями без прямых зависимостей.
    """

    permission_callback: Callable[
        [str | int, Any, list[Any], Callable[[str | int, str], None]],
        None,
    ] | None = None
    _permission_handler: Any | None = field(default=None, repr=False)

    def set_permission_callback(
        self,
        callback: Callable[
            [str | int, Any, list[Any], Callable[[str | int, str], None]],
            None,
        ],
    ) -> None:
        """Установить callback для показа UI modal."""
        self.permission_callback = callback

    def set_permission_handler(self, handler: Any) -> None:
        """Установить reference на PermissionHandler."""
        self._permission_handler = handler

    def get_permission_handler(self) -> Any:
        """Получить reference на PermissionHandler."""
        return self._permission_handler
