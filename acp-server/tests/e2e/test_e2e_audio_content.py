"""E2E тесты для audio content обработки."""

import base64

import pytest

from acp_server.tools.base import ToolExecutionResult
from tests.e2e.base_e2e_test import BaseE2EContentTest
from tests.e2e.helpers import (
    create_tool_result_with_content,
)


class TestAudioContentE2E(BaseE2EContentTest):
    """E2E тесты для audio content с разными провайдерами."""

    @pytest.mark.asyncio
    async def test_audio_content_openai_full_cycle(
        self, sample_tool_result_audio: ToolExecutionResult
    ) -> None:
        """E2E-007: Audio content extraction → OpenAI format (полный цикл).
        
        Проверяет:
        - Извлечение audio content из результата инструмента
        - Валидацию audio content (наличие data и format)
        - Форматирование для OpenAI API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с audio content
        tool_call_id = "tc_audio_openai_001"
        
        # 2. Run: полный цикл обработки для OpenAI
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_audio,
            tool_call_id=tool_call_id,
            content_type="audio",
            provider="openai",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "audio", "openai")
        
        # Дополнительные проверки для audio контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что audio не пуст
        audio_item = extracted.content_items[0]
        assert audio_item["type"] == "audio"
        assert audio_item["data"], "Audio content should have data"
        assert audio_item["format"], "Audio content should have format"
        assert isinstance(audio_item["data"], str)
        assert isinstance(audio_item["format"], str)
        
        # Проверить что data это валидный base64
        try:
            base64.b64decode(audio_item["data"])
        except Exception as e:
            pytest.fail(f"Audio data is not valid base64: {e}")
        
        # Проверить формат OpenAI
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == tool_call_id
        assert isinstance(formatted["content"], str)
        # Content должен содержать информацию об аудио
        assert "Audio" in formatted["content"] or "audio" in formatted["content"].lower()

    @pytest.mark.asyncio
    async def test_audio_content_anthropic_full_cycle(
        self, sample_tool_result_audio: ToolExecutionResult
    ) -> None:
        """E2E-008: Audio content extraction → Anthropic format (полный цикл).
        
        Проверяет:
        - Извлечение audio content из результата инструмента
        - Валидацию audio content (наличие data и format)
        - Форматирование для Anthropic API
        - Корректность структуры на каждом этапе
        """
        # 1. Setup: использовать fixture с audio content
        tool_call_id = "tc_audio_anthropic_001"
        
        # 2. Run: полный цикл обработки для Anthropic
        cycle_result = await self.run_full_cycle(
            tool_result=sample_tool_result_audio,
            tool_call_id=tool_call_id,
            content_type="audio",
            provider="anthropic",
        )
        
        # 3. Verify: проверить результаты
        self.verify_result(cycle_result, "audio", "anthropic")
        
        # Дополнительные проверки для audio контента
        extracted = cycle_result["extracted"]
        assert extracted.tool_call_id == tool_call_id
        
        # Проверить что audio не пуст
        audio_item = extracted.content_items[0]
        assert audio_item["type"] == "audio"
        assert audio_item["data"], "Audio content should have data"
        assert audio_item["format"], "Audio content should have format"
        assert isinstance(audio_item["data"], str)
        assert isinstance(audio_item["format"], str)
        
        # Проверить что data это валидный base64
        try:
            base64.b64decode(audio_item["data"])
        except Exception as e:
            pytest.fail(f"Audio data is not valid base64: {e}")
        
        # Проверить формат Anthropic
        formatted = cycle_result["formatted"]
        assert formatted["role"] == "user"
        assert isinstance(formatted["content"], list)
        assert len(formatted["content"]) > 0
        
        # Проверить tool_result элемент
        tool_result_item = formatted["content"][0]
        assert tool_result_item["type"] == "tool_result"
        assert tool_result_item["tool_use_id"] == tool_call_id
        # Content должен содержать информацию об аудио
        content_lower = tool_result_item["content"].lower()
        assert "Audio" in tool_result_item["content"] or "audio" in content_lower

    @pytest.mark.asyncio
    async def test_audio_content_mp3_format_openai(self) -> None:
        """Дополнительный тест: Audio MP3 format для OpenAI.
        
        Проверяет обработку аудио разных форматов.
        """
        # Создать tool result с custom audio content (MP3)
        audio_data = base64.b64encode(b"fake_mp3_audio_data").decode("utf-8")
        
        tool_result = create_tool_result_with_content(
            "audio",
            data=audio_data,
            format="mp3"
        )
        
        tool_call_id = "tc_audio_mp3_openai"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="audio",
            provider="openai",
        )
        
        # Проверить что все данные сохранились
        extracted = cycle_result["extracted"]
        audio_item = extracted.content_items[0]
        assert audio_item["data"] == audio_data
        assert audio_item["format"] == "mp3"

    @pytest.mark.asyncio
    async def test_audio_content_wav_format_anthropic(self) -> None:
        """Дополнительный тест: Audio WAV format для Anthropic.
        
        Проверяет обработку аудио разных форматов.
        """
        # Создать tool result с custom audio content (WAV)
        audio_data = base64.b64encode(b"fake_wav_audio_data").decode("utf-8")
        
        tool_result = create_tool_result_with_content(
            "audio",
            data=audio_data,
            format="wav"
        )
        
        tool_call_id = "tc_audio_wav_anthropic"
        
        # Запустить полный цикл
        cycle_result = await self.run_full_cycle(
            tool_result=tool_result,
            tool_call_id=tool_call_id,
            content_type="audio",
            provider="anthropic",
        )
        
        # Проверить что все данные сохранились
        extracted = cycle_result["extracted"]
        audio_item = extracted.content_items[0]
        assert audio_item["data"] == audio_data
        assert audio_item["format"] == "wav"
