"""Панель отображения плана выполнения в активной сессии."""

from __future__ import annotations

from textual.widgets import Static

from acp_client.messages import PlanUpdate


class PlanPanel(Static):
    """Показывает последний полученный план с приоритетами и статусами."""

    def __init__(self) -> None:
        """Создает панель с placeholder до первого plan update."""

        super().__init__("План: не получен", id="plan-panel")
        self._entries: list[dict[str, str]] = []

    def reset(self) -> None:
        """Сбрасывает локальное состояние панели плана."""

        self._entries = []
        self.update("План: не получен")

    def apply_update(self, update: PlanUpdate) -> None:
        """Применяет новый snapshot плана из session/update события."""

        self._entries = [
            {
                "content": entry.content,
                "priority": entry.priority,
                "status": entry.status,
            }
            for entry in update.entries
        ]
        self.update(self._render_text())

    def _render_text(self) -> str:
        """Формирует компактное представление пунктов плана."""

        if not self._entries:
            return "План: не получен"

        lines: list[str] = ["План:"]
        for entry in self._entries:
            lines.append(f"- [{entry['status']}] ({entry['priority']}) {entry['content']}")
        return "\n".join(lines)
