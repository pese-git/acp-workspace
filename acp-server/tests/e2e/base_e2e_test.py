"""Базовый класс для E2E тестов Content Integration."""

from typing import Any, Literal

from acp_server.protocol.content.extractor import ContentExtractor, ExtractedContent
from acp_server.protocol.content.formatter import ContentFormatter
from acp_server.protocol.content.validator import ContentValidator
from acp_server.tools.base import ToolExecutionResult
from tests.e2e.helpers import assert_content_structure, assert_llm_format


class BaseE2EContentTest:
    """Базовый класс с общими методами для всех E2E тестов контента.
    
    Предоставляет удобные методы для настройки пайплайна, запуска полного цикла
    обработки контента и проверки результатов.
    """

    def setup_pipeline(self) -> tuple[ContentExtractor, ContentValidator, ContentFormatter]:
        """Инициализировать пайплайн обработки контента.
        
        Returns:
            Кортеж (extractor, validator, formatter) компонентов
        """
        extractor = ContentExtractor()
        validator = ContentValidator()
        formatter = ContentFormatter()
        return extractor, validator, formatter

    async def run_full_cycle(
        self,
        tool_result: ToolExecutionResult,
        tool_call_id: str,
        content_type: Literal["text", "diff", "image", "audio", "embedded", "resource_link"],
        provider: Literal["openai", "anthropic"] = "openai",
    ) -> dict[str, Any]:
        """Запустить полный цикл обработки контента.
        
        Выполняет:
        1. Извлечение контента из результата выполнения инструмента
        2. Валидацию контента
        3. Форматирование для LLM провайдера
        
        Args:
            tool_result: Результат выполнения инструмента
            tool_call_id: ID tool call
            content_type: Ожидаемый тип контента
            provider: LLM провайдер
            
        Returns:
            Словарь с результатами цикла:
                - 'extracted': ExtractedContent
                - 'is_valid': bool
                - 'validation_errors': list[str]
                - 'formatted': dict (отформатированное содержимое)
        """
        extractor, validator, formatter = self.setup_pipeline()
        
        # Шаг 1: Извлечение контента
        extracted = await extractor.extract_from_result(tool_call_id, tool_result)
        
        # Шаг 2: Валидация контента
        is_valid, validation_errors = validator.validate_content_list(extracted.content_items)
        
        # Шаг 3: Форматирование для LLM
        formatted = formatter.format_for_llm(extracted, provider)
        
        return {
            "extracted": extracted,
            "is_valid": is_valid,
            "validation_errors": validation_errors,
            "formatted": formatted,
        }

    def verify_result(
        self,
        cycle_result: dict[str, Any],
        content_type: Literal["text", "diff", "image", "audio", "embedded", "resource_link"],
        provider: Literal["openai", "anthropic"],
    ) -> None:
        """Проверить результат полного цикла обработки.
        
        Args:
            cycle_result: Результат run_full_cycle()
            content_type: Ожидаемый тип контента
            provider: LLM провайдер
            
        Raises:
            AssertionError: Если проверка не пройдена
        """
        # Проверить что валидация прошла успешно
        assert cycle_result["is_valid"], (
            f"Validation failed: {cycle_result['validation_errors']}"
        )
        
        # Проверить структуру извлеченного контента
        extracted = cycle_result["extracted"]
        assert extracted.has_content, "Extracted content should have content"
        assert len(extracted.content_items) > 0, "Extracted content should not be empty"
        
        # Проверить структуру каждого content item
        for content_item in extracted.content_items:
            assert_content_structure(content_item, content_type)
        
        # Проверить формат для LLM провайдера
        formatted = cycle_result["formatted"]
        assert_llm_format(formatted, provider)

    def verify_content_extraction(
        self,
        extracted: ExtractedContent,
        content_type: Literal["text", "diff", "image", "audio", "embedded", "resource_link"],
    ) -> None:
        """Проверить результат извлечения контента.
        
        Args:
            extracted: ExtractedContent объект
            content_type: Ожидаемый тип контента
            
        Raises:
            AssertionError: Если проверка не пройдена
        """
        assert extracted is not None, "Extracted content should not be None"
        assert extracted.has_content, "Extracted content should have content flag set"
        assert len(extracted.content_items) > 0, "Extracted content items should not be empty"
        assert extracted.tool_call_id, "Extracted content should have tool_call_id"
        
        # Проверить все content items
        for content_item in extracted.content_items:
            assert_content_structure(content_item, content_type)

    def verify_content_validation(
        self,
        validator: ContentValidator,
        content_items: list[dict[str, Any]],
    ) -> None:
        """Проверить результат валидации контента.
        
        Args:
            validator: ContentValidator объект
            content_items: Список content items для валидации
            
        Raises:
            AssertionError: Если валидация не пройдена
        """
        is_valid, errors = validator.validate_content_list(content_items)
        assert is_valid, f"Content validation failed: {errors}"

    def verify_llm_formatting(
        self,
        formatted: dict[str, Any],
        provider: Literal["openai", "anthropic"],
        check_content_not_empty: bool = True,
    ) -> None:
        """Проверить результат форматирования для LLM.
        
        Args:
            formatted: Отформатированный контент
            provider: LLM провайдер
            check_content_not_empty: Проверить что контент не пуст
            
        Raises:
            AssertionError: Если форматирование некорректно
        """
        assert_llm_format(formatted, provider)
        
        if check_content_not_empty:
            if provider == "openai":
                assert formatted["content"], "OpenAI content should not be empty"
            elif provider == "anthropic":
                assert formatted["content"], "Anthropic content should not be empty"
                assert len(formatted["content"]) > 0, (
                    "Anthropic content list should not be empty"
                )
