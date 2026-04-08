from __future__ import annotations

from pathlib import Path

from acp_client.messages import SessionUpdateNotification
from acp_client.tui.managers.cache import HistoryCache


def _build_update(text: str) -> SessionUpdateNotification:
    """Создает минимальный валидный `session/update` notification для тестов кэша."""

    return SessionUpdateNotification.model_validate(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "sess_1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": text},
                },
            },
        }
    )


def test_history_cache_save_and_load_roundtrip(tmp_path: Path) -> None:
    cache = HistoryCache(root_dir=tmp_path / "history")
    first_update = _build_update("one")
    second_update = _build_update("two")

    cache.save_update(session_id="sess_1", update=first_update)
    cache.save_update(session_id="sess_1", update=second_update)
    loaded_updates = cache.load_updates(session_id="sess_1")

    assert len(loaded_updates) == 2
    assert loaded_updates[0].params.update.model_dump()["content"]["text"] == "one"
    assert loaded_updates[1].params.update.model_dump()["content"]["text"] == "two"


def test_history_cache_save_updates_overwrites_snapshot(tmp_path: Path) -> None:
    cache = HistoryCache(root_dir=tmp_path / "history")
    cache.save_update(session_id="sess_1", update=_build_update("old"))

    cache.save_updates(session_id="sess_1", updates=[_build_update("new")])
    loaded_updates = cache.load_updates(session_id="sess_1")

    assert len(loaded_updates) == 1
    assert loaded_updates[0].params.update.model_dump()["content"]["text"] == "new"
