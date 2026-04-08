"""Панель отображения вызовов инструментов в активной сессии."""

from __future__ import annotations

from typing import Any

from textual.widgets import Static

from acp_client.messages import ToolCallUpdate

from .terminal_output import TerminalOutputPanel


class ToolPanel(Static):
    """Показывает последние статусы вызовов инструментов."""

    def __init__(self) -> None:
        """Создает панель с пустым состоянием до первых tool updates."""

        super().__init__("Инструменты: нет активных вызовов", id="tool-panel")
        self._tool_calls: dict[str, dict[str, Any]] = {}

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

        previous = self._tool_calls.get(tool_call_id, {})
        terminal_id = self._extract_terminal_id(payload)
        if terminal_id is None:
            terminal_id = previous.get("terminal_id")

        output_payload = payload.get("rawOutput")
        output_text, exit_code = self._extract_terminal_output(output_payload)
        terminal_view = previous.get("terminal_view")
        if terminal_view is None:
            terminal_view = TerminalOutputPanel()
        if output_text:
            terminal_view.append_output(output_text)
        if exit_code is not None:
            terminal_view.set_exit_code(exit_code)

        self._tool_calls[tool_call_id] = {
            "title": title,
            "status": status,
            "terminal_id": terminal_id,
            "terminal_view": terminal_view,
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
            terminal_id = payload.get("terminal_id")
            lines.append(f"- {title} [{status}] ({tool_call_id})")
            if isinstance(terminal_id, str) and terminal_id:
                lines.append(f"  terminal: {terminal_id}")

            terminal_view = payload.get("terminal_view")
            if isinstance(terminal_view, TerminalOutputPanel):
                rendered_output = terminal_view.render_text().plain.strip()
                if rendered_output and rendered_output != "Нет вывода терминала":
                    lines.append(f"  output: {self._shorten_output(rendered_output)}")
        return "\n".join(lines)

    @staticmethod
    def _extract_terminal_id(payload: dict[str, Any]) -> str | None:
        """Извлекает terminalId из payload content для tool-call события."""

        content_list = payload.get("content")
        if not isinstance(content_list, list):
            return None
        for content_item in content_list:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") != "terminal":
                continue
            terminal_id = content_item.get("terminalId")
            if isinstance(terminal_id, str) and terminal_id:
                return terminal_id
        return None

    @staticmethod
    def _extract_terminal_output(raw_output: Any) -> tuple[str | None, int | None]:
        """Извлекает output и exit code из rawOutput tool-call payload."""

        if not isinstance(raw_output, dict):
            return None, None

        output_text = raw_output.get("output")
        if not isinstance(output_text, str):
            output_text = None
        exit_code = raw_output.get("exitCode")
        if not isinstance(exit_code, int):
            exit_code = None
        return output_text, exit_code

    @staticmethod
    def _shorten_output(output: str) -> str:
        """Обрезает многострочный terminal output для компактного отображения."""

        normalized_output = " ".join(line.strip() for line in output.splitlines() if line.strip())
        if len(normalized_output) <= 140:
            return normalized_output
        return f"{normalized_output[:137]}..."
