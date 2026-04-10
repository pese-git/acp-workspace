"""Тесты session-aware поведения ChatViewModel."""

from __future__ import annotations

import pytest

from acp_client.infrastructure.events.bus import EventBus
from acp_client.presentation.chat_view_model import ChatViewModel


@pytest.fixture
def chat_view_model() -> ChatViewModel:
    """Создает ChatViewModel для тестов."""

    return ChatViewModel(coordinator=None, event_bus=EventBus(), logger=None)


def test_chat_state_isolated_between_sessions(chat_view_model: ChatViewModel) -> None:
    """История сообщений хранится отдельно для каждой сессии."""

    chat_view_model.set_active_session("sess_1")
    chat_view_model.add_message("user", "hello from s1")

    chat_view_model.set_active_session("sess_2")
    assert chat_view_model.messages.value == []
    chat_view_model.add_message("user", "hello from s2")

    chat_view_model.set_active_session("sess_1")
    assert len(chat_view_model.messages.value) == 1
    assert chat_view_model.messages.value[0]["content"] == "hello from s1"

    chat_view_model.set_active_session("sess_2")
    assert len(chat_view_model.messages.value) == 1
    assert chat_view_model.messages.value[0]["content"] == "hello from s2"


def test_chat_resets_when_no_active_session(chat_view_model: ChatViewModel) -> None:
    """При отсутствии активной сессии отображается пустой чат."""

    chat_view_model.set_active_session("sess_1")
    chat_view_model.add_message("assistant", "saved message")

    chat_view_model.set_active_session(None)
    assert chat_view_model.messages.value == []

    chat_view_model.set_active_session("sess_1")
    assert len(chat_view_model.messages.value) == 1
    assert chat_view_model.messages.value[0]["content"] == "saved message"


def test_session_update_chunk_written_to_original_session(chat_view_model: ChatViewModel) -> None:
    """Chunk ответа сохраняется в сессию из params.sessionId, а не в активную."""

    chat_view_model.set_active_session("sess_1")
    chat_view_model.add_message("user", "question s1", session_id="sess_1")

    chat_view_model.set_active_session("sess_2")
    chat_view_model._handle_session_update(
        {
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"text": "answer s1"},
                },
            }
        }
    )

    # В активной сессии chunk не должен появиться.
    assert chat_view_model.streaming_text.value == ""

    # После возврата в исходную сессию chunk доступен.
    chat_view_model.set_active_session("sess_1")
    assert chat_view_model.streaming_text.value == "answer s1"
