"""OpenAI LLM провайдер."""
# mypy: ignore-errors

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from acp_server.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Провайдер для взаимодействия с OpenAI API.

    Поддерживает:
    - Обычные completion с инструментами
    - Потоковые completion
    - Преобразование инструментов в OpenAI формат
    """

    def __init__(self) -> None:
        """Инициализация провайдера."""
        self._client: AsyncOpenAI | None = None
        self._model: str = "gpt-4o"
        self._temperature: float = 0.7
        self._max_tokens: int = 8192

    async def initialize(self, config: dict[str, Any]) -> None:
        """Инициализировать провайдер с конфигурацией.

        Args:
            config: {
                "api_key": str (опционально, по умолчанию из переменной окружения),
                "model": str (по умолчанию "gpt-4o"),
                "temperature": float (по умолчанию 0.7),
                "max_tokens": int (по умолчанию 8192),
                "base_url": str (опционально),
            }
        """
        api_key = config.get("api_key")
        self._model = config.get("model", "gpt-4o")
        self._temperature = config.get("temperature", 0.7)
        self._max_tokens = config.get("max_tokens", 8192)

        base_url = config.get("base_url")

        # Создать async клиента OpenAI
        self._client = AsyncOpenAI(
            api_key=api_key,  # Если None, использует OPENAI_API_KEY из env
            base_url=base_url,  # Если None, использует дефолтный
        )

        logger.info(f"OpenAI провайдер инициализирован: model={self._model}")

    async def create_completion(  # type: ignore[no-untyped-def]
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Получить завершение от OpenAI API.

        Args:
            messages: История сообщений
            tools: Список инструментов в OpenAI формате
            **kwargs: Дополнительные параметры (temperature, max_tokens, etc.)

        Returns:
            LLMResponse с текстом, tool calls и stop reason
        """
        if self._client is None:
            msg = "Провайдер не инициализирован"
            raise RuntimeError(msg)

        # Преобразовать сообщения в формат OpenAI
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Подготовить параметры запроса
        request_params = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
        }

        # Добавить инструменты если есть
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        try:
            response: ChatCompletion = await self._client.chat.completions.create(  # type: ignore[arg-type]
                **request_params
            )

            return self._parse_completion(response)

        except Exception as e:
            logger.error(f"Ошибка при вызове OpenAI: {e}")
            raise

    async def stream_completion(  # type: ignore[no-untyped-def,override]
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[LLMResponse]:
        """Потоковое получение ответа от OpenAI API.

        Генерирует промежуточные LLMResponse при получении данных.
        """
        if self._client is None:
            msg = "Провайдер не инициализирован"
            raise RuntimeError(msg)

        # Преобразовать сообщения
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        request_params = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
            "stream": True,
        }

        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        try:
            # Получить потоковый ответ от OpenAI
            stream = await self._client.chat.completions.create(  # type: ignore[arg-type]
                **request_params
            )
            buffer = ""
            async for chunk in stream:  # type: ignore[union-attr]
                if chunk.choices[0].delta.content:
                    buffer += chunk.choices[0].delta.content
                    yield LLMResponse(
                        text=buffer,
                        tool_calls=[],
                        stop_reason="streaming",
                    )

        except Exception as e:
            logger.error(f"Ошибка при потоковом вызове OpenAI: {e}")
            raise

    def _parse_completion(self, response: ChatCompletion) -> LLMResponse:  # type: ignore[no-untyped-def]  # noqa: C901
        """Преобразовать ответ OpenAI в LLMResponse.

        Args:
            response: Ответ от OpenAI API

        Returns:
            LLMResponse с распарсенными инструментами
        """
        choice = response.choices[0]
        message = choice.message

        # Извлечь текст
        text = message.content or ""

        # Извлечь tool calls
        tool_calls: list[LLMToolCall] = []
        if message.tool_calls:  # type: ignore[union-attr]
            for tool_call in message.tool_calls:  # type: ignore[union-attr]
                if tool_call.type == "function":  # type: ignore[union-attr]
                    # Получить функцию из tool_call
                    func = tool_call.function  # type: ignore[union-attr]
                    # Преобразовать arguments из строки в dict если нужно
                    args: dict[str, Any] = {}
                    if hasattr(func, "arguments"):  # noqa: SIM118
                        if isinstance(func.arguments, str):  # type: ignore[union-attr]
                            try:
                                args = json.loads(func.arguments)  # type: ignore[union-attr]
                            except (json.JSONDecodeError, TypeError):
                                args = {}
                        elif isinstance(func.arguments, dict):  # type: ignore[union-attr]
                            args = func.arguments  # type: ignore[union-attr]

                    tool_calls.append(
                        LLMToolCall(
                            id=tool_call.id,  # type: ignore[union-attr]
                            name=func.name,  # type: ignore[union-attr]
                            arguments=args,
                        )
                    )

        # Определить stop reason
        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
        )
