"""Оркестратор для управления LLM-агентом в контексте ACP протокола."""

from typing import Any

import structlog

from acp_server.agent.base import AgentContext, AgentResponse, LLMAgent
from acp_server.agent.naive import NaiveAgent
from acp_server.agent.state import OrchestratorConfig
from acp_server.llm.base import LLMMessage, LLMProvider
from acp_server.protocol.state import ClientRuntimeCapabilities, SessionState
from acp_server.tools.base import ToolDefinition, ToolRegistry

# Используем structlog для структурированного логирования
logger = structlog.get_logger()


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
            
        Примечание:
            Встроенные инструменты (fs/*, terminal/*) регистрируются
            в PromptOrchestrator, где доступен контекст сессии.
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
    ) -> AgentResponse:
        """Обработать промпт и вернуть ответ агента.

        Согласно архитектуре двухуровневой истории, этот метод:
        - НЕ добавляет assistant message в историю сессии
        - НЕ модифицирует session_state
        - ТОЛЬКО возвращает текст ответа агента

        История сообщений обновляется в PromptOrchestrator,
        что обеспечивает централизованное управление сохранением.

        Args:
            session_state: Текущее состояние сессии
            prompt: Текст промпта от пользователя

        Returns:
            AgentResponse с текстом ответа и информацией о tool calls
        """
        # Создать контекст агента из состояния сессии
        agent_context = self._create_agent_context(session_state, prompt)

        # Вызвать агента для обработки промпта
        agent_response = await self.agent.process_prompt(agent_context)

        # Логируем результат обработки
        logger.info(
            "agent processed prompt successfully",
            session_id=session_state.session_id,
            response_length=len(agent_response.text),
        )
        logger.debug(
            "agent response content",
            content=agent_response.text[:200],
        )

        # Возвращаем ответ агента без модификации session_state
        return agent_response

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
        conversation_history = self._convert_to_llm_messages(session_state.history)

        # Преобразовать промпт в формат list[dict]
        prompt_blocks = [{"type": "text", "text": prompt}]

        # Получить доступные инструменты для этой сессии
        all_tools = self.tool_registry.get_available_tools(session_state.session_id)

        # Отфильтровать tools согласно ACP спецификации:
        # Согласно спецификации, capabilities omitted in the initialize request
        # считаются UNSUPPORTED
        available_tools = self._filter_tools_by_capabilities(
            all_tools,
            session_state.runtime_capabilities,
        )

        # Создать и вернуть AgentContext
        return AgentContext(
            session_id=session_state.session_id,
            prompt=prompt_blocks,
            conversation_history=conversation_history,
            available_tools=available_tools,
            config=session_state.config_values,
        )

    def _convert_to_llm_messages(
        self,
        history: list[dict[str, Any]] | list,
    ) -> list[LLMMessage]:
        """Преобразовать историю из SessionState в формат LLMMessage.

        Args:
            history: История сообщений из SessionState

        Returns:
            Список LLMMessage для отправки в LLM
        """
        messages: list[LLMMessage] = []

        for entry in history:
            # Конвертировать Pydantic модель в dict если необходимо
            entry_dict = (
                entry if isinstance(entry, dict) else entry.model_dump()  # type: ignore[attr-defined]
            )

            # Определить роль сообщения
            role = entry_dict.get("role", "user")
            if role not in ("system", "user", "assistant", "tool"):
                role = "user"

            # Получить содержимое сообщения
            content = entry_dict.get("text", "")
            if not content:
                content = entry_dict.get("content", "")

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
            history.append(
                {
                    "type": "text",
                    "role": msg.role,
                    "text": msg.content,
                }
            )

        return history

    def _filter_tools_by_capabilities(
        self,
        tools: list[ToolDefinition],
        runtime_capabilities: ClientRuntimeCapabilities | None,
    ) -> list[ToolDefinition]:
        """Отфильтровать tools согласно ACP спецификации.

        Согласно спецификации, capabilities omitted in the initialize request
        считаются UNSUPPORTED и не должны быть доступны для использования.

        Args:
            tools: Все доступные tools
            runtime_capabilities: Parsed capabilities от клиента

        Returns:
            Отфильтрованный список tools
        """
        if runtime_capabilities is None:
            # Если capabilities не указаны, возвращаем пустой список tools
            logger.debug(
                "runtime_capabilities is None, filtering out all tools",
            )
            return []

        # Отфильтровать tools на основе capabilities
        filtered_tools: list[ToolDefinition] = []

        for tool in tools:
            # File System tools
            if (
                (
                    tool.name == "fs/read_text_file"
                    and runtime_capabilities.fs_read
                )
                or (
                    tool.name == "fs/write_text_file"
                    and runtime_capabilities.fs_write
                )
            ):
                filtered_tools.append(tool)
            # Terminal tools
            elif tool.name.startswith("terminal/"):
                if runtime_capabilities.terminal:
                    filtered_tools.append(tool)
            # Другие tools пропускаем
            else:
                # Пока не зарегистрировано других tools
                pass

        logger.debug(
            "tools filtered by capabilities",
            total_tools=len(tools),
            filtered_tools=len(filtered_tools),
            fs_read=runtime_capabilities.fs_read,
            fs_write=runtime_capabilities.fs_write,
            terminal=runtime_capabilities.terminal,
        )

        return filtered_tools
