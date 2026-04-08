from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest

from acp_client.tui.app import (
    FILE_VIEWER_LINE_LIMIT,
    HELP_FOOTER_DETAIL,
    READY_FOOTER_DETAIL,
    ACPClientApp,
    ConnectionState,
    build_error_state_status,
    build_retry_skipped_status,
    build_retry_started_status,
    format_footer_error,
    format_footer_status,
    format_offline_footer_detail,
    format_retry_footer_error,
)
from acp_client.tui.components import ChatView, FileTree, PlanPanel, PromptInput, Sidebar, ToolPanel


class _FakeChatView:
    """Минимальный тестовый double для проверки сообщений и завершения стрима."""

    def __init__(self) -> None:
        self.finished = False
        self.cleared = False
        self.system_messages: list[str] = []

    def finish_agent_message(self) -> None:
        """Отмечает завершение стриминга agent-сообщения."""

        self.finished = True

    def add_system_message(self, text: str) -> None:
        """Сохраняет системное сообщение для последующей проверки в тесте."""

        self.system_messages.append(text)

    def clear_messages(self) -> None:
        """Эмулирует очистку чата для action_clear_chat тестов."""

        self.cleared = True


class _FakePromptInput:
    """Минимальный PromptInput double для сценариев retry и persist state."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.focused = False

    def focus(self) -> None:
        """Отмечает фокусировку поля ввода."""

        self.focused = True


class _FakeSidebar:
    """Минимальный focusable sidebar double для hotkey-навигации."""

    def __init__(self) -> None:
        self.focused = False

    def focus(self) -> None:
        """Отмечает перевод фокуса на sidebar."""

        self.focused = True


class _FakeToolPanel:
    """Минимальный double tool panel для replay-тестов."""

    def __init__(self) -> None:
        self.updates_count = 0

    def apply_update(self, _update: object) -> None:
        """Сохраняет факт применения update в тесте."""

        self.updates_count += 1


class _FakeFileTree:
    """Минимальный double FileTree для тестов file-system сценариев."""

    def __init__(self) -> None:
        self.refreshed = False
        self.changed_paths: list[Path] = []

    def mark_changed(self, path: Path) -> None:
        """Сохраняет путь, который app пометил как измененный."""

        self.changed_paths.append(path)

    def refresh_tree(self) -> None:
        """Отмечает факт обновления дерева файлов."""

        self.refreshed = True


class _FakePlanPanel:
    """Минимальный double plan panel для replay-тестов."""

    def __init__(self) -> None:
        self.entries_count = 0

    def apply_update(self, update: object) -> None:
        """Сохраняет размер snapshot плана из update объекта."""

        entries = getattr(update, "entries", [])
        self.entries_count = len(entries)


class _FakeHistoryCache:
    """Минимальный double history cache для тестов fallback replay."""

    def __init__(self) -> None:
        self.saved_updates: list[tuple[str, list[Any]]] = []
        self.loaded_session_ids: list[str] = []
        self.load_result: list[Any] = []

    def save_updates(self, *, session_id: str, updates: list[Any]) -> None:
        """Сохраняет аргументы вызова save_updates для проверок."""

        self.saved_updates.append((session_id, updates))

    def load_updates(self, *, session_id: str) -> list[Any]:
        """Возвращает заранее заданный результат load_updates."""

        self.loaded_session_ids.append(session_id)
        return self.load_result


def test_format_footer_error_extracts_jsonrpc_code_and_reason() -> None:
    error = RuntimeError("WebSocket initialize failed: -32601 Method not found")

    formatted = format_footer_error(error, prefix="Connection error")

    assert "Connection error" in formatted
    assert "code=-32601" in formatted
    assert "Method not found" in formatted


def test_format_footer_error_handles_plain_error_message() -> None:
    error = RuntimeError("temporary network timeout")

    formatted = format_footer_error(error, prefix="Connected | Error")

    assert formatted == "Connected | Error | temporary network timeout"


def test_format_retry_footer_error_adds_retry_hint() -> None:
    error = RuntimeError("temporary network timeout")

    formatted = format_retry_footer_error(error, action_label="prompt", pending_count=2)

    assert formatted == "Error | temporary network timeout | Ctrl+R retry prompt | queued=2"


def test_failed_operations_queue_deduplicates_by_label() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)

    async def first_action() -> None:
        return None

    async def second_action() -> None:
        return None

    app._remember_failed_operation(label="prompt", action=first_action)  # noqa: SLF001
    app._remember_failed_operation(label="prompt", action=second_action)  # noqa: SLF001

    assert len(app._failed_operations) == 1  # noqa: SLF001
    failed_operation = app._pop_failed_operation()  # noqa: SLF001
    assert failed_operation is not None
    assert failed_operation.label == "prompt"


def test_failed_operations_queue_keeps_latest_five() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)

    async def retry_action() -> None:
        return None

    for index in range(6):
        app._remember_failed_operation(  # noqa: SLF001
            label=f"op_{index}",
            action=retry_action,
        )

    assert len(app._failed_operations) == 5  # noqa: SLF001
    assert app._failed_operations[0].label == "op_1"  # noqa: SLF001
    assert app._failed_operations[-1].label == "op_5"  # noqa: SLF001


def test_format_offline_footer_detail_includes_retry_hint() -> None:
    formatted = format_offline_footer_detail(reason="Prompt blocked: connection unavailable")

    assert formatted == "Prompt blocked: connection unavailable | Ctrl+R retry failed op"


def test_format_offline_footer_detail_uses_default_reason_when_empty() -> None:
    formatted = format_offline_footer_detail(reason="   ")

    assert formatted == "connection unavailable | Ctrl+R retry failed op"


def test_format_footer_status_builds_state_prefixed_line() -> None:
    formatted = format_footer_status(state=ConnectionState.OFFLINE, detail="connection unavailable")

    assert formatted == "Offline | connection unavailable"


def test_build_error_state_status_returns_offline_when_not_ready() -> None:
    error = RuntimeError("network timeout")

    state, detail = build_error_state_status(
        error,
        connection_ready=False,
        degraded_prefix="Error creating session",
    )

    assert state == ConnectionState.OFFLINE
    assert detail == "network timeout | Ctrl+R retry failed op"


def test_build_error_state_status_returns_degraded_with_prefix() -> None:
    error = RuntimeError("method failed")

    state, detail = build_error_state_status(
        error,
        connection_ready=True,
        degraded_prefix="Error switching session",
    )

    assert state == ConnectionState.DEGRADED
    assert detail == "Error switching session | method failed"


def test_build_error_state_status_adds_retry_hint_for_retryable_action() -> None:
    error = RuntimeError("temporary network timeout")

    state, detail = build_error_state_status(
        error,
        connection_ready=True,
        degraded_prefix="Error",
        include_retry_hint=True,
        retry_action_label="prompt",
        pending_count=2,
    )

    assert state == ConnectionState.DEGRADED
    assert detail == "Error | temporary network timeout | Ctrl+R retry prompt | queued=2"


def test_build_retry_skipped_status_returns_offline_when_disconnected() -> None:
    state, detail = build_retry_skipped_status(connection_ready=False)

    assert state == ConnectionState.OFFLINE
    assert detail == "Retry skipped: no failed operation | Ctrl+R retry failed op"


def test_build_retry_started_status_returns_reconnecting_when_disconnected() -> None:
    state, detail = build_retry_started_status(
        connection_ready=False,
        label="prompt",
        remaining_count=1,
    )

    assert state == ConnectionState.RECONNECTING
    assert detail == "Retrying failed operation: prompt (1 remaining)"


def test_focus_session_list_alias_focuses_sidebar(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    sidebar = _FakeSidebar()

    def _query_one(selector: object) -> _FakeSidebar:
        if selector is Sidebar:
            return sidebar
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    monkeypatch.setattr(app, "query_one", _query_one)

    app.action_focus_session_list()

    assert sidebar.focused is True
    assert app._focus_index == 0  # noqa: SLF001


def test_cycle_focus_switches_between_sidebar_and_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    sidebar = _FakeSidebar()
    prompt = _FakePromptInput()

    def _query_one(selector: object) -> _FakeSidebar | _FakePromptInput:
        if selector is Sidebar:
            return sidebar
        if selector is PromptInput:
            return prompt
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    monkeypatch.setattr(app, "query_one", _query_one)

    app.action_cycle_focus()
    app.action_cycle_focus()

    assert sidebar.focused is True
    assert prompt.focused is True
    assert app._focus_index == 1  # noqa: SLF001


def test_clear_chat_resets_messages_and_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    transitions: list[tuple[ConnectionState, str]] = []

    def _query_one(selector: object) -> _FakeChatView:
        if selector is ChatView:
            return chat
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "_set_connection_state", _capture_state)

    app.action_clear_chat()

    assert chat.cleared is True
    assert transitions == [(ConnectionState.CONNECTED, "Chat cleared")]


def test_open_help_adds_system_message_and_help_status(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    transitions: list[tuple[ConnectionState, str]] = []

    def _query_one(selector: object) -> _FakeChatView:
        if selector is ChatView:
            return chat
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "_set_connection_state", _capture_state)

    app.action_open_help()

    assert len(chat.system_messages) == 1
    assert "Горячие клавиши:" in chat.system_messages[0]
    assert transitions == [(ConnectionState.CONNECTED, HELP_FOOTER_DETAIL)]


def test_render_replay_updates_routes_plan_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    tools = _FakeToolPanel()
    plans = _FakePlanPanel()

    def _query_one(selector: object) -> object:
        if selector is ChatView:
            return chat
        if selector is ToolPanel:
            return tools
        if selector is PlanPanel:
            return plans
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    monkeypatch.setattr(app, "query_one", _query_one)

    from acp_client.messages import SessionUpdateNotification

    replay_updates = [
        SessionUpdateNotification.model_validate(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "sess_1",
                    "update": {
                        "sessionUpdate": "plan",
                        "entries": [
                            {"content": "Шаг 1", "priority": "high", "status": "completed"},
                            {
                                "content": "Шаг 2",
                                "priority": "medium",
                                "status": "in_progress",
                            },
                        ],
                    },
                },
            }
        )
    ]

    app._render_replay_updates(replay_updates)  # noqa: SLF001

    assert plans.entries_count == 2


def test_resolve_replay_updates_uses_server_snapshot_and_persists() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    cache = _FakeHistoryCache()
    cast(Any, app)._history_cache = cache  # noqa: SLF001

    from acp_client.messages import SessionUpdateNotification

    server_updates = [
        SessionUpdateNotification.model_validate(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "sess_1",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "server"},
                    },
                },
            }
        )
    ]

    resolved = app._resolve_replay_updates(  # noqa: SLF001
        session_id="sess_1",
        server_updates=server_updates,
    )

    assert resolved == server_updates
    assert cache.saved_updates == [("sess_1", server_updates)]


def test_resolve_replay_updates_falls_back_to_history_cache() -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    cache = _FakeHistoryCache()
    cast(Any, app)._history_cache = cache  # noqa: SLF001

    from acp_client.messages import SessionUpdateNotification

    cached_updates = [
        SessionUpdateNotification.model_validate(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "sess_1",
                    "update": {
                        "sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": "cached"},
                    },
                },
            }
        )
    ]
    cache.load_result = cached_updates

    resolved = app._resolve_replay_updates(  # noqa: SLF001
        session_id="sess_1",
        server_updates=[],
    )

    assert resolved == cached_updates
    assert cache.loaded_session_ids == ["sess_1"]


def test_reconnect_callbacks_emit_runtime_state_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    transitions: list[tuple[ConnectionState, str]] = []

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)

    app._on_reconnect_attempt("session/prompt")  # noqa: SLF001
    app._on_reconnect_recovered("session/prompt")  # noqa: SLF001

    assert transitions == [
        (ConnectionState.RECONNECTING, "retry method=session/prompt"),
        (ConnectionState.CONNECTED, "Recovered after retry: session/prompt"),
    ]


def test_retry_prompt_without_failed_operations_uses_offline_state_when_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    transitions: list[tuple[ConnectionState, str]] = []

    monkeypatch.setattr(app._connection, "is_ready", lambda: False)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)

    app.action_retry_prompt()

    assert transitions == [
        (ConnectionState.OFFLINE, "Retry skipped: no failed operation | Ctrl+R retry failed op")
    ]


def test_retry_prompt_starts_reconnecting_when_operation_exists_but_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    transitions: list[tuple[ConnectionState, str]] = []
    workers_started = 0

    async def retry_action() -> None:
        return None

    def _capture_worker(work: object, *args: object, **kwargs: object) -> None:
        nonlocal workers_started
        workers_started += 1
        # Закрываем coroutine, чтобы не оставлять un-awaited объекты в тесте.
        close_callable = getattr(work, "close", None)
        if callable(close_callable):
            close_callable()

    app._remember_failed_operation(label="prompt", action=retry_action)  # noqa: SLF001
    monkeypatch.setattr(app._connection, "is_ready", lambda: False)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "run_worker", _capture_worker)

    app.action_retry_prompt()

    assert workers_started == 1
    assert transitions == [
        (ConnectionState.RECONNECTING, "Retrying failed operation: prompt (0 remaining)")
    ]


@pytest.mark.asyncio
async def test_offline_prompt_blocked_then_reconnect_then_retry_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    prompt_input = _FakePromptInput(text="draft text")
    transitions: list[tuple[ConnectionState, str]] = []
    worker_tasks: list[asyncio.Task[object]] = []
    sent_prompts: list[str] = []
    connection_ready = False

    async def _send_prompt_success(
        text: str,
        _on_update: object,
        _on_permission: object,
        _on_fs_read: object,
        _on_fs_write: object,
        _on_terminal_create: object,
        _on_terminal_output: object,
        _on_terminal_wait_for_exit: object,
        _on_terminal_release: object,
        _on_terminal_kill: object,
    ) -> None:
        sent_prompts.append(text)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> object:
        if selector is ChatView:
            return chat
        from acp_client.tui.components import PromptInput

        if selector is PromptInput:
            return prompt_input
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _run_worker(work: object, *_args: object, **_kwargs: object) -> asyncio.Task[object]:
        if not asyncio.iscoroutine(work):
            msg = "Expected coroutine for retry worker"
            raise AssertionError(msg)
        task = asyncio.create_task(work)
        worker_tasks.append(task)
        return task

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "run_worker", _run_worker)
    monkeypatch.setattr(app._connection, "is_ready", lambda: connection_ready)
    monkeypatch.setattr(app._sessions, "send_prompt", _send_prompt_success)

    from acp_client.tui.components import PromptInput

    await app.on_prompt_input_submitted(PromptInput.Submitted("retry me"))

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert transitions[0] == (
        ConnectionState.OFFLINE,
        "Prompt blocked: connection unavailable | Ctrl+R retry failed op",
    )
    assert chat.system_messages == ["Отправка prompt отложена: нет подключения к серверу"]

    connection_ready = True
    app._on_reconnect_recovered("session/prompt")  # noqa: SLF001
    app.action_retry_prompt()
    await asyncio.gather(*worker_tasks)

    assert sent_prompts == ["retry me"]
    assert len(app._failed_operations) == 0  # noqa: SLF001
    assert transitions[-3:] == [
        (ConnectionState.CONNECTED, "Recovered after retry: session/prompt"),
        (ConnectionState.CONNECTED, "Retrying failed operation: prompt (0 remaining)"),
        (ConnectionState.CONNECTED, READY_FOOTER_DETAIL),
    ]


@pytest.mark.asyncio
async def test_offline_prompt_blocked_then_reconnect_retry_failure_returns_to_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    prompt_input = _FakePromptInput(text="draft text")
    transitions: list[tuple[ConnectionState, str]] = []
    worker_tasks: list[asyncio.Task[object]] = []
    connection_ready = False

    async def _send_prompt_fail(
        text: str,
        _on_update: object,
        _on_permission: object,
        _on_fs_read: object,
        _on_fs_write: object,
        _on_terminal_create: object,
        _on_terminal_output: object,
        _on_terminal_wait_for_exit: object,
        _on_terminal_release: object,
        _on_terminal_kill: object,
    ) -> None:
        if text != "retry me":
            msg = f"Unexpected prompt: {text}"
            raise AssertionError(msg)
        raise RuntimeError("retry still failed")

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> object:
        if selector is ChatView:
            return chat
        from acp_client.tui.components import PromptInput

        if selector is PromptInput:
            return prompt_input
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _run_worker(work: object, *_args: object, **_kwargs: object) -> asyncio.Task[object]:
        if not asyncio.iscoroutine(work):
            msg = "Expected coroutine for retry worker"
            raise AssertionError(msg)
        task = asyncio.create_task(work)
        worker_tasks.append(task)
        return task

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "run_worker", _run_worker)
    monkeypatch.setattr(app._connection, "is_ready", lambda: connection_ready)
    monkeypatch.setattr(app._sessions, "send_prompt", _send_prompt_fail)

    from acp_client.tui.components import PromptInput

    await app.on_prompt_input_submitted(PromptInput.Submitted("retry me"))

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert transitions[0] == (
        ConnectionState.OFFLINE,
        "Prompt blocked: connection unavailable | Ctrl+R retry failed op",
    )

    connection_ready = True
    app._on_reconnect_recovered("session/prompt")  # noqa: SLF001
    app.action_retry_prompt()
    await asyncio.gather(*worker_tasks)

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert app._failed_operations[0].label == "prompt"  # noqa: SLF001
    assert chat.system_messages == [
        "Отправка prompt отложена: нет подключения к серверу",
        "Ошибка отправки prompt: retry still failed",
    ]
    assert transitions[-3:] == [
        (ConnectionState.CONNECTED, "Recovered after retry: session/prompt"),
        (ConnectionState.CONNECTED, "Retrying failed operation: prompt (0 remaining)"),
        (
            ConnectionState.DEGRADED,
            "Error | retry still failed | Ctrl+R retry prompt | queued=0",
        ),
    ]


@pytest.mark.asyncio
async def test_offline_prompt_blocked_then_retry_loses_connection_returns_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    prompt_input = _FakePromptInput(text="draft text")
    transitions: list[tuple[ConnectionState, str]] = []
    worker_tasks: list[asyncio.Task[object]] = []
    connection_ready = False

    async def _send_prompt_disconnect(
        text: str,
        _on_update: object,
        _on_permission: object,
        _on_fs_read: object,
        _on_fs_write: object,
        _on_terminal_create: object,
        _on_terminal_output: object,
        _on_terminal_wait_for_exit: object,
        _on_terminal_release: object,
        _on_terminal_kill: object,
    ) -> None:
        nonlocal connection_ready
        if text != "retry me":
            msg = f"Unexpected prompt: {text}"
            raise AssertionError(msg)
        connection_ready = False
        raise RuntimeError("transport disconnected")

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> object:
        if selector is ChatView:
            return chat
        from acp_client.tui.components import PromptInput

        if selector is PromptInput:
            return prompt_input
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _run_worker(work: object, *_args: object, **_kwargs: object) -> asyncio.Task[object]:
        if not asyncio.iscoroutine(work):
            msg = "Expected coroutine for retry worker"
            raise AssertionError(msg)
        task = asyncio.create_task(work)
        worker_tasks.append(task)
        return task

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "run_worker", _run_worker)
    monkeypatch.setattr(app._connection, "is_ready", lambda: connection_ready)
    monkeypatch.setattr(app._sessions, "send_prompt", _send_prompt_disconnect)

    from acp_client.tui.components import PromptInput

    await app.on_prompt_input_submitted(PromptInput.Submitted("retry me"))

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert transitions[0] == (
        ConnectionState.OFFLINE,
        "Prompt blocked: connection unavailable | Ctrl+R retry failed op",
    )

    connection_ready = True
    app._on_reconnect_recovered("session/prompt")  # noqa: SLF001
    app.action_retry_prompt()
    await asyncio.gather(*worker_tasks)

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert app._failed_operations[0].label == "prompt"  # noqa: SLF001
    assert chat.system_messages == [
        "Отправка prompt отложена: нет подключения к серверу",
        "Ошибка отправки prompt: transport disconnected",
    ]
    assert transitions[-3:] == [
        (ConnectionState.CONNECTED, "Recovered after retry: session/prompt"),
        (ConnectionState.CONNECTED, "Retrying failed operation: prompt (0 remaining)"),
        (
            ConnectionState.OFFLINE,
            "transport disconnected | Ctrl+R retry failed op",
        ),
    ]


@pytest.mark.asyncio
async def test_multiple_offline_prompt_blocks_retry_latest_prompt_after_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    prompt_input = _FakePromptInput(text="draft text")
    transitions: list[tuple[ConnectionState, str]] = []
    worker_tasks: list[asyncio.Task[object]] = []
    sent_prompts: list[str] = []
    connection_ready = False

    async def _send_prompt_success(
        text: str,
        _on_update: object,
        _on_permission: object,
        _on_fs_read: object,
        _on_fs_write: object,
        _on_terminal_create: object,
        _on_terminal_output: object,
        _on_terminal_wait_for_exit: object,
        _on_terminal_release: object,
        _on_terminal_kill: object,
    ) -> None:
        sent_prompts.append(text)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> object:
        if selector is ChatView:
            return chat
        from acp_client.tui.components import PromptInput

        if selector is PromptInput:
            return prompt_input
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    def _run_worker(work: object, *_args: object, **_kwargs: object) -> asyncio.Task[object]:
        if not asyncio.iscoroutine(work):
            msg = "Expected coroutine for retry worker"
            raise AssertionError(msg)
        task = asyncio.create_task(work)
        worker_tasks.append(task)
        return task

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "run_worker", _run_worker)
    monkeypatch.setattr(app._connection, "is_ready", lambda: connection_ready)
    monkeypatch.setattr(app._sessions, "send_prompt", _send_prompt_success)

    from acp_client.tui.components import PromptInput

    await app.on_prompt_input_submitted(PromptInput.Submitted("first prompt"))
    await app.on_prompt_input_submitted(PromptInput.Submitted("latest prompt"))

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert app._failed_operations[0].label == "prompt"  # noqa: SLF001
    assert chat.system_messages == [
        "Отправка prompt отложена: нет подключения к серверу",
        "Отправка prompt отложена: нет подключения к серверу",
    ]

    connection_ready = True
    app._on_reconnect_recovered("session/prompt")  # noqa: SLF001
    app.action_retry_prompt()
    await asyncio.gather(*worker_tasks)

    assert sent_prompts == ["latest prompt"]
    assert len(app._failed_operations) == 0  # noqa: SLF001
    assert transitions[-3:] == [
        (ConnectionState.CONNECTED, "Recovered after retry: session/prompt"),
        (ConnectionState.CONNECTED, "Retrying failed operation: prompt (0 remaining)"),
        (ConnectionState.CONNECTED, READY_FOOTER_DETAIL),
    ]


@pytest.mark.asyncio
async def test_cancel_prompt_sets_reconnecting_state_when_disconnect_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    transitions: list[tuple[ConnectionState, str]] = []

    async def _cancel_ok() -> None:
        return None

    monkeypatch.setattr(app._sessions, "cancel", _cancel_ok)
    monkeypatch.setattr(app._connection, "is_ready", lambda: False)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> _FakeChatView:
        if selector is ChatView:
            return chat
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)

    await app.action_cancel_prompt()

    assert chat.finished is True
    assert transitions == [
        (ConnectionState.RECONNECTING, "Cancel requested during reconnect"),
    ]


@pytest.mark.asyncio
async def test_cancel_prompt_failure_is_queued_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()
    transitions: list[tuple[ConnectionState, str]] = []

    async def _cancel_fail() -> None:
        msg = "cancel failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(app._sessions, "cancel", _cancel_fail)
    monkeypatch.setattr(app._connection, "is_ready", lambda: True)

    def _capture_state(state: ConnectionState, *, detail: str) -> None:
        transitions.append((state, detail))

    def _query_one(selector: object) -> _FakeChatView:
        if selector is ChatView:
            return chat
        msg = f"Unexpected selector: {selector}"
        raise AssertionError(msg)

    monkeypatch.setattr(app, "_set_connection_state", _capture_state)
    monkeypatch.setattr(app, "query_one", _query_one)

    await app.action_cancel_prompt()

    assert len(app._failed_operations) == 1  # noqa: SLF001
    assert app._failed_operations[0].label == "cancel_prompt"  # noqa: SLF001
    assert transitions == [
        (ConnectionState.DEGRADED, "Error cancelling prompt | cancel failed"),
    ]
    assert chat.system_messages == ["Ошибка отмены prompt: cancel failed"]


def test_on_file_written_refreshes_file_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    tree = _FakeFileTree()

    def _query_one(selector: object) -> _FakeFileTree:
        if selector is not FileTree:
            msg = f"Unexpected selector: {selector}"
            raise AssertionError(msg)
        return tree

    monkeypatch.setattr(app, "query_one", _query_one)

    app._on_file_written(Path("/tmp/example.txt"))  # noqa: SLF001

    assert tree.refreshed is True
    assert tree.changed_paths == [Path("/tmp/example.txt")]


def test_file_tree_open_request_reads_file_and_opens_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    pushed_screens: list[object] = []
    read_calls: list[tuple[str, int, int]] = []

    def _read_file(path: str, line: int | None = None, limit: int | None = None) -> str:
        read_calls.append((path, line or 0, limit or 0))
        return "print('ok')\n"

    def _push_screen(screen: object) -> None:
        pushed_screens.append(screen)

    monkeypatch.setattr(app._filesystem, "read_file", _read_file)
    monkeypatch.setattr(app, "push_screen", _push_screen)

    from acp_client.tui.components.file_tree import FileTree as FileTreeWidget

    app.on_file_tree_file_open_requested(FileTreeWidget.FileOpenRequested(Path("/tmp/demo.py")))

    assert read_calls == [("/tmp/demo.py", 1, FILE_VIEWER_LINE_LIMIT)]
    assert len(pushed_screens) == 1


def test_terminal_create_and_output_are_reported_to_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()

    def _query_one(selector: object) -> _FakeChatView:
        if selector is not ChatView:
            msg = f"Unexpected selector: {selector}"
            raise AssertionError(msg)
        return chat

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app._terminal, "create_terminal", lambda _cmd: "term_1")
    monkeypatch.setattr(app._terminal, "get_output", lambda _term_id: "line1\n")

    terminal_id = app._on_terminal_create("python -V")  # noqa: SLF001
    output = app._on_terminal_output("term_1")  # noqa: SLF001

    assert terminal_id == "term_1"
    assert output == "line1\n"
    assert chat.system_messages == [
        "Терминал запущен: term_1 | python -V",
        "[terminal term_1]\nline1",
    ]


def test_terminal_wait_and_kill_are_reported_to_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()

    def _query_one(selector: object) -> _FakeChatView:
        if selector is not ChatView:
            msg = f"Unexpected selector: {selector}"
            raise AssertionError(msg)
        return chat

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app._terminal, "wait_for_exit", lambda _term_id: 0)
    monkeypatch.setattr(app._terminal, "kill_terminal", lambda _term_id: True)

    wait_result = app._on_terminal_wait_for_exit("term_1")  # noqa: SLF001
    killed = app._on_terminal_kill("term_1")  # noqa: SLF001

    assert wait_result == 0
    assert killed is True
    assert chat.system_messages == [
        "Терминал завершен: term_1 (exit=0)",
        "Терминал остановлен: term_1",
    ]


@pytest.mark.asyncio
async def test_permission_request_auto_applies_saved_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()

    def _query_one(selector: object) -> _FakeChatView:
        if selector is not ChatView:
            msg = f"Unexpected selector: {selector}"
            raise AssertionError(msg)
        return chat

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "_set_connection_state", lambda _state, detail: detail)

    request_payload: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": "perm_1",
        "method": "session/request_permission",
        "params": {
            "sessionId": "sess_1",
            "toolCall": {"toolCallId": "call_1", "title": "Run", "kind": "execute"},
            "options": [
                {"optionId": "allow_always_1", "name": "Allow always", "kind": "allow_always"},
                {"optionId": "reject_once_1", "name": "Reject once", "kind": "reject_once"},
            ],
        },
    }
    app._permission_manager.clear()  # noqa: SLF001
    app._permission_manager._snapshot.by_tool_kind["execute"] = "allow_always"  # noqa: SLF001
    monkeypatch.setattr(
        app,
        "push_screen_wait",
        lambda _modal: (_ for _ in ()).throw(AssertionError("modal should not open")),
    )

    option_id = await app._on_permission_request(request_payload)  # noqa: SLF001

    assert option_id == "allow_always_1"
    assert "Автоприменено разрешение: allow_always_1" in chat.system_messages


@pytest.mark.asyncio
async def test_permission_request_saves_policy_after_always_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = ACPClientApp(host="127.0.0.1", port=8765)
    chat = _FakeChatView()

    def _query_one(selector: object) -> _FakeChatView:
        if selector is not ChatView:
            msg = f"Unexpected selector: {selector}"
            raise AssertionError(msg)
        return chat

    async def _push_screen_wait(_modal: object) -> str:
        return "allow_always_1"

    monkeypatch.setattr(app, "query_one", _query_one)
    monkeypatch.setattr(app, "_set_connection_state", lambda _state, detail: detail)
    monkeypatch.setattr(app, "push_screen_wait", _push_screen_wait)

    request_payload: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": "perm_1",
        "method": "session/request_permission",
        "params": {
            "sessionId": "sess_1",
            "toolCall": {"toolCallId": "call_1", "title": "Run", "kind": "execute"},
            "options": [
                {"optionId": "allow_always_1", "name": "Allow always", "kind": "allow_always"},
                {"optionId": "reject_once_1", "name": "Reject once", "kind": "reject_once"},
            ],
        },
    }

    option_id = await app._on_permission_request(request_payload)  # noqa: SLF001

    assert option_id == "allow_always_1"
    assert app._permission_manager.get_policy("execute") == "allow_always"  # noqa: SLF001
    assert "Сохранена policy разрешений для kind=execute" in chat.system_messages
