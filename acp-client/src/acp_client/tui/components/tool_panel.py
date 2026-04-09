"""Панель отображения вызовов инструментов с MVVM интеграцией.

Отвечает за:
- Отображение статуса выполнения tool calls
- Показ результатов выполнения инструментов
- Интеграция с ChatViewModel для синхронизации tool calls
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from acp_client.messages import ToolCallUpdate

from .terminal_output import TerminalOutputPanel

if TYPE_CHECKING:
    from acp_client.presentation.chat_view_model import ChatViewModel
    from acp_client.presentation.terminal_view_model import TerminalViewModel


class ToolPanel(Static):
    """Панель tool calls с MVVM интеграцией.
    
    Обязательно требует ChatViewModel для работы. Подписывается на Observable свойства:
    - tool_calls: список активных tool calls
    
    Примеры использования:
        >>> from acp_client.presentation.chat_view_model import ChatViewModel
        >>> chat_vm = ChatViewModel(coordinator, event_bus)
        >>> tool_panel = ToolPanel(chat_vm)
        >>> 
        >>> # Когда ChatViewModel обновляется, панель обновляется автоматически
        >>> chat_vm.tool_calls.value = [tool_call1, tool_call2]
    """

    def __init__(
        self,
        chat_vm: ChatViewModel,
        terminal_vm: TerminalViewModel,
    ) -> None:
        """Инициализирует ToolPanel с обязательными ViewModels.
        
        Args:
            chat_vm: ChatViewModel для управления tool calls
            terminal_vm: TerminalViewModel для управления output панелями
        """
        super().__init__("Инструменты: нет активных вызовов", id="tool-panel")
        self.chat_vm = chat_vm
        self._terminal_vm = terminal_vm
        self._tool_calls: dict[str, dict[str, Any]] = {}
        
        # Подписываемся на изменения в ChatViewModel
        self.chat_vm.tool_calls.subscribe(self._on_tool_calls_changed)

    def _on_tool_calls_changed(self, tool_calls: list) -> None:
        """Обновить панель при изменении tool calls.
        
        Args:
            tool_calls: Новый список tool calls
        """
        # Обновляем отображение на основе новых tool calls
        if not tool_calls:
            self.update("Инструменты: нет активных вызовов")
        else:
            # Формируем текст отображения из tool calls
            lines: list[str] = ["Инструменты:"]
            for tool_call in tool_calls[-8:]:  # Показываем последние 8
                # tool_call может быть разными типами, обрабатываем безопасно
                tool_id = getattr(tool_call, "id", str(tool_call)[:20])
                status = getattr(tool_call, "status", "pending")
                lines.append(f"- {tool_id} [{status}]")
            self.update("\n".join(lines))

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
            # Создаём новую панель вывода терминала с ViewModel
            terminal_view = TerminalOutputPanel(self._terminal_vm)
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

    def latest_terminal_snapshot(self) -> tuple[str, str, Text] | None:
        """Возвращает полный вывод последнего tool call с terminal-контентом."""

        for payload in reversed(list(self._tool_calls.values())):
            terminal_id = payload.get("terminal_id")
            terminal_view = payload.get("terminal_view")
            title = payload.get("title")
            if not isinstance(terminal_id, str) or not terminal_id:
                continue
            if not isinstance(terminal_view, TerminalOutputPanel):
                continue
            if not isinstance(title, str) or not title:
                title = "Tool call"
            return title, terminal_id, terminal_view.render_text()
        return None

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
