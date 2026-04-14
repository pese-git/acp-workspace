"""Content типы для ACP протокола.

Этот пакет предоставляет классы для представления различных типов контента
в ACP протоколе: текст, изображения, аудио, встроенные ресурсы и ссылки.

Основные классы:
- TextContent: Текстовый контент
- ImageContent: Контент с изображением
- AudioContent: Контент с аудиоданными
- EmbeddedResourceContent: Встроенный ресурс
- ResourceLinkContent: Ссылка на ресурс

Вспомогательные классы:
- TextResource: Текстовый ресурс для встраивания
- BlobResource: Бинарный ресурс для встраивания
- ContentBlock: Базовый тип для всех контентов (для типизации)

Примеры использования:

    from acp_server.protocol.content import (
        TextContent,
        ImageContent,
        ResourceLinkContent,
    )

    # Создание текстового контента
    text = TextContent(text="Hello, world!")

    # Создание контента с изображением
    image = ImageContent(
        mimeType="image/png",
        data="iVBORw0KGgo..."
    )

    # Создание ссылки на ресурс
    link = ResourceLinkContent(
        uri="file:///document.pdf",
        name="document.pdf"
    )
"""

from acp_server.protocol.content.audio import AudioContent
from acp_server.protocol.content.base import (
    BlobResource,
    ContentBlock,
    EmbeddedResource,
    TextResource,
)
from acp_server.protocol.content.embedded import EmbeddedResourceContent
from acp_server.protocol.content.image import ImageContent
from acp_server.protocol.content.resource_link import ResourceLinkContent
from acp_server.protocol.content.text import TextContent

__all__ = [
    # Основные Content типы
    "TextContent",
    "ImageContent",
    "AudioContent",
    "EmbeddedResourceContent",
    "ResourceLinkContent",
    # Вспомогательные классы для ресурсов
    "TextResource",
    "BlobResource",
    # Типы для использования в типизации
    "ContentBlock",
    "EmbeddedResource",
]
