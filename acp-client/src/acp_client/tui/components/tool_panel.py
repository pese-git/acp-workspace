"""Панель отображения вызовов инструментов в активной сессии."""

from __future__ import annotations

from textual.widgets import Static

from acp_client.messages import ToolCallUpdate


class ToolPanel(Static):
    """Показывает последние статусы вызовов инструментов."""

    def __init__(self) -> None:
        """Создает панель с пустым состоянием до первых tool updates."""

        super().__init__("Инструменты: нет активных вызовов", id="tool-panel")
        self._tool_calls: dict[str, dict[str, str]] = {}

    def reset(self) -> None:
        """Сбрасывает локальный список вызовов инструментов."""

        self._tool_calls = {}
        self.update("Инструменты: нет активных вызовов")

    def apply_update(self, update: ToolCallUpdate) -> None:
        """Применяет одно событие tool_call/tool_call_update к панели."""

        payload = update.model_dump()
        tool_call_id = payload.get("toolCallId")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            return

        title = payload.get("title")
        if not isinstance(title, str) or not title:
            title = self._tool_calls.get(tool_call_id, {}).get("title", tool_call_id)

        status = payload.get("status")
        if not isinstance(status, str) or not status:
            status = self._tool_calls.get(tool_call_id, {}).get("status", "pending")

        self._tool_calls[tool_call_id] = {
            "title": title,
            "status": status,
        }
        self.update(self._render_text())

    def _render_text(self) -> str:
        """Формирует компактный список вызовов для отображения в панели."""

        if not self._tool_calls:
            return "Инструменты: нет активных вызовов"

        lines: list[str] = ["Инструменты:"]
        for tool_call_id, payload in list(self._tool_calls.items())[-8:]:
            title = payload["title"]
            status = payload["status"]
            lines.append(f"- {title} [{status}] ({tool_call_id})")
        return "\n".join(lines)
