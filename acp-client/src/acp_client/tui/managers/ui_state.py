"""Персистентное состояние TUI между запусками клиента."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

type RuntimeUIState = str

_ALLOWED_TRANSITIONS: dict[RuntimeUIState, set[RuntimeUIState]] = {
    "initializing": {"ready", "error", "reconnecting"},
    "ready": {"processing_prompt", "waiting_permission", "cancelling", "reconnecting", "error"},
    "processing_prompt": {
        "ready",
        "waiting_permission",
        "cancelling",
        "reconnecting",
        "error",
    },
    "waiting_permission": {"processing_prompt", "ready", "error", "reconnecting", "cancelling"},
    "cancelling": {"ready", "reconnecting", "error"},
    "reconnecting": {"ready", "error"},
    "error": {"reconnecting", "ready"},
}


@dataclass(slots=True)
class TUIStateSnapshot:
    """Снимок UI-состояния для восстановления после перезапуска TUI."""

    last_active_session_id: str | None = None
    draft_prompt_text: str = ""
    draft_session_id: str | None = None


class UIStateStore:
    """Читает и записывает небольшой JSON-файл с состоянием интерфейса."""

    def __init__(self, file_path: Path | None = None) -> None:
        """Настраивает путь хранения состояния, по умолчанию в домашней директории."""

        self._file_path = file_path or (Path.home() / ".acp-client" / "tui_state.json")

    def load(self) -> TUIStateSnapshot:
        """Загружает состояние из файла или возвращает пустой snapshot."""

        if not self._file_path.exists():
            return TUIStateSnapshot()

        try:
            raw_text = self._file_path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except (OSError, json.JSONDecodeError):
            return TUIStateSnapshot()

        return self._from_payload(payload)

    def save(self, snapshot: TUIStateSnapshot) -> None:
        """Сохраняет текущее состояние интерфейса в JSON-файл."""

        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(
                json.dumps(
                    {
                        "lastActiveSessionId": snapshot.last_active_session_id,
                        "draftPromptText": snapshot.draft_prompt_text,
                        "draftSessionId": snapshot.draft_session_id,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            # Не блокируем работу TUI из-за невозможности записать локальное состояние.
            return

    def _from_payload(self, payload: Any) -> TUIStateSnapshot:
        """Преобразует произвольный JSON payload в валидный snapshot."""

        if not isinstance(payload, dict):
            return TUIStateSnapshot()

        session_id = payload.get("lastActiveSessionId")
        draft_text = payload.get("draftPromptText")
        draft_session_id = payload.get("draftSessionId")

        return TUIStateSnapshot(
            last_active_session_id=session_id if isinstance(session_id, str) else None,
            draft_prompt_text=draft_text if isinstance(draft_text, str) else "",
            draft_session_id=draft_session_id if isinstance(draft_session_id, str) else None,
        )


class UIStateMachine:
    """Управляет runtime-состояниями TUI и валидирует переходы."""

    def __init__(self, initial_state: RuntimeUIState = "initializing") -> None:
        """Инициализирует state-machine с начальным состоянием интерфейса."""

        if initial_state not in _ALLOWED_TRANSITIONS:
            msg = f"Unknown UI state: {initial_state}"
            raise ValueError(msg)
        self._state = initial_state

    @property
    def state(self) -> RuntimeUIState:
        """Возвращает текущее runtime-состояние TUI."""

        return self._state

    def can_transition(self, new_state: RuntimeUIState) -> bool:
        """Проверяет допустимость перехода из текущего состояния в новое."""

        return new_state in _ALLOWED_TRANSITIONS.get(self._state, set())

    def transition(self, new_state: RuntimeUIState) -> None:
        """Переводит state-machine в новое состояние или бросает ValueError."""

        if new_state not in _ALLOWED_TRANSITIONS:
            msg = f"Unknown UI state: {new_state}"
            raise ValueError(msg)
        if not self.can_transition(new_state):
            msg = f"Invalid UI transition: {self._state} -> {new_state}"
            raise ValueError(msg)
        self._state = new_state
