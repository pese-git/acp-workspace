from __future__ import annotations

import asyncio

import pytest

from acp_client.tui.app import (
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
from acp_client.tui.components import ChatView


class _FakeChatView:
    """Минимальный тестовый double для проверки сообщений и завершения стрима."""

    def __init__(self) -> None:
        self.finished = False
        self.system_messages: list[str] = []

    def finish_agent_message(self) -> None:
        """Отмечает завершение стриминга agent-сообщения."""

        self.finished = True

    def add_system_message(self, text: str) -> None:
        """Сохраняет системное сообщение для последующей проверки в тесте."""

        self.system_messages.append(text)


class _FakePromptInput:
    """Минимальный PromptInput double для сценариев retry и persist state."""

    def __init__(self, text: str = "") -> None:
        self.text = text


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
        (
            ConnectionState.CONNECTED,
            "Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch",
        ),
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
        (
            ConnectionState.CONNECTED,
            "Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch",
        ),
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
