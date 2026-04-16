"""Вспомогательные функции и утилиты для E2E тестов."""

from typing import Any, Literal

from acp_server.tools.base import ToolExecutionResult


def create_tool_result_with_content(
    content_type: Literal["text", "diff", "image", "audio", "embedded", "resource_link"],
    **kwargs: Any
) -> ToolExecutionResult:
    """Создать ToolExecutionResult с content определенного типа.
    
    Args:
        content_type: Тип контента
        **kwargs: Дополнительные параметры для content
        
    Returns:
        ToolExecutionResult с заданным контентом
        
    Examples:
        >>> result = create_tool_result_with_content("text", text="Hello")
        >>> result.content[0]["type"]
        'text'
    """
    content_item: dict[str, Any] = {"type": content_type}
    content_item.update(kwargs)
    
    return ToolExecutionResult(
        success=True,
        output=f"{content_type} output",
        content=[content_item]
    )


def assert_content_structure(
    content: dict[str, Any],
    expected_type: Literal["text", "diff", "image", "audio", "embedded", "resource_link"]
) -> None:
    """Проверить структуру content item.
    
    Args:
        content: Content item для проверки
        expected_type: Ожидаемый тип контента
        
    Raises:
        AssertionError: Если структура некорректна
    """
    assert isinstance(content, dict), "Content должен быть словарем"
    assert "type" in content, "Content должен иметь поле 'type'"
    assert content["type"] == expected_type, (
        f"Expected content type '{expected_type}', got '{content['type']}'"
    )
    
    # Проверить обязательные поля для каждого типа
    required_fields = {
        "text": {"text"},
        "diff": {"path", "diff"},
        "image": {"data", "format"},
        "audio": {"data", "format"},
        "embedded": {"content"},
        "resource_link": {"uri"}
    }
    
    if expected_type in required_fields:
        missing = required_fields[expected_type] - set(content.keys())
        assert not missing, f"Missing required fields for {expected_type}: {missing}"


def assert_llm_format(
    formatted: dict[str, Any],
    provider: Literal["openai", "anthropic"],
    expected_fields: set[str] | None = None
) -> None:
    """Проверить формат LLM для конкретного провайдера.
    
    Args:
        formatted: Отформатированный контент для LLM
        provider: Тип провайдера
        expected_fields: Ожидаемые поля (опционально)
        
    Raises:
        AssertionError: Если формат некорректен
    """
    assert isinstance(formatted, dict), "Formatted content должен быть словарем"
    
    if provider == "openai":
        assert "role" in formatted, "OpenAI format должен иметь 'role'"
        assert formatted["role"] == "tool", "OpenAI role должен быть 'tool'"
        assert "tool_call_id" in formatted, "OpenAI format должен иметь 'tool_call_id'"
        assert "content" in formatted, "OpenAI format должен иметь 'content'"
        assert isinstance(formatted["content"], str), "OpenAI content должен быть строкой"
        
    elif provider == "anthropic":
        assert "role" in formatted, "Anthropic format должен иметь 'role'"
        assert formatted["role"] == "user", "Anthropic role должен быть 'user'"
        assert "content" in formatted, "Anthropic format должен иметь 'content'"
        assert isinstance(formatted["content"], list), "Anthropic content должен быть списком"
        
        # Проверить структуру tool_result элемента
        if formatted["content"]:
            tool_result = formatted["content"][0]
            assert tool_result.get("type") == "tool_result", (
                "Anthropic content должен содержать tool_result"
            )
            assert "tool_use_id" in tool_result, "tool_result должен иметь 'tool_use_id'"
            assert "content" in tool_result, "tool_result должен иметь 'content'"
    
    # Проверить дополнительные поля если указаны
    if expected_fields:
        for field in expected_fields:
            assert field in formatted, f"Expected field '{field}' not found in formatted content"


def assert_content_not_empty(content: dict[str, Any]) -> None:
    """Проверить, что контент не пуст.
    
    Args:
        content: Content item для проверки
        
    Raises:
        AssertionError: Если контент пуст
    """
    assert content, "Content не должен быть пустым"
    assert content.get("type"), "Content должен иметь тип"
    
    content_type = content.get("type")
    
    # Проверить конкретное содержимое для каждого типа
    if content_type == "text":
        assert content.get("text"), "Text content должен иметь непустой текст"
    elif content_type == "diff":
        assert content.get("path"), "Diff content должен иметь путь файла"
        assert content.get("diff"), "Diff content должен иметь diff"
    elif content_type == "image":
        assert content.get("data"), "Image content должен иметь data"
        assert content.get("format"), "Image content должен иметь format"
    elif content_type == "audio":
        assert content.get("data"), "Audio content должен иметь data"
        assert content.get("format"), "Audio content должен иметь format"
    elif content_type == "embedded":
        assert content.get("content"), "Embedded content должен иметь content"
    elif content_type == "resource_link":
        assert content.get("uri"), "Resource link должен иметь uri"


def create_empty_tool_result() -> ToolExecutionResult:
    """Создать пустой ToolExecutionResult без контента.
    
    Returns:
        ToolExecutionResult без контента
    """
    return ToolExecutionResult(
        success=True,
        output="Empty result",
        content=[]
    )


def create_failed_tool_result(error_message: str = "Tool execution failed") -> ToolExecutionResult:
    """Создать ToolExecutionResult с ошибкой.
    
    Args:
        error_message: Сообщение об ошибке
        
    Returns:
        ToolExecutionResult с ошибкой
    """
    return ToolExecutionResult(
        success=False,
        output=None,
        error=error_message,
        content=[]
    )
