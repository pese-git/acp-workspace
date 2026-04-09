"""Infrastructure layer модули для ACP-клиента.

Содержит реализации низкоуровневых компонентов:
- Транспортные адаптеры (WebSocket и т.д.)
- Парсеры сообщений
- Обработчики ошибок
- Структурированное логирование
- DI контейнер
- Repositories
"""

from .di_container import ContainerBuilder, DIContainer, DIError, Scope
from .handler_registry import (
    FsReadHandler,
    FsWriteHandler,
    Handler,
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
from .repositories import InMemorySessionRepository
from .services import ACPTransportService
from .transport import Transport, WebSocketTransport

__all__ = [
    # Transport
    "Transport",
    "WebSocketTransport",
    # Parsing
    "MessageParser",
    # Handlers
    "Handler",
    "HandlerRegistry",
    "PermissionHandler",
    "FsReadHandler",
    "FsWriteHandler",
    "TerminalCreateHandler",
    "TerminalOutputHandler",
    "TerminalWaitHandler",
    "TerminalReleaseHandler",
    "TerminalKillHandler",
    # Logging
    "setup_logging",
    "get_logger",
    "OperationTimer",
    # DI
    "DIContainer",
    "ContainerBuilder",
    "Scope",
    "DIError",
    # Repositories
    "InMemorySessionRepository",
    # Services
    "ACPTransportService",
]
