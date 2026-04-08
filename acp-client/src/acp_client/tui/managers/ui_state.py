"""Персистентное состояние TUI между запусками клиента."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
