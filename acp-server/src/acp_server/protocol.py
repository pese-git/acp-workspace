from __future__ import annotations

from datetime import UTC, datetime

from .messages import ACPMessage


def process_request(request: ACPMessage) -> ACPMessage:
    if request.type != "request":
        return ACPMessage(
            id=request.id,
            type="response",
            error={"code": -32600, "message": "Invalid message type"},
        )

    if request.method == "initialize":
        return ACPMessage(
            id=request.id,
            type="response",
            result={
                "protocol": "ACP",
                "version": "1.0",
                "capabilities": ["ping", "echo", "shutdown"],
                "transports": ["tcp", "http", "ws"],
            },
        )

    if request.method == "ping":
        return ACPMessage(
            id=request.id,
            type="response",
            result={"pong": True, "timestamp": datetime.now(UTC).isoformat()},
        )

    if request.method == "echo":
        return ACPMessage(
            id=request.id,
            type="response",
            result={"echo": request.params or {}},
        )

    if request.method == "shutdown":
        return ACPMessage(
            id=request.id,
            type="response",
            result={"ok": True, "message": "Server session closed"},
        )

    return ACPMessage(
        id=request.id,
        type="response",
        error={"code": -32601, "message": f"Method not found: {request.method}"},
    )
