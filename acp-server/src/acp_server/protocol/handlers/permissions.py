"""Обработчики методов управления разрешениями.

Содержит логику обработки session/request_permission и related.
"""

from __future__ import annotations

from typing import Any

from ...messages import JsonRpcId
from ..state import SessionState


def find_session_by_permission_request_id(
    permission_request_id: JsonRpcId,
    sessions: dict[str, SessionState],
) -> SessionState | None:
    """Ищет сессию с активным turn, ожидающим ответ по permission-request.

    Пример использования:
        session = find_session_by_permission_request_id("perm_1", sessions)
    """

    for session in sessions.values():
        active_turn = session.active_turn
        if active_turn is None:
            continue
        if active_turn.permission_request_id == permission_request_id:
            return session
    return None


def extract_permission_outcome(result: Any) -> str | None:
    """Извлекает outcome из `session/request_permission` response.

    Поддерживает текущий ACP shape (`{"outcome": {"outcome": ...}}`) и
    legacy-вариант (`{"outcome": ...}`) для обратной совместимости.

    Пример использования:
        outcome = extract_permission_outcome(
            {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
        )
    """

    if not isinstance(result, dict):
        return None

    nested_outcome = result.get("outcome")
    if isinstance(nested_outcome, dict):
        raw_value = nested_outcome.get("outcome")
        if isinstance(raw_value, str):
            return raw_value

    # Legacy fallback для старых клиентов.
    if isinstance(nested_outcome, str):
        return nested_outcome
    return None


def extract_permission_option_id(result: Any) -> str | None:
    """Извлекает `optionId` из `session/request_permission` response.

    Поддерживает ACP shape (`{"outcome": {"optionId": ...}}`) и legacy
    (`{"optionId": ...}`) формат для обратной совместимости.

    Пример использования:
        option_id = extract_permission_option_id(
            {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
        )
    """

    if not isinstance(result, dict):
        return None

    nested_outcome = result.get("outcome")
    if isinstance(nested_outcome, dict):
        raw_option_id = nested_outcome.get("optionId")
        if isinstance(raw_option_id, str):
            return raw_option_id

    raw_option_id = result.get("optionId")
    if isinstance(raw_option_id, str):
        return raw_option_id
    return None


def resolve_permission_option_kind(
    option_id: str | None,
    permission_options: list[dict[str, Any]],
) -> str | None:
    """Возвращает kind permission-опции по ее `optionId`.

    Пример использования:
        kind = resolve_permission_option_kind("allow_once", options)
    """

    if option_id is None:
        return None
    for option in permission_options:
        if not isinstance(option, dict):
            continue
        if option.get("optionId") != option_id:
            continue
        kind_value = option.get("kind")
        if isinstance(kind_value, str):
            return kind_value
        return None
    return None


def resolve_remembered_permission_decision(
    *,
    session: SessionState,
    tool_kind: str,
) -> str:
    """Возвращает применяемое policy-решение для tool kind.

    Возвращаемые значения:
    - `allow`: выполнить tool-call без запроса permission.
    - `reject`: отклонить tool-call без запроса permission.
    - `ask`: запросить решение у клиента через `session/request_permission`.

    Пример использования:
        decision = resolve_remembered_permission_decision(
            session=state,
            tool_kind="execute",
        )
    """

    remembered = session.permission_policy.get(tool_kind)
    if remembered == "allow_always":
        return "allow"
    if remembered == "reject_always":
        return "reject"
    return "ask"


def build_permission_options() -> list[dict[str, Any]]:
    """Возвращает варианты решения для `session/request_permission`.

    Пример использования:
        options = build_permission_options()
    """

    return [
        {
            "optionId": "allow_once",
            "name": "Allow once",
            "kind": "allow_once",
        },
        {
            "optionId": "allow_always",
            "name": "Always allow this tool",
            "kind": "allow_always",
        },
        {
            "optionId": "reject_once",
            "name": "Reject once",
            "kind": "reject_once",
        },
        {
            "optionId": "reject_always",
            "name": "Always reject this tool",
            "kind": "reject_always",
        },
    ]


def consume_cancelled_permission_response(
    request_id: JsonRpcId,
    sessions: dict[str, SessionState],
) -> bool:
    """Поглощает late-response на ранее отмененный permission-request.

    Возвращает `True`, если идентификатор найден в canceled-tombstones и
    удален; иначе `False`.

    Пример использования:
        if consume_cancelled_permission_response("perm_1", sessions):
            ...
    """

    for session in sessions.values():
        if request_id not in session.cancelled_permission_requests:
            continue
        session.cancelled_permission_requests.remove(request_id)
        return True
    return False


def consume_cancelled_client_rpc_response(
    request_id: JsonRpcId,
    sessions: dict[str, SessionState],
) -> bool:
    """Поглощает late-response на ранее отмененный agent->client RPC.

    Возвращает `True`, если идентификатор найден в canceled-tombstones и
    удален; иначе `False`.

    Пример использования:
        if consume_cancelled_client_rpc_response("rpc_1", sessions):
            ...
    """

    for session in sessions.values():
        if request_id not in session.cancelled_client_rpc_requests:
            continue
        session.cancelled_client_rpc_requests.remove(request_id)
        return True
    return False
