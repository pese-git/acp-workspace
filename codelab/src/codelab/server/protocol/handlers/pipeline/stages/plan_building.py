"""Стадия построения плана выполнения задачи."""

from __future__ import annotations

from codelab.server.protocol.handlers.plan_builder import PlanBuilder

from ..base import PromptStage
from ..context import PromptContext


class PlanBuildingStage(PromptStage):
    """Построение плана выполнения задачи."""

    def __init__(self, plan_builder: PlanBuilder) -> None:
        self._plan_builder = plan_builder

    async def process(self, context: PromptContext) -> PromptContext:
        # План строится на основе промпта и сессии
        # В текущей реализации план может быть пустым
        plan_notifications = await self._plan_builder.build(
            context.session, context.raw_text
        )
        context.notifications.extend(plan_notifications)
        return context
