"""E2E тесты для resource_link content обработки."""

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestResourceLinkContentE2E(BaseE2EContentTest):
    """E2E тесты для resource_link content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_resource_link_content_openai_full_cycle(
        self, sample_tool_result_resource_link: ToolExecutionResult
    ) -> None:
        """E2E-011: Resource link content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение resource_link content из результата инструмента
        - Валидацию resource_link content (наличие uri)
        - Форматирование для OpenAI API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с resource_link content
        tool_call_id = "tc_resource_link_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_resource_link,
            tool_call_id=tool_call_id,
            content_type="resource_link",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "resource_link", "openai")
        
        # Дополнительные проверки для resource_link контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что resource_link не пуст
        resource_link_item = extracted.content_items[0]
        assert resource_link_item["type"] == "resource_link"
        assert resource_link_item["uri"], "Resource link should have uri"
        assert isinstance(resource_link_item["uri"], str)
        
        # Проверить что URI валидный формат
        uri = resource_link_item["uri"]
        is_valid_uri = (
            uri.startswith("http://")
            or uri.startswith("https://")
            or uri.startswith("file://")
        )
        assert is_valid_uri, f"Invalid URI format: {uri}"
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        # Content должен содержать информацию о ресурсе
        assert "Resource:" in formatted["content"]

    @pytest.mark.asyncio
    async def test_resource_link_content_anthropic_full_cycle(
        self, sample_tool_result_resource_link: ToolExecutionResult
    ) -> None:
        """E2E-012: Resource link content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение resource_link content из результата инструмента
        - Валидацию resource_link content (наличие uri)
        - Форматирование для Anthropic API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с resource_link content
        tool_call_id = "tc_resource_link_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_resource_link,
            tool_call_id=tool_call_id,
            content_type="resource_link",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "resource_link", "anthropic")
        
        # Дополнительные проверки для resource_link контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что resource_link не пуст
        resource_link_item = extracted.content_items[0]
        assert resource_link_item["type"] == "resource_link"
        assert resource_link_item["uri"], "Resource link should have uri"
        assert isinstance(resource_link_item["uri"], str)
        
        # Проверить что URI валидный формат
        uri = resource_link_item["uri"]
        is_valid_uri = (
            uri.startswith("http://")
            or uri.startswith("https://")
            or uri.startswith("file://")
        )
        assert is_valid_uri, f"Invalid URI format: {uri}"
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        # Content должен содержать информацию о ресурсе
        assert "Resource:" in tool_result_item["content"]

    @pytest.mark.asyncio
    async def test_resource_link_content_file_uri_openai(self) -> None:
        """Дополнительный тест: Resource link с file:// URI для OpenAI.
        
        Проверяет обработку различных типов URI.
        """
        # Создать tool result с custom resource_link content (file URI)
        file_uri = "file:///home/user/documents/report.pdf"
        
        tool_result = create_tool_result_with_content(
            "resource_link",
            uri=file_uri
        )
        
        tool_call_id = "tc_resource_link_file_openai"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="resource_link",
            provider="openai",
        )
        
        # Проверить что URI сохранился
        extracted = cycle_result["extracted"]
        resource_link_item = extracted.content_items[0]
        assert resource_link_item["uri"] == file_uri

    @pytest.mark.asyncio
    async def test_resource_link_content_https_uri_anthropic(self) -> None:
        """Дополнительный тест: Resource link с https:// URI для Anthropic.
        
        Проверяет обработку различных типов URI.
        """
        # Создать tool result с custom resource_link content (https URI)
        https_uri = "https://api.example.com/v1/resource/12345"
        
        tool_result = create_tool_result_with_content(
            "resource_link",
            uri=https_uri
        )
        
        tool_call_id = "tc_resource_link_https_anthropic"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="resource_link",
            provider="anthropic",
        )
        
        # Проверить что URI сохранился
        extracted = cycle_result["extracted"]
        resource_link_item = extracted.content_items[0]
        assert resource_link_item["uri"] == https_uri
