"""Наивный агент с базовым циклом tool-calling."""

from typing import Any

import structlog

from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.llm.base import LLMMessage, LLMProvider
from acp_server.tools.base import ToolRegistry

# Используем structlog для структурированного логирования
logger = structlog.get_logger()


class NaiveAgent(LLMAgent):
    """Простой агент с базовым циклом tool-calling.

    Алгоритм:
    1. Отправляет промпт в LLM
    2. Если LLM возвращает tool_calls:
       - Выполняет каждый tool через ToolRegistry
       - Добавляет результаты в историю
       - Повторяет запрос к LLM (максимум max_iterations)
    3. Возвращает финальный текстовый ответ
    """

    def __init__(
        self,
        llm: LLMProvider,
        tools: ToolRegistry,
        max_iterations: int = 5,
    ) -> None:
        """Инициализация агента.

        Args:
            llm: LLM провайдер для обработки промптов
            tools: Реестр инструментов для выполнения
            max_iterations: Максимальное количество итераций цикла tool-calling
        """
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        # Словарь для хранения истории сессий
        self._session_histories: dict[str, list[LLMMessage]] = {}

    async def initialize(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        config: dict[str, Any],
    ) -> None:
        """Инициализация агента (переопределение из базового класса)."""
        self.llm = llm_provider
        self.tools = tool_registry

    async def process_prompt(self, context: AgentContext) -> AgentResponse:
        """Обработать prompt и вернуть ответ.

        Args:
            context: Контекст с промптом, историей и инструментами

        Returns:
            AgentResponse с финальным ответом и обновленной историей
        """
        # Подготовить messages для LLM
        messages = list(context.conversation_history)

        # Добавить user message с промптом
        # Промпт может содержать list[dict] - преобразуем в текст
        prompt_text = self._format_prompt(context.prompt)
        messages.append(LLMMessage(role="user", content=prompt_text))

        # Получить список инструментов для этой сессии
        available_tools = self.tools.get_available_tools(context.session_id)

        # Преобразовать определения инструментов в формат OpenAI function calling
        tools_dict = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            }
            for tool in available_tools
        ]

        # Цикл tool-calling
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1

            # Вызвать LLM
            response = await self.llm.create_completion(
                messages=messages,
                tools=tools_dict if tools_dict else None,
            )

            # Логирование полученного от LLM ответа
            logger.info(
                "llm response received from agent",
                iteration=iteration,
                response_length=len(response.text),
                has_tool_calls=bool(response.tool_calls),
                tool_calls_count=len(response.tool_calls),
            )
            logger.debug(
                "llm response text content",
                content=response.text[:200],
            )

            # Если нет tool calls - вернуть ответ
            if not response.tool_calls:
                # Обновить историю в контексте
                if context.session_id not in self._session_histories:
                    self._session_histories[context.session_id] = []

                # Добавить assistant message и user message в историю
                self._session_histories[context.session_id].extend(messages)
                self._session_histories[context.session_id].append(
                    LLMMessage(role="assistant", content=response.text)
                )

                return AgentResponse(
                    text=response.text,
                    tool_calls=[],
                    stop_reason=response.stop_reason,
                    metadata={"iterations": iteration},
                )

            # Добавить assistant message с tool calls в историю
            messages.append(LLMMessage(role="assistant", content=response.text))

            # Выполнить каждый tool
            for tool_call in response.tool_calls:
                # Выполнить инструмент
                result = await self.tools.execute_tool(
                    context.session_id,
                    tool_call.name,
                    tool_call.arguments,
                )

                # Добавить результат в историю как tool message
                tool_result_text = result.output if result.success else result.error
                if tool_result_text is None:
                    tool_result_text = "Инструмент выполнен без вывода"

                messages.append(
                    LLMMessage(
                        role="tool",
                        content=tool_result_text,
                    )
                )

        # Достигнут лимит итераций
        if context.session_id not in self._session_histories:
            self._session_histories[context.session_id] = []

        self._session_histories[context.session_id].extend(messages)

        return AgentResponse(
            text="Достигнут максимум итераций tool-calling",
            tool_calls=[],
            stop_reason="max_iterations",
            metadata={"iterations": iteration},
        )

    async def cancel_prompt(self, session_id: str) -> None:
        """Отменить текущую обработку prompt.

        Args:
            session_id: ID сессии
        """
        # Наивная реализация - просто очищаем историю для этой сессии
        # В реальном случае здесь была бы отмена текущей операции LLM
        pass

    def add_to_history(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Добавить сообщение в историю сессии.

        Args:
            session_id: ID сессии
            role: Роль сообщения (user, assistant, tool, system)
            content: Содержимое сообщения
        """
        if session_id not in self._session_histories:
            self._session_histories[session_id] = []

        self._session_histories[session_id].append(LLMMessage(role=role, content=content))

    def get_session_history(self, session_id: str) -> list[LLMMessage]:
        """Получить историю сообщений для сессии.

        Args:
            session_id: ID сессии

        Returns:
            Список сообщений LLM для этой сессии
        """
        return self._session_histories.get(session_id, [])

    async def end_session(self, session_id: str) -> None:
        """Завершить сессию и освободить ресурсы.

        Args:
            session_id: ID сессии
        """
        # Очистить историю для этой сессии
        if session_id in self._session_histories:
            del self._session_histories[session_id]

    def _format_prompt(self, prompt: list[dict[str, Any]]) -> str:
        """Преобразовать список блоков промпта в текст.

        Args:
            prompt: Список блоков вида [{"type": "text", "text": "..."}]

        Returns:
            Объединенный текст промпта
        """
        result_parts = []
        for block in prompt:
            if block.get("type") == "text":
                result_parts.append(block.get("text", ""))

        return "".join(result_parts)
