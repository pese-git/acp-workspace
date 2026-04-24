"""Модуль протокола ACP.

Инкапсулирует в-memory реализацию ACP-протокола для demo/интеграционных сценариев.
"""

from .core import ACPProtocol
from .session_factory import SessionFactory
from .state import (
    ActiveTurnState,
    ClientRuntimeCapabilities,
    LLMLoopResult,
    PendingClientRequestState,
    PreparedFsClientRequest,
    PromptDirectives,
    ProtocolOutcome,
    SessionState,
    ToolCallState,
    ToolResult,
)

__all__ = [
    "ACPProtocol",
    "SessionFactory",
    "ProtocolOutcome",
    "SessionState",
    "ToolCallState",
    "ActiveTurnState",
    "PromptDirectives",
    "PendingClientRequestState",
    "PreparedFsClientRequest",
    "ClientRuntimeCapabilities",
    "ToolResult",
    "LLMLoopResult",
]
