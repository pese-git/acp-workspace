"""Маршрутизация session/update событий для TUI."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from acp_client.messages import (
    PlanUpdate,
    ToolCallUpdate,
    parse_plan_update,
    parse_session_update_notification,
    parse_tool_call_update,
)


class UpdateMessageHandler:
    """Роутит update-события в callback функции UI."""

    def __init__(
        self,
        *,
        on_agent_chunk: Callable[[str], None],
        on_user_chunk: Callable[[str], None],
        on_tool_update: Callable[[ToolCallUpdate], None] | None = None,
        on_plan_update: Callable[[PlanUpdate], None] | None = None,
    ) -> None:
        """Сохраняет callback-и для текстовых chunk-событий."""

        self._on_agent_chunk = on_agent_chunk
        self._on_user_chunk = on_user_chunk
        self._on_tool_update = on_tool_update
        self._on_plan_update = on_plan_update
        self._logger = structlog.get_logger("update_message_handler")

    def handle(self, payload: dict[str, Any]) -> None:
        """Обрабатывает одно сырое session/update сообщение."""

        # Логируем получение update события
        if isinstance(payload, dict):
            self._logger.debug("handling_update", payload_keys=list(payload.keys()))
        
        parsed = parse_session_update_notification(payload)
        if parsed is None:
            self._logger.debug("failed_to_parse_notification")
            return

        self._logger.debug("notification_parsed", session_id=parsed.params.sessionId)

        if self._on_tool_update is not None:
            parsed_tool_update = parse_tool_call_update(parsed)
            if parsed_tool_update is not None:
                # Type checking fix: toolCallId может отсутствовать в union типе
                self._logger.debug("dispatching_tool_update",
                                   tool_call_id=parsed_tool_update.toolCallId)  # type: ignore[union-attr]
                self._on_tool_update(parsed_tool_update)

        if self._on_plan_update is not None:
            parsed_plan_update = parse_plan_update(parsed)
            if parsed_plan_update is not None:
                self._logger.debug("dispatching_plan_update")
                self._on_plan_update(parsed_plan_update)

        update_payload = parsed.params.update.model_dump()
        session_update_type = update_payload.get("sessionUpdate")
        self._logger.debug("update_type", session_update_type=session_update_type)
        
        content = update_payload.get("content")
        if not isinstance(content, dict):
            self._logger.debug("content_not_dict", content_type=type(content).__name__)
            return

        # В MVP-alpha поддерживаем только текстовые chunks.
        if content.get("type") != "text":
            self._logger.debug("content_not_text", content_type=content.get("type"))
            return
        text = content.get("text")
        if not isinstance(text, str):
            self._logger.debug("text_not_string", text_type=type(text).__name__)
            return

        # Логируем отправку текста в обработчик
        self._logger.debug("dispatching_chunk", session_update_type=session_update_type,
                          text_length=len(text))
        if session_update_type == "agent_message_chunk":
            self._on_agent_chunk(text)
            return
        if session_update_type == "user_message_chunk":
            self._on_user_chunk(text)
