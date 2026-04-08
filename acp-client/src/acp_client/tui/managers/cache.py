"""Локальный кэш истории session/update для TUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from acp_client.messages import SessionUpdateNotification


class HistoryCache:
    """Хранит и возвращает сериализованные `session/update` события по session id."""

    def __init__(self, root_dir: Path | None = None) -> None:
        """Настраивает директорию кэша истории в домашнем профиле пользователя."""

        self._root_dir = root_dir or (Path.home() / ".acp-client" / "history")

    def save_update(self, *, session_id: str, update: SessionUpdateNotification) -> None:
        """Добавляет одно update-событие в JSON-кэш конкретной сессии."""

        if not session_id:
            return

        payload = self._read_session_payload(session_id)
        updates = payload.get("updates")
        if not isinstance(updates, list):
            updates = []
        updates.append(update.model_dump())
        payload["updates"] = updates
        self._write_session_payload(session_id, payload)

    def save_updates(self, *, session_id: str, updates: list[SessionUpdateNotification]) -> None:
        """Сохраняет список update-событий, полностью перезаписывая snapshot сессии."""

        if not session_id:
            return

        serialized_updates = [update.model_dump() for update in updates]
        self._write_session_payload(session_id, {"updates": serialized_updates})

    def load_updates(self, *, session_id: str) -> list[SessionUpdateNotification]:
        """Загружает update-события сессии из кэша и валидирует их модели."""

        if not session_id:
            return []

        payload = self._read_session_payload(session_id)
        raw_updates = payload.get("updates")
        if not isinstance(raw_updates, list):
            return []

        parsed_updates: list[SessionUpdateNotification] = []
        for raw_update in raw_updates:
            if not isinstance(raw_update, dict):
                continue
            try:
                parsed_updates.append(SessionUpdateNotification.model_validate(raw_update))
            except Exception:
                continue
        return parsed_updates

    def _session_file(self, session_id: str) -> Path:
        """Возвращает путь до JSON-файла кэша выбранной сессии."""

        sanitized_session_id = session_id.replace("/", "_")
        return self._root_dir / f"{sanitized_session_id}.json"

    def _read_session_payload(self, session_id: str) -> dict[str, Any]:
        """Читает payload файла сессии или возвращает пустую структуру."""

        session_file = self._session_file(session_id)
        if not session_file.exists():
            return {"updates": []}
        try:
            raw_payload = json.loads(session_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"updates": []}
        if not isinstance(raw_payload, dict):
            return {"updates": []}
        return raw_payload

    def _write_session_payload(self, session_id: str, payload: dict[str, Any]) -> None:
        """Записывает payload сессии на диск, не прерывая UI при ошибках IO."""

        session_file = self._session_file(session_id)
        try:
            session_file.parent.mkdir(parents=True, exist_ok=True)
            session_file.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            # Кэш best-effort и не должен ломать основной UX работы TUI.
            return
