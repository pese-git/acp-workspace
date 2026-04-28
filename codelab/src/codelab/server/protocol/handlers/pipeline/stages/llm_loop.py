"""Стадия основного цикла LLM и выполнения tool calls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..base import PromptStage
from ..context import PromptContext

if TYPE_CHECKING:
    from codelab.server.agent.orchestrator import AgentOrchestrator
    from codelab.server.protocol.handlers.permission_manager import PermissionManager
    from codelab.server.protocol.handlers.tool_call_handler import ToolCallHandler


class LLMLoopStage(PromptStage):
    """Основной цикл взаимодействия с LLM и выполнения tool calls."""

    def __init__(
        self,
        agent_orchestrator: AgentOrchestrator,
        tool_call_handler: ToolCallHandler,
        permission_manager: PermissionManager,
    ) -> None:
        self._agent = agent_orchestrator
        self._tool_handler = tool_call_handler
        self._permission = permission_manager

    async def process(self, context: PromptContext) -> PromptContext:
        # Вызов LLM агента для обработки промпта
        result = await self._agent.process_prompt(
            session=context.session,
            text=context.raw_text,
        )
        context.notifications.extend(result.notifications)
        context.stop_reason = result.stop_reason
        return context
