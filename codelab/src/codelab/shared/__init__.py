"""Shared модули для CodeLab.

Этот пакет содержит общие модули, используемые как сервером,
так и клиентом CodeLab:
- messages — JSON-RPC сообщения для ACP протокола
- logging — структурированное логирование
- content — типы контента для передачи данных

Пример использования:
    from codelab.shared import ACPMessage, JsonRpcError, setup_logging
    from codelab.shared.content import TextContent, ImageContent
"""

# Re-exports из модуля сообщений
from codelab.shared.messages import (
    ACPMessage,
    JsonRpcError,
    JsonRpcId,
    is_parse_error,
)

# Re-exports из модуля логирования
from codelab.shared.logging import (
    get_codelab_dir,
    get_logs_dir,
    setup_logging,
)

# Re-exports из модуля content
from codelab.shared.content import (
    # Базовые типы ресурсов
    TextResource,
    BlobResource,
    EmbeddedResource,
    ContentBlock,
    # Типы контента
    TextContent,
    ImageContent,
    AudioContent,
    EmbeddedResourceContent,
    ResourceLinkContent,
    # Константы
    ALLOWED_IMAGE_MIME_TYPES,
    ALLOWED_AUDIO_MIME_TYPES,
)

__all__ = [
    # Messages
    "ACPMessage",
    "JsonRpcError",
    "JsonRpcId",
    "is_parse_error",
    # Logging
    "setup_logging",
    "get_codelab_dir",
    "get_logs_dir",
    # Content base types
    "TextResource",
    "BlobResource",
    "EmbeddedResource",
    "ContentBlock",
    # Content types
    "TextContent",
    "ImageContent",
    "AudioContent",
    "EmbeddedResourceContent",
    "ResourceLinkContent",
    # Constants
    "ALLOWED_IMAGE_MIME_TYPES",
    "ALLOWED_AUDIO_MIME_TYPES",
]
