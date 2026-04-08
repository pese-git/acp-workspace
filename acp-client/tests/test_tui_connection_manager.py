from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from acp_client.transport import ACPClientWSSession
from acp_client.tui.managers.connection import ACPConnectionManager


class FakeWSSession:
    """Тестовая WS-сессия с контролируемым сценарием ответа."""

    def __init__(self, *, fail_request: bool, result: Any = None) -> None:
        self._fail_request = fail_request
        self._result = result
        self.request_calls = 0
        self.exit_calls = 0

    async def request(self, **kwargs: Any) -> Any:
        self.request_calls += 1
        if self._fail_request:
            msg = "network error"
            raise RuntimeError(msg)
        return self._result

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.exit_calls += 1


class RetryAwareConnectionManager(ACPConnectionManager):
    """Connection manager с подменой WS-сессий для тестов retry-поведения."""

    def __init__(
        self,
        sessions: list[FakeWSSession],
        *,
        on_reconnect_attempt: Callable[[str], None] | None = None,
        on_reconnect_recovered: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            host="127.0.0.1",
            port=8765,
            on_reconnect_attempt=on_reconnect_attempt,
            on_reconnect_recovered=on_reconnect_recovered,
        )
        self._fake_sessions = sessions

    async def _ensure_ws_session(self) -> ACPClientWSSession:
        active = self._fake_sessions[0]
        if len(self._fake_sessions) > 1:
            self._fake_sessions.pop(0)
        self._ws_session = cast(ACPClientWSSession, active)
        return cast(ACPClientWSSession, active)


@pytest.mark.asyncio
async def test_connection_manager_retries_once_after_transport_error() -> None:
    first = FakeWSSession(fail_request=True)
    second = FakeWSSession(fail_request=False, result={"ok": True})
    reconnect_attempts: list[str] = []
    reconnect_recovered: list[str] = []
    manager = RetryAwareConnectionManager(
        [first, second],
        on_reconnect_attempt=reconnect_attempts.append,
        on_reconnect_recovered=reconnect_recovered.append,
    )

    result = await manager._request("ping")  # noqa: SLF001

    assert result == {"ok": True}
    assert first.request_calls == 1
    assert first.exit_calls == 1
    assert second.request_calls == 1
    assert reconnect_attempts == ["ping"]
    assert reconnect_recovered == ["ping"]


@pytest.mark.asyncio
async def test_connection_manager_raises_after_second_transport_error() -> None:
    first = FakeWSSession(fail_request=True)
    second = FakeWSSession(fail_request=True)
    reconnect_attempts: list[str] = []
    reconnect_recovered: list[str] = []
    manager = RetryAwareConnectionManager(
        [first, second],
        on_reconnect_attempt=reconnect_attempts.append,
        on_reconnect_recovered=reconnect_recovered.append,
    )

    with pytest.raises(RuntimeError, match="network error"):
        await manager._request("ping")  # noqa: SLF001

    assert first.request_calls == 1
    assert second.request_calls == 1
    assert first.exit_calls == 1
    assert second.exit_calls == 1
    assert reconnect_attempts == ["ping"]
    assert reconnect_recovered == []


def test_connection_manager_is_ready_returns_false_by_default() -> None:
    manager = ACPConnectionManager(host="127.0.0.1", port=8765)

    assert manager.is_ready() is False


def test_connection_manager_is_ready_requires_session_and_initialize() -> None:
    manager = ACPConnectionManager(host="127.0.0.1", port=8765)
    manager._ws_session = cast(ACPClientWSSession, object())  # noqa: SLF001

    assert manager.is_ready() is False

    manager._initialized = True  # noqa: SLF001
    assert manager.is_ready() is True
