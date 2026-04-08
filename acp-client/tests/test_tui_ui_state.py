from __future__ import annotations

from pathlib import Path

import pytest

from acp_client.tui.managers.ui_state import TUIStateSnapshot, UIStateMachine, UIStateStore


def test_ui_state_store_save_and_load_roundtrip(tmp_path: Path) -> None:
    state_file = tmp_path / "state" / "tui_state.json"
    store = UIStateStore(file_path=state_file)

    store.save(
        TUIStateSnapshot(
            last_active_session_id="sess_1",
            draft_prompt_text="draft text",
            draft_session_id="sess_1",
        )
    )
    loaded = store.load()

    assert loaded.last_active_session_id == "sess_1"
    assert loaded.draft_prompt_text == "draft text"
    assert loaded.draft_session_id == "sess_1"


def test_ui_state_store_returns_empty_snapshot_on_invalid_json(tmp_path: Path) -> None:
    state_file = tmp_path / "state" / "tui_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("{", encoding="utf-8")

    loaded = UIStateStore(file_path=state_file).load()

    assert loaded.last_active_session_id is None
    assert loaded.draft_prompt_text == ""
    assert loaded.draft_session_id is None


def test_ui_state_machine_valid_transition_flow() -> None:
    machine = UIStateMachine()

    machine.transition("reconnecting")
    machine.transition("ready")
    machine.transition("processing_prompt")
    machine.transition("waiting_permission")
    machine.transition("processing_prompt")
    machine.transition("ready")

    assert machine.state == "ready"


def test_ui_state_machine_rejects_invalid_transition() -> None:
    machine = UIStateMachine(initial_state="ready")

    with pytest.raises(ValueError, match="Invalid UI transition"):
        machine.transition("initializing")
