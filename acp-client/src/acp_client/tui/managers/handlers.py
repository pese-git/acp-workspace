"""Маршрутизация session/update событий для TUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from acp_client.messages import parse_session_update_notification


class UpdateMessageHandler:
    """Роутит update-события в callback функции UI."""

    def __init__(
        self,
        *,
        on_agent_chunk: Callable[[str], None],
        on_user_chunk: Callable[[str], None],
    ) -> None:
        """Сохраняет callback-и для текстовых chunk-событий."""

        self._on_agent_chunk = on_agent_chunk
        self._on_user_chunk = on_user_chunk

    def handle(self, payload: dict[str, Any]) -> None:
        """Обрабатывает одно сырое session/update сообщение."""

        parsed = parse_session_update_notification(payload)
        if parsed is None:
            return

        update_payload = parsed.params.update.model_dump()
        session_update_type = update_payload.get("sessionUpdate")
        content = update_payload.get("content")
        if not isinstance(content, dict):
            return

        # В MVP-alpha поддерживаем только текстовые chunks.
        if content.get("type") != "text":
            return
        text = content.get("text")
        if not isinstance(text, str):
            return

        if session_update_type == "agent_message_chunk":
            self._on_agent_chunk(text)
            return
        if session_update_type == "user_message_chunk":
            self._on_user_chunk(text)
