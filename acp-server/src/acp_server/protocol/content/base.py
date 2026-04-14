"""Базовые классы для Content типов ACP протокола.

Этот модуль определяет базовый класс ContentBlock и вспомогательные
типы для работы с встроенными ресурсами (TextResource, BlobResource).
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextResource(BaseModel):
    """Текстовый ресурс внутри EmbeddedResourceContent.

    Используется для встраивания текстового содержимого (например, исходного кода)
    прямо в сообщение.

    Attributes:
        uri: Универсальный идентификатор ресурса (например, file:///path/to/file.py).
        text: Содержимое текстового ресурса.
        mimeType: Опциональный MIME-тип ресурса (например, text/x-python).
    """

    uri: str = Field(..., description="URI ресурса")
    text: str = Field(..., description="Содержимое текстового ресурса")
    mimeType: str | None = Field(None, description="MIME-тип ресурса (опционально)")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Валидирует URI на непустоту."""
        if not v or not v.strip():
            raise ValueError("URI не может быть пустым")
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Валидирует текст на непустоту."""
        if not isinstance(v, str):
            raise ValueError("text должен быть строкой")
        return v


class BlobResource(BaseModel):
    """Бинарный ресурс внутри EmbeddedResourceContent.

    Используется для встраивания бинарного содержимого (например, изображений)
    прямо в сообщение в виде base64.

    Attributes:
        uri: Универсальный идентификатор ресурса.
        blob: Base64-кодированные бинарные данные.
        mimeType: Опциональный MIME-тип ресурса.
    """

    uri: str = Field(..., description="URI ресурса")
    blob: str = Field(..., description="Base64-кодированные бинарные данные")
    mimeType: str | None = Field(None, description="MIME-тип ресурса (опционально)")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Валидирует URI на непустоту."""
        if not v or not v.strip():
            raise ValueError("URI не может быть пустым")
        return v

    @field_validator("blob")
    @classmethod
    def validate_blob(cls, v: str) -> str:
        """Валидирует blob на непустоту."""
        if not v or not v.strip():
            raise ValueError("blob не может быть пустым")
        return v


# Объединение вариантов ресурсов
EmbeddedResource = TextResource | BlobResource


class ContentBlock(BaseModel):
    """Базовый класс для всех Content типов.

    Используется как discriminated union для полиморфной десериализации.
    Каждый конкретный тип контента наследуется от этого класса.

    Примечание: Это базовый класс для типизации. Фактические объекты
    будут экземплярами конкретных подклассов (TextContent, ImageContent и т.д.).
    """

    type: str = Field(..., description="Тип контента")

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
    )
