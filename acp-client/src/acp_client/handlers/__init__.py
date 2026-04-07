"""Обработчики для ACP методов и запросов."""

from typing import TYPE_CHECKING

from .filesystem import handle_server_fs_request
from .permissions import build_permission_result
from .terminal import handle_server_terminal_request

if TYPE_CHECKING:
    from ..client import (
        FsReadHandler,
        FsWriteHandler,
        PermissionHandler,
        TerminalCreateHandler,
        TerminalKillHandler,
        TerminalOutputHandler,
        TerminalReleaseHandler,
        TerminalWaitHandler,
    )

__all__ = [
    "build_permission_result",
    "handle_server_fs_request",
    "handle_server_terminal_request",
]
