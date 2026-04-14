"""
Тесты для DirectiveResolver.

Проверяет резолвинг директив и slash-команд из параметров prompt запроса.
"""

from acp_server.protocol.prompt_handlers import DirectiveResolver
from acp_server.protocol.state import PromptDirectives


class TestDirectiveResolverResolve:
    """Тесты для резолвинга директив из session/prompt запроса."""

    def test_resolve_without_any_directives(self) -> None:
        """Тест резолвинга без директив."""
        params = {
            "sessionId": "sess_1",
            "content": "Hello, world!",
        }
        result = DirectiveResolver.resolve(params, "Hello, world!")

        # Проверяем базовые свойства
        assert result.directives is not None
        assert result.is_slash_command is False
        assert result.slash_command is None
        assert result.slash_args is None
        # Проверяем что overrides не установлены
        assert result.model_override is None
        assert result.system_prompt_override is None

    def test_resolve_with_model_override(self) -> None:
        """Тест резолвинга с model override."""
        params = {
            "sessionId": "sess_1",
            "content": "Hello",
            "model": "gpt-4",
        }
        result = DirectiveResolver.resolve(params, "Hello")

        assert result.model_override == "gpt-4"
        assert result.system_prompt_override is None
        assert result.is_slash_command is False

    def test_resolve_with_system_prompt_override(self) -> None:
        """Тест резолвинга с systemPrompt override."""
        params = {
            "sessionId": "sess_1",
            "content": "Hello",
            "systemPrompt": "You are a helpful assistant",
        }
        result = DirectiveResolver.resolve(params, "Hello")

        assert result.system_prompt_override == "You are a helpful assistant"
        assert result.model_override is None
        assert result.is_slash_command is False

    def test_resolve_with_both_overrides(self) -> None:
        """Тест резолвинга с обоими overrides."""
        params = {
            "sessionId": "sess_1",
            "content": "Hello",
            "model": "gpt-4",
            "systemPrompt": "Custom prompt",
        }
        result = DirectiveResolver.resolve(params, "Hello")

        assert result.model_override == "gpt-4"
        assert result.system_prompt_override == "Custom prompt"
        assert result.is_slash_command is False

    def test_resolve_slash_command_without_args(self) -> None:
        """Тест обнаружения slash-команды без аргументов."""
        params = {"sessionId": "sess_1", "content": "/help"}
        result = DirectiveResolver.resolve(params, "/help")

        assert result.is_slash_command is True
        assert result.slash_command == "help"
        assert result.slash_args == []

    def test_resolve_slash_command_with_single_arg(self) -> None:
        """Тест обнаружения slash-команды с одним аргументом."""
        params = {"sessionId": "sess_1", "content": "/run test.py"}
        result = DirectiveResolver.resolve(params, "/run test.py")

        assert result.is_slash_command is True
        assert result.slash_command == "run"
        assert result.slash_args == ["test.py"]

    def test_resolve_slash_command_with_multiple_args(self) -> None:
        """Тест обнаружения slash-команды с несколькими аргументами."""
        params = {"sessionId": "sess_1", "content": "/run python script.py arg1 arg2"}
        result = DirectiveResolver.resolve(params, "/run python script.py arg1 arg2")

        assert result.is_slash_command is True
        assert result.slash_command == "run"
        # После команды 'run' всё остальное - это аргумент
        assert result.slash_args == ["python", "script.py", "arg1", "arg2"]

    def test_resolve_slash_command_with_whitespace(self) -> None:
        """Тест обработки пробелов в slash-команде."""
        params = {"sessionId": "sess_1", "content": "  /help  "}
        result = DirectiveResolver.resolve(params, "  /help  ")

        assert result.is_slash_command is True
        assert result.slash_command == "help"
        assert result.slash_args == []

    def test_resolve_slash_command_with_model_override(self) -> None:
        """Тест slash-команды с model override."""
        params = {
            "sessionId": "sess_1",
            "content": "/clear",
            "model": "gpt-3.5-turbo",
        }
        result = DirectiveResolver.resolve(params, "/clear")

        assert result.is_slash_command is True
        assert result.slash_command == "clear"
        assert result.model_override == "gpt-3.5-turbo"

    def test_resolve_slash_command_only_slash(self) -> None:
        """Тест обработки одного символа '/'."""
        params = {"sessionId": "sess_1", "content": "/"}
        result = DirectiveResolver.resolve(params, "/")

        assert result.is_slash_command is True
        assert result.slash_command == ""
        assert result.slash_args == []

    def test_resolve_regular_text_starting_with_slash(self) -> None:
        """Тест что обычный текст распознаётся как slash-команда если начинается с '/'."""
        # Это ожидаемое поведение - распознавание на основе первого символа
        params = {"sessionId": "sess_1", "content": "/this is not a command"}
        result = DirectiveResolver.resolve(params, "/this is not a command")

        assert result.is_slash_command is True
        assert result.slash_command == "this"
        assert result.slash_args == ["is", "not", "a", "command"]

    def test_resolve_with_list_content(self) -> None:
        """Тест резолвинга со списком content (не использует slash-команды)."""
        content_list = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "World"},
        ]
        params = {
            "sessionId": "sess_1",
            "content": content_list,
            "model": "gpt-4",
        }
        result = DirectiveResolver.resolve(params, content_list)

        assert result.is_slash_command is False
        assert result.slash_command is None
        assert result.slash_args is None
        assert result.model_override == "gpt-4"

    def test_resolve_preserves_directives_structure(self) -> None:
        """Тест что структура PromptDirectives сохраняется."""
        params = {
            "sessionId": "sess_1",
            "content": "test",
            "model": "gpt-4",
        }
        result = DirectiveResolver.resolve(params, "test")

        # Проверяем что все поля есть в directives
        assert isinstance(result.directives, PromptDirectives)
        assert hasattr(result.directives, "request_tool")
        assert hasattr(result.directives, "keep_tool_pending")
        assert hasattr(result.directives, "publish_plan")

    def test_resolve_slash_command_with_quoted_args(self) -> None:
        """Тест что аргументы разделяются по пробелам (без обработки кавычек)."""
        params = {"sessionId": "sess_1", "content": '/cmd "hello world"'}
        result = DirectiveResolver.resolve(params, '/cmd "hello world"')

        # Аргументы разбиваются по пробелам, кавычки не обрабатываются
        assert result.is_slash_command is True
        assert result.slash_command == "cmd"
        assert result.slash_args == ['"hello', 'world"']

    def test_resolve_empty_params_with_content(self) -> None:
        """Тест резолвинга с минимальными params."""
        params = {"sessionId": "sess_1"}
        result = DirectiveResolver.resolve(params, "Hello")

        assert result.model_override is None
        assert result.system_prompt_override is None
        assert result.is_slash_command is False
