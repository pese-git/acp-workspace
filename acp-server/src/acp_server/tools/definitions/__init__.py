"""Определения инструментов (tool definitions) для регистрации в реестре.

Включает определения для файловых и терминальных инструментов.
"""

from acp_server.tools.definitions.filesystem import FileSystemToolDefinitions
from acp_server.tools.definitions.terminal import TerminalToolDefinitions

__all__ = [
    "FileSystemToolDefinitions",
    "TerminalToolDefinitions",
]
