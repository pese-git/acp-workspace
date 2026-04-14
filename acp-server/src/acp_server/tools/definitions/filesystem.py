"""Определения для файловых инструментов (fs/*)."""

from __future__ import annotations

from acp_server.tools.base import ToolDefinition


class FileSystemToolDefinitions:
    """Фабрика для создания определений файловых инструментов.
    
    Поддерживает:
    - fs/read_text_file: Чтение текстовых файлов
    - fs/write_text_file: Запись текстовых файлов с diff tracking
    """

    @staticmethod
    def read_text_file() -> ToolDefinition:
        """Создать определение для инструмента fs/read_text_file.
        
        Позволяет LLM читать содержимое текстовых файлов в окружении клиента
        с поддержкой partial reads (line и limit).
        
        Returns:
            ToolDefinition для регистрации в реестре.
        """
        return ToolDefinition(
            name="read_text_file",
            description=(
                "Read text file content from client filesystem. "
                "Supports line numbers (1-based) and limits for partial reads."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative file path",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Starting line number (1-based, optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (optional)",
                    },
                    "operation": {
                        "type": "string",
                        "description": "Internal: operation type (read)",
                    },
                },
                "required": ["path"],
            },
            kind="read",
            requires_permission=True,
        )

    @staticmethod
    def write_text_file() -> ToolDefinition:
        """Создать определение для инструмента fs/write_text_file.
        
        Позволяет LLM создавать и обновлять текстовые файлы в окружении клиента
        с автоматическим отслеживанием изменений (diff).
        
        Returns:
            ToolDefinition для регистрации в реестре.
        """
        return ToolDefinition(
            name="write_text_file",
            description=(
                "Write or update text file in client filesystem. "
                "Supports diff generation for tracking changes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative file path",
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write",
                    },
                    "operation": {
                        "type": "string",
                        "description": "Internal: operation type (write)",
                    },
                },
                "required": ["path", "content"],
            },
            kind="write",
            requires_permission=True,
        )
