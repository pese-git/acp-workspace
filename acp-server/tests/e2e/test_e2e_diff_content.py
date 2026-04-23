"""E2E тесты для diff content обработки."""

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestDiffContentE2E(BaseE2EContentTest):
    """E2E тесты для diff content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_diff_content_openai_full_cycle(
        self, sample_tool_result_diff: ToolExecutionResult
    ) -> None:
        """E2E-003: Diff content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение diff content из результата инструмента
        - Валидацию diff content (наличие path и diff)
        - Форматирование для OpenAI API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с diff content
        tool_call_id = "tc_diff_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_diff,
            tool_call_id=tool_call_id,
            content_type="diff",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "diff", "openai")
        
        # Дополнительные проверки для diff контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что diff не пуст
        diff_item = extracted.content_items[0]
        assert diff_item["type"] == "diff"
        assert diff_item["path"], "Diff content should have path"
        assert diff_item["diff"], "Diff content should have diff"
        assert isinstance(diff_item["path"], str)
        assert isinstance(diff_item["diff"], str)
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        # Content должен содержать информацию о file path и diff
        assert "File:" in formatted["content"]
        assert diff_item["path"] in formatted["content"]

    @pytest.mark.asyncio
    async def test_diff_content_anthropic_full_cycle(
        self, sample_tool_result_diff: ToolExecutionResult
    ) -> None:
        """E2E-004: Diff content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение diff content из результата инструмента
        - Валидацию diff content (наличие path и diff)
        - Форматирование для Anthropic API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с diff content
        tool_call_id = "tc_diff_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_diff,
            tool_call_id=tool_call_id,
            content_type="diff",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "diff", "anthropic")
        
        # Дополнительные проверки для diff контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что diff не пуст
        diff_item = extracted.content_items[0]
        assert diff_item["type"] == "diff"
        assert diff_item["path"], "Diff content should have path"
        assert diff_item["diff"], "Diff content should have diff"
        assert isinstance(diff_item["path"], str)
        assert isinstance(diff_item["diff"], str)
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        # Content должен содержать информацию о file path и diff
        assert "File:" in tool_result_item["content"]
        assert diff_item["path"] in tool_result_item["content"]

    @pytest.mark.asyncio
    async def test_diff_content_custom_path_openai(self) -> None:
        """Дополнительный тест: Diff с custom path для OpenAI.
        
        Проверяет обработку diff с различными путями файлов.
        """
        # Создать tool result с custom diff content
        custom_path = "/src/module/file.py"
        custom_diff = "--- a/file.py\\n+++ b/file.py\\n@@ -10 +10 @@\\n-old code\\n+new code"
        
        tool_result = create_tool_result_with_content(
            "diff",
            path=custom_path,
            diff=custom_diff
        )
        
        tool_call_id = "tc_custom_diff_openai"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="diff",
            provider="openai",
        )
        
        # Проверить что path и diff сохранились
        extracted = cycle_result["extracted"]
        diff_item = extracted.content_items[0]
        assert diff_item["path"] == custom_path
        assert diff_item["diff"] == custom_diff

    @pytest.mark.asyncio
    async def test_diff_content_custom_path_anthropic(self) -> None:
        """Дополнительный тест: Diff с custom path для Anthropic.
        
        Проверяет обработку diff с различными путями файлов.
        """
        # Создать tool result с custom diff content
        custom_path = "/config/settings.json"
        custom_diff = (
            "--- a/settings.json\\n+++ b/settings.json\\n@@ -5 +5 @@\\n"
            "-  \"debug\": false\\n+  \"debug\": true"
        )
        
        tool_result = create_tool_result_with_content(
            "diff",
            path=custom_path,
            diff=custom_diff
        )
        
        tool_call_id = "tc_custom_diff_anthropic"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="diff",
            provider="anthropic",
        )
        
        # Проверить что path и diff сохранились
        extracted = cycle_result["extracted"]
        diff_item = extracted.content_items[0]
        assert diff_item["path"] == custom_path
        assert diff_item["diff"] == custom_diff
