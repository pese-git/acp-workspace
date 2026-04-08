"""Основная область отображения сообщений чата."""

from __future__ import annotations

from textual.containers import VerticalScroll
from textual.widgets import Static


class ChatView(VerticalScroll):
    """Показывает историю сообщений с поддержкой простого streaming."""

    def __init__(self) -> None:
        """Инициализирует контейнер чата и временное состояние streaming."""

        super().__init__(id="chat-view")
        self._active_agent_block: Static | None = None
        self._active_agent_text: str = ""

    def add_system_message(self, text: str) -> None:
        """Добавляет техническое сообщение от системы."""

        self.mount(Static(f"[system] {text}", classes="message system"))
        self.scroll_end(animate=False)

    def add_user_message(self, text: str) -> None:
        """Добавляет сообщение пользователя в историю."""

        self.mount(Static(f"[you] {text}", classes="message user"))
        self.scroll_end(animate=False)

    def append_agent_chunk(self, text_chunk: str) -> None:
        """Добавляет новый текстовый chunk к активному сообщению агента."""

        if self._active_agent_block is None:
            self._active_agent_text = ""
            self._active_agent_block = Static("[agent] ", classes="message agent")
            self.mount(self._active_agent_block)

        self._active_agent_text += text_chunk
        self._active_agent_block.update(f"[agent] {self._active_agent_text}")
        self.scroll_end(animate=False)

    def finish_agent_message(self) -> None:
        """Завершает текущее stream-сообщение от агента."""

        self._active_agent_block = None
        self._active_agent_text = ""
