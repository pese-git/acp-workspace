"""Обработчики legacy методов.

Содержит логику обработки ping, echo, shutdown.
"""

from __future__ import annotations

from typing import Any

from ...messages import ACPMessage, JsonRpcId


def ping(request_id: JsonRpcId | None) -> ACPMessage:
    """Обрабатывает `ping` метод.

    Пример использования:
        response = ping("req_1")
    """
    return ACPMessage.response(request_id, {"pong": True})


def echo(request_id: JsonRpcId | None, params: dict[str, Any]) -> ACPMessage:
    """Обрабатывает `echo` метод.

    Пример использования:
        response = echo("req_1", {"message": "hello"})
    """
    return ACPMessage.response(request_id, {"echo": params})


def shutdown(request_id: JsonRpcId | None) -> ACPMessage:
    """Обрабатывает `shutdown` метод.

    Пример использования:
        response = shutdown("req_1")
    """
    return ACPMessage.response(
        request_id,
        {
            "ok": True,
            "message": "Server session closed",
        },
    )
