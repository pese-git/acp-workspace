"""E2E тесты для embedded content обработки."""

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestEmbeddedContentE2E(BaseE2EContentTest):
    """E2E тесты для embedded content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_embedded_content_openai_full_cycle(
        self, sample_tool_result_embedded: ToolExecutionResult
    ) -> None:
        """E2E-009: Embedded content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение embedded content из результата инструмента
        - Валидацию embedded content (наличие content поля)
        - Форматирование для OpenAI API
        - Рекурсивную обработку вложенного контента
        """
        # 1. Setup: использовать fixture с embedded content
        tool_call_id = "tc_embedded_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_embedded,
            tool_call_id=tool_call_id,
            content_type="embedded",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "embedded", "openai")
        
        # Дополнительные проверки для embedded контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что embedded не пуст
        embedded_item = extracted.content_items[0]
        assert embedded_item["type"] == "embedded"
        assert embedded_item["content"], "Embedded content should have content"
        assert isinstance(embedded_item["content"], list)
        assert len(embedded_item["content"]) > 0
        
        # Проверить что вложенный контент валидный
        inner_content = embedded_item["content"][0]
        assert "type" in inner_content
        valid_types = {"text", "diff", "image", "audio", "embedded", "resource_link"}
        assert inner_content["type"] in valid_types
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        # Content должен содержать информацию об embedded контенте
        assert "Embedded" in formatted["content"]

    @pytest.mark.asyncio
    async def test_embedded_content_anthropic_full_cycle(
        self, sample_tool_result_embedded: ToolExecutionResult
    ) -> None:
        """E2E-010: Embedded content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение embedded content из результата инструмента
        - Валидацию embedded content (наличие content поля)
        - Форматирование для Anthropic API
        - Рекурсивную обработку вложенного контента
        """
        # 1. Setup: использовать fixture с embedded content
        tool_call_id = "tc_embedded_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_embedded,
            tool_call_id=tool_call_id,
            content_type="embedded",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "embedded", "anthropic")
        
        # Дополнительные проверки для embedded контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что embedded не пуст
        embedded_item = extracted.content_items[0]
        assert embedded_item["type"] == "embedded"
        assert embedded_item["content"], "Embedded content should have content"
        assert isinstance(embedded_item["content"], list)
        assert len(embedded_item["content"]) > 0
        
        # Проверить что вложенный контент валидный
        inner_content = embedded_item["content"][0]
        assert "type" in inner_content
        valid_types = {"text", "diff", "image", "audio", "embedded", "resource_link"}
        assert inner_content["type"] in valid_types
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        # Content должен содержать информацию об embedded контенте
        assert "Embedded" in tool_result_item["content"]

    @pytest.mark.asyncio
    async def test_embedded_content_with_multiple_items_openai(self) -> None:
        """Дополнительный тест: Embedded с несколькими items для OpenAI.
        
        Проверяет обработку embedded контента с несколькими вложенными items.
        """
        # Создать tool result с custom embedded content (несколько items)
        tool_result = create_tool_result_with_content(
            "embedded",
            content=[
                {"type": "text", "text": "First embedded item"},
                {"type": "text", "text": "Second embedded item"}
            ]
        )
        
        tool_call_id = "tc_embedded_multi_openai"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="embedded",
            provider="openai",
        )
        
        # Проверить что все items сохранились
        extracted = cycle_result["extracted"]
        embedded_item = extracted.content_items[0]
        assert len(embedded_item["content"]) == 2
        assert embedded_item["content"][0]["text"] == "First embedded item"
        assert embedded_item["content"][1]["text"] == "Second embedded item"

    @pytest.mark.asyncio
    async def test_embedded_content_with_multiple_items_anthropic(self) -> None:
        """Дополнительный тест: Embedded с несколькими items для Anthropic.
        
        Проверяет обработку embedded контента с несколькими вложенными items.
        """
        # Создать tool result с custom embedded content (несколько items)
        tool_result = create_tool_result_with_content(
            "embedded",
            content=[
                {"type": "text", "text": "Item 1"},
                {"type": "text", "text": "Item 2"},
                {"type": "text", "text": "Item 3"}
            ]
        )
        
        tool_call_id = "tc_embedded_multi_anthropic"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="embedded",
            provider="anthropic",
        )
        
        # Проверить что все items сохранились
        extracted = cycle_result["extracted"]
        embedded_item = extracted.content_items[0]
        assert len(embedded_item["content"]) == 3
        assert embedded_item["content"][0]["text"] == "Item 1"
        assert embedded_item["content"][1]["text"] == "Item 2"
        assert embedded_item["content"][2]["text"] == "Item 3"
