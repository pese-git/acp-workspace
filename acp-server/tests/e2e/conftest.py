"""Fixtures и конфигурация для E2E тестов Content Integration."""

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from acp_server.protocol.content.extractor import ContentExtractor
from acp_server.protocol.content.formatter import ContentFormatter
from acp_server.protocol.content.validator import ContentValidator
from acp_server.tools.base import ToolExecutionResult


@pytest.fixture
def mock_tool_executor() -> MagicMock:
    """Мок executor для генерации ToolExecutionResult.
    
    Returns:
        MagicMock объект для создания результатов выполнения инструментов
    """
    executor = MagicMock()
    executor.execute = AsyncMock()
    return executor


@pytest.fixture
def content_extractor() -> ContentExtractor:
    """Экземпляр ContentExtractor для E2E тестов.
    
    Returns:
        Инициализированный ContentExtractor
    """
    return ContentExtractor()


@pytest.fixture
def content_validator() -> ContentValidator:
    """Экземпляр ContentValidator для E2E тестов.
    
    Returns:
        Инициализированный ContentValidator
    """
    return ContentValidator()


@pytest.fixture
def content_formatter() -> ContentFormatter:
    """Экземпляр ContentFormatter для E2E тестов.
    
    Returns:
        Инициализированный ContentFormatter
    """
    return ContentFormatter()


@pytest.fixture
def sample_content_data() -> dict[str, Any]:
    """Fixture с примерами всех 6 типов content.
    
    Returns:
        Словарь с примерами content для всех типов
    """
    return {
        "text": {
            "type": "text",
            "text": "This is sample text content for testing."
        },
        "diff": {
            "type": "diff",
            "path": "/tmp/test_file.py",
            "diff": "--- a/test_file.py\n+++ b/test_file.py\n@@ -1 +1 @@\n-old line\n+new line"
        },
        "image": {
            "type": "image",
            "data": base64.b64encode(b"fake_png_data").decode("utf-8"),
            "format": "png",
            "alt_text": "Test image"
        },
        "audio": {
            "type": "audio",
            "data": base64.b64encode(b"fake_audio_data").decode("utf-8"),
            "format": "mp3"
        },
        "embedded": {
            "type": "embedded",
            "content": [
                {"type": "text", "text": "Embedded text content"}
            ]
        },
        "resource_link": {
            "type": "resource_link",
            "uri": "https://example.com/resource"
        }
    }


@pytest.fixture
def sample_tool_result_text(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с text content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с text content
    """
    return ToolExecutionResult(
        success=True,
        output="Text output",
        content=[sample_content_data["text"]]
    )


@pytest.fixture
def sample_tool_result_diff(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с diff content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с diff content
    """
    return ToolExecutionResult(
        success=True,
        output="Diff output",
        content=[sample_content_data["diff"]]
    )


@pytest.fixture
def sample_tool_result_image(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с image content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с image content
    """
    return ToolExecutionResult(
        success=True,
        output="Image output",
        content=[sample_content_data["image"]]
    )


@pytest.fixture
def sample_tool_result_audio(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с audio content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с audio content
    """
    return ToolExecutionResult(
        success=True,
        output="Audio output",
        content=[sample_content_data["audio"]]
    )


@pytest.fixture
def sample_tool_result_embedded(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с embedded content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с embedded content
    """
    return ToolExecutionResult(
        success=True,
        output="Embedded output",
        content=[sample_content_data["embedded"]]
    )


@pytest.fixture
def sample_tool_result_resource_link(sample_content_data: dict[str, Any]) -> ToolExecutionResult:
    """ToolExecutionResult с resource_link content.
    
    Args:
        sample_content_data: Fixture с примерами content
        
    Returns:
        ToolExecutionResult с resource_link content
    """
    return ToolExecutionResult(
        success=True,
        output="Resource link output",
        content=[sample_content_data["resource_link"]]
    )
