"""Оркестратор для управления LLM-агентом в контексте ACP протокола."""

from typing import Any

from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.agent.naive import NaiveAgent
from acp_server.agent.state import OrchestratorConfig
from acp_server.llm.base import LLMMessage, LLMProvider
from acp_server.protocol.state import SessionState, ToolCallState
from acp_server.tools.base import ToolRegistry


class AgentOrchestrator:
    """Оркестратор для управления LLM-агентом в контексте ACP протокола.

    Отвечает за:
    - Создание и управление экземплярами NaiveAgent
    - Преобразование между ACP SessionState и AgentContext
    - Управление историей сообщений сессии
    - Координацию выполнения tool calls
    """

    def __init__(
        self,
        config: OrchestratorConfig,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
    ) -> None:
        """Инициализация оркестратора.

        Args:
            config: Конфигурация с LLM provider и tool registry
            llm_provider: Провайдер LLM для запросов
            tool_registry: Реестр инструментов для выполнения
        """
        self.config = config
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry

        # Создать агента в зависимости от конфигурации
        if config.agent_class == "naive":
            self.agent: LLMAgent = NaiveAgent(
                llm=llm_provider,
                tools=tool_registry,
                max_iterations=5,
            )
        else:
            # По умолчанию используем NaiveAgent
            self.agent = NaiveAgent(
                llm=llm_provider,
                tools=tool_registry,
                max_iterations=5,
            )

    async def process_prompt(
        self,
        session_state: SessionState,
        prompt: str,
    ) -> SessionState:
        """Обработать промпт и обновить состояние сессии.

        Args:
            session_state: Текущее состояние сессии
            prompt: Текст промпта от пользователя

        Returns:
            Обновленное состояние сессии с результатами обработки
        """
        # Создать контекст агента из состояния сессии
        agent_context = self._create_agent_context(session_state, prompt)

        # Вызвать агента для обработки промпта
        agent_response = await self.agent.process_prompt(agent_context)

        # Обновить состояние сессии с результатами
        updated_state = self._update_session_state(
            session_state,
            agent_response,
        )

        return updated_state

    def _create_agent_context(
        self,
        session_state: SessionState,
        prompt: str,
    ) -> AgentContext:
        """Преобразовать SessionState в AgentContext.

        Args:
            session_state: Состояние сессии из протокола
            prompt: Текст промпта от пользователя

        Returns:
            Контекст для агента
        """
        # Получить историю сообщений из SessionState
        conversation_history = self._convert_to_llm_messages(
            session_state.history
        )

        # Преобразовать промпт в формат list[dict]
        prompt_blocks = [{"type": "text", "text": prompt}]

        # Получить доступные инструменты для этой сессии
        available_tools = self.tool_registry.get_available_tools(
            session_state.session_id
        )

        # Создать и вернуть AgentContext
        return AgentContext(
            session_id=session_state.session_id,
            prompt=prompt_blocks,
            conversation_history=conversation_history,
            available_tools=available_tools,
            config=session_state.config_values,
        )

    def _update_session_state(
        self,
        session_state: SessionState,
        response: AgentResponse,
    ) -> SessionState:
        """Обновить SessionState результатами от агента.

        Args:
            session_state: Исходное состояние сессии
            response: Ответ от агента

        Returns:
            Обновленное состояние сессии
        """
        # Копируем состояние для модификации
        updated_state = session_state

        # Добавить user message в историю
        updated_state.history.append({
            "type": "text",
            "role": "user",
            "text": "User prompt",
        })

        # Добавить assistant message в историю
        updated_state.history.append({
            "type": "text",
            "role": "assistant",
            "text": response.text,
        })

        # Если есть tool calls, обновить их в состоянии
        if response.tool_calls:
            for tool_call in response.tool_calls:
                # Создать ToolCallState для каждого вызова инструмента
                tool_call_id = f"call_{len(updated_state.tool_calls)}"
                tool_call_state = ToolCallState(
                    tool_call_id=tool_call_id,
                    title=tool_call.name,
                    kind="other",
                    status="pending",
                )
                updated_state.tool_calls[tool_call_id] = tool_call_state

        # Обновить счетчик tool calls
        updated_state.tool_call_counter = len(updated_state.tool_calls)

        return updated_state

    def _convert_to_llm_messages(
        self,
        history: list[dict[str, Any]],
    ) -> list[LLMMessage]:
        """Преобразовать историю из SessionState в формат LLMMessage.

        Args:
            history: История сообщений из SessionState

        Returns:
            Список LLMMessage для отправки в LLM
        """
        messages: list[LLMMessage] = []

        for entry in history:
            # Определить роль сообщения
            role = entry.get("role", "user")
            if role not in ("system", "user", "assistant", "tool"):
                role = "user"

            # Получить содержимое сообщения
            content = entry.get("text", "")
            if not content:
                content = entry.get("content", "")

            # Создать LLMMessage
            if content:
                messages.append(LLMMessage(role=role, content=str(content)))

        return messages

    def _convert_from_llm_messages(
        self,
        messages: list[LLMMessage],
    ) -> list[dict[str, Any]]:
        """Преобразовать LLMMessage обратно в формат для SessionState.

        Args:
            messages: Список LLMMessage от LLM

        Returns:
            История в формате SessionState
        """
        history: list[dict[str, Any]] = []

        for msg in messages:
            history.append({
                "type": "text",
                "role": msg.role,
                "text": msg.content,
            })

        return history
