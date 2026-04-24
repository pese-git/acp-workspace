"""
Резолвер директив и slash-команд в prompt запросе.

Отвечает за парсинг и обработку:
- Slash-команд (/help, /clear и т.д.)
- Structured overrides (model, systemPrompt и т.д.)
- Директив для агента
"""

from dataclasses import dataclass
from typing import Any

from codelab.server.protocol.state import PromptDirectives


@dataclass
class ResolvedDirectives:
    """Результат резолвинга директив из prompt запроса."""

    directives: PromptDirectives
    """Распарсенные директивы."""

    is_slash_command: bool = False
    """Является ли запрос slash-командой."""

    slash_command: str | None = None
    """Имя slash-команды, если есть."""

    slash_args: list[str] | None = None
    """Аргументы slash-команды, если есть."""

    model_override: str | None = None
    """Override для модели из params."""

    system_prompt_override: str | None = None
    """Override для system prompt из params."""


class DirectiveResolver:
    """Резолвер директив и slash-команд."""

    @staticmethod
    def resolve(params: dict[str, Any], content: str | list[dict[str, Any]]) -> ResolvedDirectives:
        """
        Резолвит директивы из параметров запроса и содержимого.

        Args:
            params: Параметры session/prompt запроса
            content: Содержимое prompt (строка или список)

        Returns:
            ResolvedDirectives: Распарсенные директивы
        """
        # Извлечение structured overrides из params
        model_override = params.get("model")
        system_prompt_override = params.get("systemPrompt")

        # Проверка на slash-команду
        is_slash = False
        slash_cmd = None
        slash_args = None

        if isinstance(content, str):
            content_str = content.strip()
            if content_str.startswith("/"):
                is_slash = True
                # Парсим slash-команду и её аргументы
                parts = content_str[1:].split(maxsplit=1)
                slash_cmd = parts[0] if parts else ""
                slash_args = parts[1].split() if len(parts) > 1 else []

        # Создание базовых PromptDirectives (пустые на этапе 1)
        directives = PromptDirectives()

        return ResolvedDirectives(
            directives=directives,
            is_slash_command=is_slash,
            slash_command=slash_cmd,
            slash_args=slash_args,
            model_override=model_override,
            system_prompt_override=system_prompt_override,
        )
