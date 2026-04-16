"""E2E тесты для text content обработки."""

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestTextContentE2E(BaseE2EContentTest):
    """E2E тесты для text content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_text_content_openai_full_cycle(
        self, sample_tool_result_text: ToolExecutionResult
    ) -> None:
        """E2E-001: Text content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение text content из результата инструмента
        - Валидацию text content
        - Форматирование для OpenAI API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с text content
        tool_call_id = "tc_text_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_text,
            tool_call_id=tool_call_id,
            content_type="text",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "text", "openai")
        
        # Дополнительные проверки для text контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что text не пуст
        text_item = extracted.content_items[0]
        assert text_item["type"] == "text"
        assert text_item["text"], "Text content should not be empty"
        assert isinstance(text_item["text"], str)
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        assert formatted["content"] == text_item["text"]

    @pytest.mark.asyncio
    async def test_text_content_anthropic_full_cycle(
        self, sample_tool_result_text: ToolExecutionResult
    ) -> None:
        """E2E-002: Text content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение text content из результата инструмента
        - Валидацию text content
        - Форматирование для Anthropic API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с text content
        tool_call_id = "tc_text_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_text,
            tool_call_id=tool_call_id,
            content_type="text",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "text", "anthropic")
        
        # Дополнительные проверки для text контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что text не пуст
        text_item = extracted.content_items[0]
        assert text_item["type"] == "text"
        assert text_item["text"], "Text content should not be empty"
        assert isinstance(text_item["text"], str)
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        assert tool_result_item["content"] == text_item["text"]

    @pytest.mark.asyncio
    async def test_text_content_custom_openai(self) -> None:
        """Дополнительный тест: Custom text content для OpenAI.
        
        Проверяет обработку текста с различными специальными символами.
        """
        # Создать tool result с custom text content
        custom_text = "Line 1\\nLine 2\\nLine 3"
        tool_result = create_tool_result_with_content(
            "text",
            text=custom_text
        )
        
        tool_call_id = "tc_custom_text_001"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="text",
            provider="openai",
        )
        
        # Проверить что текст сохранился
        extracted = cycle_result["extracted"]
        assert extracted.content_items[0]["text"] == custom_text

    @pytest.mark.asyncio
    async def test_text_content_custom_anthropic(self) -> None:
        """Дополнительный тест: Custom text content для Anthropic.
        
        Проверяет обработку текста с различными специальными символами.
        """
        # Создать tool result с custom text content
        custom_text = "Custom text with special chars: @#$%"
        tool_result = create_tool_result_with_content(
            "text",
            text=custom_text
        )
        
        tool_call_id = "tc_custom_text_002"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="text",
            provider="anthropic",
        )
        
        # Проверить что текст сохранился
        extracted = cycle_result["extracted"]
        assert extracted.content_items[0]["text"] == custom_text
