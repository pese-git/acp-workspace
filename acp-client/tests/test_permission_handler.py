from __future__ import annotations

import pytest

from acp_client.handlers.permissions import build_permission_result


@pytest.mark.asyncio
async def test_build_permission_result_supports_sync_callback() -> None:
    result = await build_permission_result(
        payload={"method": "session/request_permission"},
        on_permission=lambda _payload: "allow_once",
    )

    assert result == {"outcome": {"outcome": "selected", "optionId": "allow_once"}}


@pytest.mark.asyncio
async def test_build_permission_result_supports_async_callback() -> None:
    async def on_permission(_payload: dict[str, object]) -> str | None:
        return "reject_once"

    result = await build_permission_result(
        payload={"method": "session/request_permission"},
        on_permission=on_permission,
    )

    assert result == {"outcome": {"outcome": "selected", "optionId": "reject_once"}}


@pytest.mark.asyncio
async def test_build_permission_result_returns_cancelled_without_selection() -> None:
    result = await build_permission_result(
        payload={"method": "session/request_permission"},
        on_permission=lambda _payload: None,
    )

    assert result == {"outcome": {"outcome": "cancelled"}}
