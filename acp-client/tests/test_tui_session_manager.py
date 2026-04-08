from __future__ import annotations

from typing import Any

import pytest

from acp_client.messages import SessionListItem, SessionSetupResult
from acp_client.tui.managers.session import SessionManager


class FakeConnection:
    """Тестовый connection manager с предсказуемым поведением."""

    def __init__(self) -> None:
        self.created = False
        self.prompt_calls: list[tuple[str, str]] = []

    async def list_sessions(self) -> list[SessionListItem]:
        if self.created:
            return [SessionListItem(sessionId="sess_new", cwd="/tmp")]
        return []

    async def create_session(self, cwd: str) -> SessionSetupResult:
        self.created = True
        return SessionSetupResult(sessionId="sess_new", configOptions=[])

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Any,
    ) -> None:
        self.prompt_calls.append((session_id, text))
        on_update(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "ok"},
                    },
                },
            }
        )

    async def cancel_prompt(self, session_id: str) -> None:
        self.prompt_calls.append((session_id, "<cancel>"))


@pytest.mark.asyncio
async def test_session_manager_creates_session_before_prompt() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)
    collected: list[dict[str, Any]] = []

    await session_manager.send_prompt("hello", collected.append)

    assert session_manager.active_session_id == "sess_new"
    assert fake_connection.prompt_calls == [("sess_new", "hello")]
    assert collected[0]["method"] == "session/update"


@pytest.mark.asyncio
async def test_session_manager_cancel_is_noop_without_active_session() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)

    await session_manager.cancel()

    assert fake_connection.prompt_calls == []
