from __future__ import annotations

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

    def __init__(self, sessions: list[FakeWSSession]) -> None:
        super().__init__(host="127.0.0.1", port=8765)
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
    manager = RetryAwareConnectionManager([first, second])

    result = await manager._request("ping")  # noqa: SLF001

    assert result == {"ok": True}
    assert first.request_calls == 1
    assert first.exit_calls == 1
    assert second.request_calls == 1


@pytest.mark.asyncio
async def test_connection_manager_raises_after_second_transport_error() -> None:
    first = FakeWSSession(fail_request=True)
    second = FakeWSSession(fail_request=True)
    manager = RetryAwareConnectionManager([first, second])

    with pytest.raises(RuntimeError, match="network error"):
        await manager._request("ping")  # noqa: SLF001

    assert first.request_calls == 1
    assert second.request_calls == 1
    assert first.exit_calls == 1
    assert second.exit_calls == 1
