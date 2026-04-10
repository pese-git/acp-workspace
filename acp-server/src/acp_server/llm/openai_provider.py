"""OpenAI LLM провайдер."""
# mypy: ignore-errors

import json
from collections.abc import AsyncIterator
from typing import Any

import structlog
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from acp_server.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMToolCall

# Используем structlog для структурированного логирования
logger = structlog.get_logger()


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
        logger.debug("initializing openai provider")
        
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

        logger.info(
            "openai provider initialized",
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            has_base_url=bool(base_url),
        )

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

        logger.debug(
            "openai create_completion request starting",
            num_messages=len(messages),
            has_tools=bool(tools),
            num_tools=len(tools) if tools else 0,
        )

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
            logger.debug("sending request to openai api")
            response: ChatCompletion = await self._client.chat.completions.create(  # type: ignore[arg-type]
                **request_params
            )
            logger.debug(
                "received openai api response",
                finish_reason=response.choices[0].finish_reason if response.choices else None,
            )

            parsed_response = self._parse_completion(response)
            logger.debug(
                "openai completion parsed",
                response_length=len(parsed_response.text),
                tool_calls_count=len(parsed_response.tool_calls),
                stop_reason=parsed_response.stop_reason,
            )
            
            return parsed_response

        except Exception as e:
            logger.error(
                "openai api error",
                error=str(e),
                exc_info=True,
            )
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

        logger.debug(
            "openai stream_completion request starting",
            num_messages=len(messages),
            has_tools=bool(tools),
            num_tools=len(tools) if tools else 0,
        )

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
            logger.debug("sending streaming request to openai api")
            stream = await self._client.chat.completions.create(  # type: ignore[arg-type]
                **request_params
            )
            buffer = ""
            chunk_count = 0
            async for chunk in stream:  # type: ignore[union-attr]
                chunk_count += 1
                if chunk.choices[0].delta.content:
                    buffer += chunk.choices[0].delta.content
                    logger.debug(
                        "openai stream chunk received",
                        chunk_count=chunk_count,
                        buffer_length=len(buffer),
                    )
                    yield LLMResponse(
                        text=buffer,
                        tool_calls=[],
                        stop_reason="streaming",
                    )
            
            logger.debug(
                "openai stream completed",
                total_chunks=chunk_count,
                final_length=len(buffer),
            )

        except Exception as e:
            logger.error(
                "openai stream error",
                error=str(e),
                exc_info=True,
            )
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
