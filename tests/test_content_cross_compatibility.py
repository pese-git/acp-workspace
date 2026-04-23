"""Cross-compatibility тесты для Content типов между server и client.

Проверяет что Content созданный в server может быть прочитан в client
и наоборот, обеспечивая совместимость между обоими проектами.
"""

import base64
import json
import sys
from pathlib import Path

# Добавляем оба проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent / "acp-server" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "acp-client" / "src"))

from acp_server.protocol.content import (
    AudioContent as ServerAudioContent,
    EmbeddedResourceContent as ServerEmbeddedResourceContent,
    ImageContent as ServerImageContent,
    ResourceLinkContent as ServerResourceLinkContent,
    TextContent as ServerTextContent,
    TextResource as ServerTextResource,
)
from acp_client.domain.content import (
    AudioContent as ClientAudioContent,
    EmbeddedResourceContent as ClientEmbeddedResourceContent,
    ImageContent as ClientImageContent,
    ResourceLinkContent as ClientResourceLinkContent,
    TextContent as ClientTextContent,
)


def test_server_client_text_compatibility() -> None:
    """Проверка что TextContent созданный в server может быть прочитан в client."""
    # Создаем Content в server
    server_content = ServerTextContent(text="Message from server")

    # Сериализуем в JSON (как если бы передавали через wire protocol)
    server_data = server_content.model_dump(exclude_none=True)
    json_str = json.dumps(server_data)

    # Десериализуем в client
    client_data = json.loads(json_str)
    client_content = ClientTextContent.model_validate(client_data)

    # Проверяем идентичность данных
    assert client_content.type == server_content.type
    assert client_content.text == server_content.text


def test_server_client_image_compatibility() -> None:
    """Проверка совместимости ImageContent между server и client."""
    # Создаем в server
    png_data = base64.b64encode(b"PNG_DATA").decode()
    server_image = ServerImageContent(mimeType="image/png", data=png_data)

    # Передаем через JSON
    server_data = server_image.model_dump(exclude_none=True)
    json_str = json.dumps(server_data)

    # Восстанавливаем в client
    client_data = json.loads(json_str)
    client_image = ClientImageContent.model_validate(client_data)

    # Проверяем совместимость
    assert client_image.type == server_image.type
    assert client_image.mimeType == server_image.mimeType
    assert client_image.data == server_image.data


def test_server_client_audio_compatibility() -> None:
    """Проверка совместимости AudioContent между server и client."""
    # Создаем в server
    audio_data = base64.b64encode(b"AUDIO_DATA").decode()
    server_audio = ServerAudioContent(mimeType="audio/mpeg", data=audio_data)

    # Передаем через JSON
    server_data = server_audio.model_dump(exclude_none=True)
    json_str = json.dumps(server_data)

    # Восстанавливаем в client
    client_data = json.loads(json_str)
    client_audio = ClientAudioContent.model_validate(client_data)

    # Проверяем совместимость
    assert client_audio.type == server_audio.type
    assert client_audio.mimeType == server_audio.mimeType
    assert client_audio.data == server_audio.data


def test_server_client_resource_link_compatibility() -> None:
    """Проверка совместимости ResourceLinkContent между server и client."""
    # Создаем в server
    server_link = ServerResourceLinkContent(
        uri="file:///document.pdf",
        name="document.pdf",
        mimeType="application/pdf",
    )

    # Передаем через JSON
    server_data = server_link.model_dump(exclude_none=True)
    json_str = json.dumps(server_data)

    # Восстанавливаем в client
    client_data = json.loads(json_str)
    client_link = ClientResourceLinkContent.model_validate(client_data)

    # Проверяем совместимость
    assert client_link.type == server_link.type
    assert client_link.uri == server_link.uri
    assert client_link.name == server_link.name
    assert client_link.mimeType == server_link.mimeType


def test_server_client_embedded_resource_compatibility() -> None:
    """Проверка совместимости EmbeddedResourceContent между server и client."""
    # Создаем в server
    resource = ServerTextResource(
        uri="code:///example.py",
        name="example.py",
        mimeType="text/plain",
        text="print('hello')",
    )
    server_embedded = ServerEmbeddedResourceContent(resource=resource)

    # Передаем через JSON
    server_data = server_embedded.model_dump(exclude_none=True)
    json_str = json.dumps(server_data)

    # Восстанавливаем в client
    client_data = json.loads(json_str)
    client_embedded = ClientEmbeddedResourceContent.model_validate(client_data)

    # Проверяем совместимость
    assert client_embedded.type == server_embedded.type
    assert client_embedded.resource.uri == server_embedded.resource.uri
    assert client_embedded.resource.text == server_embedded.resource.text


def test_mixed_content_compatibility() -> None:
    """Проверка совместимости смешанного контента."""
    # Создаем список контента в server
    server_contents = [
        ServerTextContent(text="Check this:"),
        ServerImageContent(
            mimeType="image/png",
            data=base64.b64encode(b"PNG").decode(),
        ),
        ServerAudioContent(
            mimeType="audio/mpeg",
            data=base64.b64encode(b"AUDIO").decode(),
        ),
    ]

    # Сериализуем каждый элемент
    server_datas = [content.model_dump(exclude_none=True) for content in server_contents]
    json_str = json.dumps(server_datas)

    # Десериализуем в client
    client_datas = json.loads(json_str)

    # Восстанавливаем каждый элемент в client по типу
    client_contents = []
    for data in client_datas:
        content_type = data.get("type")
        if content_type == "text":
            client_contents.append(ClientTextContent.model_validate(data))
        elif content_type == "image":
            client_contents.append(ClientImageContent.model_validate(data))
        elif content_type == "audio":
            client_contents.append(ClientAudioContent.model_validate(data))

    # Проверяем что все элементы восстановлены корректно
    assert len(client_contents) == 3
    assert client_contents[0].text == "Check this:"
    assert client_contents[1].mimeType == "image/png"
    assert client_contents[2].mimeType == "audio/mpeg"


def test_unicode_content_cross_compatibility() -> None:
    """Проверка совместимости Unicode контента между server и client."""
    unicode_texts = [
        "Hello 世界",
        "Привет мир",
        "مرحبا بالعالم",
        "🚀 Emoji test 🎉",
    ]

    for text in unicode_texts:
        server_content = ServerTextContent(text=text)
        server_data = server_content.model_dump(exclude_none=True)
        json_str = json.dumps(server_data)
        client_data = json.loads(json_str)
        client_content = ClientTextContent.model_validate(client_data)

        assert client_content.text == text


def test_content_type_consistency() -> None:
    """Проверка что type поле консистентно между server и client."""
    server_contents = [
        (ServerTextContent(text="test"), "text"),
        (
            ServerImageContent(
                mimeType="image/png",
                data=base64.b64encode(b"DATA").decode(),
            ),
            "image",
        ),
        (
            ServerAudioContent(
                mimeType="audio/mpeg",
                data=base64.b64encode(b"DATA").decode(),
            ),
            "audio",
        ),
        (ServerResourceLinkContent(uri="test://uri", name="test"), "resource_link"),
    ]

    for server_content, expected_type in server_contents:
        # Проверяем type в server
        server_data = server_content.model_dump(exclude_none=True)
        assert server_data["type"] == expected_type

        # Передаем через JSON
        json_str = json.dumps(server_data)
        client_data = json.loads(json_str)

        # Проверяем type в client
        assert client_data["type"] == expected_type


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
