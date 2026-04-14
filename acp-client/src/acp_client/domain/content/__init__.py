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

    from acp_client.domain.content import (
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

from acp_client.domain.content.audio import AudioContent
from acp_client.domain.content.base import (
    BlobResource,
    ContentBlock,
    EmbeddedResource,
    TextResource,
)
from acp_client.domain.content.embedded import EmbeddedResourceContent
from acp_client.domain.content.image import ImageContent
from acp_client.domain.content.resource_link import ResourceLinkContent
from acp_client.domain.content.text import TextContent

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
