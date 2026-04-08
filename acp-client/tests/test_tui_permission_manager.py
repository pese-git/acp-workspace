from __future__ import annotations

from pathlib import Path

from acp_client.messages import RequestPermissionRequest
from acp_client.tui.managers.permission import PermissionManager, PermissionPolicyStore


def _build_permission_request() -> RequestPermissionRequest:
    """Создает типизированный permission-request для тестов policy менеджера."""

    return RequestPermissionRequest.model_validate(
        {
            "jsonrpc": "2.0",
            "id": "perm_1",
            "method": "session/request_permission",
            "params": {
                "sessionId": "sess_1",
                "toolCall": {
                    "toolCallId": "call_1",
                    "title": "Run command",
                    "kind": "execute",
                },
                "options": [
                    {"optionId": "allow_once_1", "name": "Allow once", "kind": "allow_once"},
                    {
                        "optionId": "allow_always_1",
                        "name": "Allow always",
                        "kind": "allow_always",
                    },
                    {
                        "optionId": "reject_always_1",
                        "name": "Reject always",
                        "kind": "reject_always",
                    },
                ],
            },
        }
    )


def test_permission_manager_saves_and_resolves_persistent_policy(tmp_path: Path) -> None:
    store = PermissionPolicyStore(file_path=tmp_path / "permission_policy.json")
    manager = PermissionManager(store=store)
    request = _build_permission_request()

    saved = manager.remember_decision(request, "allow_always_1")
    resolved = manager.resolve_option_id(request)

    assert saved is True
    assert resolved == "allow_always_1"


def test_permission_manager_does_not_persist_once_decision(tmp_path: Path) -> None:
    store = PermissionPolicyStore(file_path=tmp_path / "permission_policy.json")
    manager = PermissionManager(store=store)
    request = _build_permission_request()

    saved = manager.remember_decision(request, "allow_once_1")

    assert saved is False
    assert manager.resolve_option_id(request) is None


def test_permission_manager_clear_resets_policy(tmp_path: Path) -> None:
    store = PermissionPolicyStore(file_path=tmp_path / "permission_policy.json")
    manager = PermissionManager(store=store)
    request = _build_permission_request()
    manager.remember_decision(request, "reject_always_1")

    manager.clear()

    assert manager.get_policy("execute") is None
