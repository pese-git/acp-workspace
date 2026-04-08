from __future__ import annotations

from typing import Any

import pytest

from acp_client.messages import SessionListItem, SessionSetupResult, SessionUpdateNotification
from acp_client.tui.managers.session import SessionManager


class FakeConnection:
    """Тестовый connection manager с предсказуемым поведением."""

    def __init__(self) -> None:
        self.created_count = 0
        self.prompt_calls: list[tuple[str, str]] = []
        self.loaded_sessions: list[str] = []

    async def list_sessions(self) -> list[SessionListItem]:
        if self.created_count >= 2:
            return [
                SessionListItem(sessionId="sess_new_2", cwd="/tmp"),
                SessionListItem(sessionId="sess_new", cwd="/tmp"),
            ]
        if self.created_count == 1:
            return [SessionListItem(sessionId="sess_new", cwd="/tmp")]
        return []

    async def create_session(self, cwd: str) -> SessionSetupResult:
        self.created_count += 1
        if self.created_count == 1:
            return SessionSetupResult(sessionId="sess_new", configOptions=[])
        return SessionSetupResult(sessionId="sess_new_2", configOptions=[])

    async def load_session(
        self,
        session_id: str,
        cwd: str,
    ) -> tuple[SessionSetupResult, list[SessionUpdateNotification]]:
        self.loaded_sessions.append(session_id)
        update = SessionUpdateNotification.model_validate(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "replay-text"},
                    },
                },
            }
        )
        return SessionSetupResult(sessionId=session_id, configOptions=[]), [update]

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Any,
        on_permission: Any,
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


class FakeConnectionWithExistingSession:
    """Тестовый connection manager c уже существующей серверной сессией."""

    def __init__(self) -> None:
        self.loaded_sessions: list[str] = []

    async def list_sessions(self) -> list[SessionListItem]:
        return [SessionListItem(sessionId="sess_existing", cwd="/tmp")]

    async def create_session(self, cwd: str) -> SessionSetupResult:
        return SessionSetupResult(sessionId="sess_new", configOptions=[])

    async def load_session(
        self,
        session_id: str,
        cwd: str,
    ) -> tuple[SessionSetupResult, list[SessionUpdateNotification]]:
        self.loaded_sessions.append(session_id)
        update = SessionUpdateNotification.model_validate(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": session_id,
                    "update": {
                        "sessionUpdate": "user_message_chunk",
                        "content": {"type": "text", "text": "restored"},
                    },
                },
            }
        )
        return SessionSetupResult(sessionId=session_id, configOptions=[]), [update]

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Any,
        on_permission: Any,
    ) -> None:
        return None

    async def cancel_prompt(self, session_id: str) -> None:
        return None


@pytest.mark.asyncio
async def test_session_manager_creates_session_before_prompt() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)
    collected: list[dict[str, Any]] = []

    await session_manager.send_prompt("hello", collected.append, None)

    assert session_manager.active_session_id == "sess_new"
    assert fake_connection.prompt_calls == [("sess_new", "hello")]
    assert collected[0]["method"] == "session/update"


@pytest.mark.asyncio
async def test_session_manager_cancel_is_noop_without_active_session() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)

    await session_manager.cancel()

    assert fake_connection.prompt_calls == []


@pytest.mark.asyncio
async def test_session_manager_create_and_activate_replaces_active_session() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)

    await session_manager.refresh_sessions()
    first_session = await session_manager.ensure_active_session()
    second_session = await session_manager.create_and_activate_session("/tmp")

    assert first_session == "sess_new"
    assert second_session == "sess_new_2"
    assert session_manager.active_session_id == "sess_new_2"


@pytest.mark.asyncio
async def test_session_manager_can_cycle_sessions() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)
    await session_manager.create_and_activate_session("/tmp")
    await session_manager.create_and_activate_session("/tmp")

    next_session = await session_manager.activate_next_session()
    previous_session = await session_manager.activate_previous_session()

    assert next_session == "sess_new"
    assert previous_session == "sess_new_2"
    assert fake_connection.loaded_sessions == ["sess_new", "sess_new_2"]


@pytest.mark.asyncio
async def test_session_manager_stores_last_replay_updates_on_activate() -> None:
    fake_connection = FakeConnection()
    session_manager = SessionManager(fake_connection)
    await session_manager.create_and_activate_session("/tmp")
    await session_manager.create_and_activate_session("/tmp")

    await session_manager.activate_session("sess_new")

    assert len(session_manager.last_replay_updates) == 1
    assert (
        session_manager.last_replay_updates[0].params.update.sessionUpdate == "agent_message_chunk"
    )


@pytest.mark.asyncio
async def test_session_manager_ensure_active_loads_existing_session_replay() -> None:
    fake_connection = FakeConnectionWithExistingSession()
    session_manager = SessionManager(fake_connection)

    await session_manager.refresh_sessions()
    session_id = await session_manager.ensure_active_session()

    assert session_id == "sess_existing"
    assert fake_connection.loaded_sessions == ["sess_existing"]
    assert len(session_manager.last_replay_updates) == 1
    assert (
        session_manager.last_replay_updates[0].params.update.sessionUpdate == "user_message_chunk"
    )
