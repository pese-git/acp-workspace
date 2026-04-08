"""Менеджер политики разрешений для session/request_permission в TUI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from acp_client.messages import RequestPermissionRequest

PERSISTENT_PERMISSION_KINDS = {"allow_always", "reject_always"}


@dataclass(slots=True)
class PermissionPolicySnapshot:
    """Снимок сохраненной permission-политики по видам инструментов."""

    by_tool_kind: dict[str, str]


class PermissionPolicyStore:
    """Читает и записывает JSON-файл с persistent permission-политикой."""

    def __init__(self, file_path: Path | None = None) -> None:
        """Настраивает путь хранения policy, по умолчанию в домашней директории."""

        self._file_path = file_path or (Path.home() / ".acp-client" / "permission_policy.json")

    def load(self) -> PermissionPolicySnapshot:
        """Загружает policy-снимок из файла или возвращает пустое состояние."""

        if not self._file_path.exists():
            return PermissionPolicySnapshot(by_tool_kind={})

        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return PermissionPolicySnapshot(by_tool_kind={})

        if not isinstance(payload, dict):
            return PermissionPolicySnapshot(by_tool_kind={})

        policies = payload.get("policies")
        if not isinstance(policies, dict):
            return PermissionPolicySnapshot(by_tool_kind={})

        normalized: dict[str, str] = {}
        for tool_kind, decision_kind in policies.items():
            if not isinstance(tool_kind, str):
                continue
            if not isinstance(decision_kind, str):
                continue
            if decision_kind not in PERSISTENT_PERMISSION_KINDS:
                continue
            normalized[tool_kind] = decision_kind
        return PermissionPolicySnapshot(by_tool_kind=normalized)

    def save(self, snapshot: PermissionPolicySnapshot) -> None:
        """Сохраняет policy-снимок на диск и не бросает ошибки в UI слой."""

        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(
                json.dumps({"policies": snapshot.by_tool_kind}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            # Не блокируем работу TUI из-за локальных проблем записи файла.
            return


class PermissionManager:
    """Управляет автоприменением и сохранением решений permission-политики."""

    def __init__(self, store: PermissionPolicyStore | None = None) -> None:
        """Инициализирует менеджер и поднимает сохраненную policy из store."""

        self._store = store or PermissionPolicyStore()
        self._snapshot = self._store.load()

    def get_policy(self, tool_kind: str | None) -> str | None:
        """Возвращает сохраненный policy kind для инструмента или `None`."""

        if not isinstance(tool_kind, str) or not tool_kind:
            return None
        policy = self._snapshot.by_tool_kind.get(tool_kind)
        if policy not in PERSISTENT_PERMISSION_KINDS:
            return None
        return policy

    def resolve_option_id(self, request: RequestPermissionRequest) -> str | None:
        """Подбирает optionId для авто-ответа на основе сохраненной политики."""

        policy_kind = self.get_policy(request.params.toolCall.kind)
        if policy_kind is None:
            return None

        for option in request.params.options:
            if option.kind == policy_kind:
                return option.optionId
        return None

    def remember_decision(self, request: RequestPermissionRequest, option_id: str) -> bool:
        """Сохраняет persistent policy для tool kind, если выбрана `*_always` опция."""

        tool_kind = request.params.toolCall.kind
        if not isinstance(tool_kind, str) or not tool_kind:
            return False

        selected_option_kind = self._resolve_option_kind(request, option_id)
        if selected_option_kind not in PERSISTENT_PERMISSION_KINDS:
            return False

        self._snapshot.by_tool_kind[tool_kind] = selected_option_kind
        self._store.save(self._snapshot)
        return True

    def clear(self) -> None:
        """Сбрасывает всю сохраненную permission-политику."""

        self._snapshot = PermissionPolicySnapshot(by_tool_kind={})
        self._store.save(self._snapshot)

    @staticmethod
    def _resolve_option_kind(request: RequestPermissionRequest, option_id: str) -> str | None:
        """Возвращает kind выбранной option по optionId из request payload."""

        for option in request.params.options:
            if option.optionId == option_id:
                return option.kind
        return None
