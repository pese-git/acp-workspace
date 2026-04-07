"""Модуль протокола ACP.

Инкапсулирует в-memory реализацию ACP-протокола для demo/интеграционных сценариев.
"""

from .core import ACPProtocol
from .state import (
    ActiveTurnState,
    ClientRuntimeCapabilities,
    PendingClientRequestState,
    PreparedFsClientRequest,
    PromptDirectives,
    ProtocolOutcome,
    SessionState,
    ToolCallState,
)

__all__ = [
    "ACPProtocol",
    "ProtocolOutcome",
    "SessionState",
    "ToolCallState",
    "ActiveTurnState",
    "PromptDirectives",
    "PendingClientRequestState",
    "PreparedFsClientRequest",
    "ClientRuntimeCapabilities",
]
