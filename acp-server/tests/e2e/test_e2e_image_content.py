"""E2E тесты для image content обработки."""

import base64

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestImageContentE2E(BaseE2EContentTest):
    """E2E тесты для image content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_image_content_openai_full_cycle(
        self, sample_tool_result_image: ToolExecutionResult
    ) -> None:
        """E2E-005: Image content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение image content из результата инструмента
        - Валидацию image content (наличие data и format)
        - Форматирование для OpenAI API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с image content
        tool_call_id = "tc_image_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_image,
            tool_call_id=tool_call_id,
            content_type="image",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "image", "openai")
        
        # Дополнительные проверки для image контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что image не пуст
        image_item = extracted.content_items[0]
        assert image_item["type"] == "image"
        assert image_item["data"], "Image content should have data"
        assert image_item["format"], "Image content should have format"
        assert isinstance(image_item["data"], str)
        assert isinstance(image_item["format"], str)
        
        # Проверить что data это валидный base64
        try:
            base64.b64decode(image_item["data"])
        except Exception as e:
            pytest.fail(f"Image data is not valid base64: {e}")
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        # Content должен содержать информацию об изображении
        assert "Image:" in formatted["content"]

    @pytest.mark.asyncio
    async def test_image_content_anthropic_full_cycle(
        self, sample_tool_result_image: ToolExecutionResult
    ) -> None:
        """E2E-006: Image content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение image content из результата инструмента
        - Валидацию image content (наличие data и format)
        - Форматирование для Anthropic API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с image content
        tool_call_id = "tc_image_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_image,
            tool_call_id=tool_call_id,
            content_type="image",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "image", "anthropic")
        
        # Дополнительные проверки для image контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что image не пуст
        image_item = extracted.content_items[0]
        assert image_item["type"] == "image"
        assert image_item["data"], "Image content should have data"
        assert image_item["format"], "Image content should have format"
        assert isinstance(image_item["data"], str)
        assert isinstance(image_item["format"], str)
        
        # Проверить что data это валидный base64
        try:
            base64.b64decode(image_item["data"])
        except Exception as e:
            pytest.fail(f"Image data is not valid base64: {e}")
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        # Content должен содержать информацию об изображении
        assert "Image:" in tool_result_item["content"]

    @pytest.mark.asyncio
    async def test_image_content_with_alt_text_openai(self) -> None:
        """Дополнительный тест: Image с alt_text для OpenAI.
        
        Проверяет обработку изображений с дополнительной информацией.
        """
        # Создать tool result с custom image content
        image_data = base64.b64encode(b"fake_png_image_bytes").decode("utf-8")
        
        tool_result = create_tool_result_with_content(
            "image",
            data=image_data,
            format="png",
            alt_text="A beautiful landscape"
        )
        
        tool_call_id = "tc_custom_image_openai"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="image",
            provider="openai",
        )
        
        # Проверить что все данные сохранились
        extracted = cycle_result["extracted"]
        image_item = extracted.content_items[0]
        assert image_item["data"] == image_data
        assert image_item["format"] == "png"
        assert image_item["alt_text"] == "A beautiful landscape"

    @pytest.mark.asyncio
    async def test_image_content_with_alt_text_anthropic(self) -> None:
        """Дополнительный тест: Image с alt_text для Anthropic.
        
        Проверяет обработку изображений с дополнительной информацией.
        """
        # Создать tool result с custom image content
        image_data = base64.b64encode(b"fake_jpg_image_bytes").decode("utf-8")
        
        tool_result = create_tool_result_with_content(
            "image",
            data=image_data,
            format="jpeg",
            alt_text="A diagram"
        )
        
        tool_call_id = "tc_custom_image_anthropic"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="image",
            provider="anthropic",
        )
        
        # Проверить что все данные сохранились
        extracted = cycle_result["extracted"]
        image_item = extracted.content_items[0]
        assert image_item["data"] == image_data
        assert image_item["format"] == "jpeg"
        assert image_item["alt_text"] == "A diagram"
