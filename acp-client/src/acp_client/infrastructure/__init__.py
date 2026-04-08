"""Infrastructure layer модули для ACP-клиента.

Содержит реализации низкоуровневых компонентов:
- Транспортные адаптеры (WebSocket и т.д.)
- Парсеры сообщений
- Обработчики ошибок
- Структурированное логирование
"""

from .handler_registry import (
    FsReadHandler,
    FsWriteHandler,
    HandlerRegistry,
    PermissionHandler,
    TerminalCreateHandler,
    TerminalKillHandler,
    TerminalOutputHandler,
    TerminalReleaseHandler,
    TerminalWaitHandler,
)
from .logging_config import OperationTimer, get_logger, setup_logging
from .message_parser import MessageParser
from .transport import Transport, WebSocketTransport

__all__ = [
    "Transport",
    "WebSocketTransport",
    "MessageParser",
    "HandlerRegistry",
    "PermissionHandler",
    "FsReadHandler",
    "FsWriteHandler",
    "TerminalCreateHandler",
    "TerminalOutputHandler",
    "TerminalWaitHandler",
    "TerminalReleaseHandler",
    "TerminalKillHandler",
    "setup_logging",
    "get_logger",
    "OperationTimer",
]
