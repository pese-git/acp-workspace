"""Главное Textual приложение ACP-Client TUI."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical

from acp_client.messages import (
    RequestPermissionRequest,
    SessionUpdateNotification,
    ToolCallUpdate,
    parse_request_permission_request,
    parse_tool_call_update,
)

from .components import (
    ChatView,
    FooterBar,
    HeaderBar,
    PermissionModal,
    PromptInput,
    Sidebar,
    ToolPanel,
)
from .managers import (
    ACPConnectionManager,
    SessionManager,
    TUIStateSnapshot,
    UIStateStore,
    UpdateMessageHandler,
)

READY_FOOTER_DETAIL = "Ready | Ctrl+S/B sessions | Tab cycle focus | Ctrl+L clear | Ctrl+Enter send"
HELP_FOOTER_DETAIL = (
    "Help | Ctrl+S/B sessions | Tab cycle focus | Ctrl+N new | Ctrl+J/K switch | "
    "Ctrl+L clear | Ctrl+R retry | Ctrl+C cancel | Ctrl+Q quit"
)


class ConnectionState(StrEnum):
    """Единый набор состояний подключения для Header и Footer."""

    CONNECTED = "Connected"
    RECONNECTING = "Reconnecting"
    DEGRADED = "Degraded"
    OFFLINE = "Offline"


def format_footer_status(*, state: ConnectionState, detail: str) -> str:
    """Собирает строку footer в формате `<state> | <detail>` для всех режимов."""

    compact_detail = detail.strip()
    if not compact_detail:
        return state.value
    return f"{state.value} | {compact_detail}"


def format_offline_footer_detail(*, reason: str) -> str:
    """Формирует detail для offline режима с подсказкой по retry."""

    compact_reason = reason.strip()
    if not compact_reason:
        compact_reason = "connection unavailable"
    return f"{compact_reason} | Ctrl+R retry failed op"


def build_error_state_status(
    exc: Exception,
    *,
    connection_ready: bool,
    degraded_prefix: str,
    include_retry_hint: bool = False,
    retry_action_label: str = "",
    pending_count: int = 0,
) -> tuple[ConnectionState, str]:
    """Возвращает состояние и detail footer для ошибок по единой политике."""

    if not connection_ready:
        return ConnectionState.OFFLINE, format_offline_footer_detail(reason=str(exc))

    if include_retry_hint:
        return (
            ConnectionState.DEGRADED,
            format_retry_footer_error(
                exc,
                action_label=retry_action_label,
                pending_count=pending_count,
            ),
        )

    return ConnectionState.DEGRADED, format_footer_error(exc, prefix=degraded_prefix)


def build_retry_skipped_status(*, connection_ready: bool) -> tuple[ConnectionState, str]:
    """Возвращает статус для случая, когда в очереди нет операций для retry."""

    if connection_ready:
        return ConnectionState.CONNECTED, "Retry skipped: no failed operation"
    return (
        ConnectionState.OFFLINE,
        format_offline_footer_detail(reason="Retry skipped: no failed operation"),
    )


def build_retry_started_status(
    *,
    connection_ready: bool,
    label: str,
    remaining_count: int,
) -> tuple[ConnectionState, str]:
    """Возвращает статус для запуска retry с учетом доступности соединения."""

    detail = f"Retrying failed operation: {label} ({remaining_count} remaining)"
    if connection_ready:
        return ConnectionState.CONNECTED, detail
    return ConnectionState.RECONNECTING, detail


class ACPClientApp(App[None]):
    """Главное TUI приложение с базовой ACP интеграцией."""

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+r", "retry_prompt", "Retry Prompt"),
        ("ctrl+b", "focus_sidebar", "Focus Sessions"),
        ("ctrl+s", "focus_session_list", "Focus Sessions"),
        ("ctrl+j", "next_session", "Next Session"),
        ("ctrl+k", "previous_session", "Prev Session"),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+h", "open_help", "Help"),
        ("tab", "cycle_focus", "Cycle Focus"),
        ("ctrl+c", "cancel_prompt", "Cancel"),
    ]

    CSS_PATH = str(Path(__file__).with_name("styles") / "app.tcss")

    def __init__(self, *, host: str, port: int) -> None:
        """Инициализирует UI и менеджеры состояния приложения."""

        super().__init__()
        self._app_logger = structlog.get_logger("acp_client.tui.app")
        self._connection = ACPConnectionManager(
            host=host,
            port=port,
            on_reconnect_attempt=self._on_reconnect_attempt,
            on_reconnect_recovered=self._on_reconnect_recovered,
        )
        self._sessions = SessionManager(self._connection)
        self._updates = UpdateMessageHandler(
            on_agent_chunk=self._on_agent_chunk,
            on_user_chunk=self._on_user_chunk,
            on_tool_update=self._on_tool_update,
        )
        self._failed_operations: list[FailedOperation] = []
        self._focus_order: tuple[type[Sidebar] | type[PromptInput], ...] = (Sidebar, PromptInput)
        self._focus_index: int = 1
        self._ui_state_store = UIStateStore()
        self._loaded_ui_state = self._ui_state_store.load()

    def compose(self) -> ComposeResult:
        """Собирает базовый layout приложения."""

        yield HeaderBar()
        with Horizontal(id="body"):
            yield Sidebar()
            yield ChatView()
            yield ToolPanel()
        with Vertical(id="bottom"):
            yield PromptInput()
            yield FooterBar()

    def on_mount(self) -> None:
        """Запускает начальную инициализацию после старта приложения."""

        self.run_worker(self._bootstrap(), exclusive=True)

    async def on_unmount(self) -> None:
        """Закрывает persistent WS-соединение при завершении приложения."""

        self._persist_ui_state()
        await self._connection.close()

    async def _bootstrap(self) -> None:
        """Инициализирует соединение и обеспечивает активную сессию."""

        chat = self.query_one(ChatView)
        sidebar = self.query_one(Sidebar)
        tools = self.query_one(ToolPanel)
        try:
            self._set_connection_state(
                ConnectionState.RECONNECTING,
                detail="Starting bootstrap",
            )
            await self._connection.initialize()
            await self._sessions.refresh_sessions()
            restored = await self._restore_active_session_from_snapshot()
            if not restored:
                await self._sessions.ensure_active_session()
            prompt_input = self.query_one(PromptInput)
            prompt_input.set_active_session(self._sessions.active_session_id)
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            tools.reset()
            chat.clear_messages()
            self._render_replay_updates(self._sessions.last_replay_updates)
            if (
                self._loaded_ui_state.draft_prompt_text
                and self._loaded_ui_state.draft_session_id == self._sessions.active_session_id
            ):
                prompt_input.text = self._loaded_ui_state.draft_prompt_text
                chat.add_system_message("Восстановлен черновик prompt")
            prompt_input.focus()
            self._focus_index = 1
            self._set_connection_state(ConnectionState.CONNECTED, detail=READY_FOOTER_DETAIL)
            chat.add_system_message("TUI ready")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_bootstrap_failed", error=str(exc))
            self._set_connection_state(
                ConnectionState.OFFLINE,
                detail=format_offline_footer_detail(
                    reason=format_footer_error(exc, prefix="Connection error")
                ),
            )
            chat.add_system_message(f"Ошибка подключения: {exc}")

    async def on_prompt_input_submitted(self, message: PromptInput.Submitted) -> None:
        """Отправляет введенный prompt и запускает обработку update-потока."""

        prompt_input = self.query_one(PromptInput)
        chat = self.query_one(ChatView)

        # При критическом disconnect блокируем отправку и оставляем черновик в поле.
        if not self._connection.is_ready():
            self._set_connection_state(
                ConnectionState.OFFLINE,
                detail=format_offline_footer_detail(
                    reason="Prompt blocked: connection unavailable"
                ),
            )
            chat.add_system_message("Отправка prompt отложена: нет подключения к серверу")
            self._remember_failed_operation(
                label="prompt",
                action=lambda: self._send_prompt(message.text),
            )
            return

        chat.add_user_message(message.text)
        prompt_input.remember_prompt(message.text)
        prompt_input.text = ""
        self._persist_ui_state()
        self._set_connection_state(ConnectionState.CONNECTED, detail="Sending prompt...")
        self.run_worker(self._send_prompt(message.text), exclusive=True)

    async def _send_prompt(self, text: str) -> None:
        """Выполняет session/prompt и завершает streaming состояние."""

        chat = self.query_one(ChatView)
        try:
            await self._sessions.send_prompt(
                text,
                self._updates.handle,
                self._on_permission_request,
            )
            chat.finish_agent_message()
            self._clear_failed_operations()
            self._persist_ui_state()
            self._set_connection_state(ConnectionState.CONNECTED, detail=READY_FOOTER_DETAIL)
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_prompt_failed", error=str(exc))
            error_state, error_detail = build_error_state_status(
                exc,
                connection_ready=self._connection.is_ready(),
                degraded_prefix="Error",
                include_retry_hint=True,
                retry_action_label="prompt",
                pending_count=len(self._failed_operations),
            )
            self._set_connection_state(error_state, detail=error_detail)
            chat.finish_agent_message()
            chat.add_system_message(f"Ошибка отправки prompt: {exc}")
            self._remember_failed_operation(
                label="prompt",
                action=lambda: self._send_prompt(text),
            )

    async def action_new_session(self) -> None:
        """Создает новую сессию и обновляет sidebar состояние."""

        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
        tools = self.query_one(ToolPanel)
        try:
            new_session_id = await self._sessions.create_and_activate_session(str(Path.cwd()))
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            self.query_one(PromptInput).set_active_session(self._sessions.active_session_id)
            self.query_one(PromptInput).text = ""
            tools.reset()
            chat.clear_messages()
            self._clear_failed_operations()
            self._persist_ui_state()
            self._set_connection_state(
                ConnectionState.CONNECTED,
                detail=f"New session created: {new_session_id}",
            )
            chat.add_system_message(f"Создана новая сессия: {new_session_id}")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_new_session_failed", error=str(exc))
            error_state, error_detail = build_error_state_status(
                exc,
                connection_ready=self._connection.is_ready(),
                degraded_prefix="Error creating session",
            )
            self._set_connection_state(error_state, detail=error_detail)
            self._remember_failed_operation(label="new_session", action=self.action_new_session)

    async def action_next_session(self) -> None:
        """Переключает активную сессию на следующую и обновляет sidebar."""

        await self._switch_session(direction="next")

    async def action_previous_session(self) -> None:
        """Переключает активную сессию на предыдущую и обновляет sidebar."""

        await self._switch_session(direction="previous")

    def action_focus_sidebar(self) -> None:
        """Переводит фокус в sidebar для выбора сессии по Enter."""

        self.query_one(Sidebar).focus()
        self._focus_index = 0

    def action_focus_session_list(self) -> None:
        """Алиас для быстрого перехода к списку сессий по Ctrl+S."""

        self.action_focus_sidebar()

    def action_cycle_focus(self) -> None:
        """Переключает фокус между sidebar и prompt input по Tab."""

        self._focus_index = (self._focus_index + 1) % len(self._focus_order)
        self.query_one(self._focus_order[self._focus_index]).focus()

    def action_open_help(self) -> None:
        """Показывает краткую справку по горячим клавишам в чате и footer."""

        self.query_one(ChatView).add_system_message(
            "Горячие клавиши: Ctrl+S/B сессии, Tab фокус, Ctrl+N новая сессия, "
            "Ctrl+J/K переключение, Ctrl+L очистить чат, Ctrl+R retry, Ctrl+C cancel, Ctrl+Q выход"
        )
        self._set_connection_state(ConnectionState.CONNECTED, detail=HELP_FOOTER_DETAIL)

    def action_clear_chat(self) -> None:
        """Очищает историю чата текущей сессии и сообщает об этом в footer."""

        self.query_one(ChatView).clear_messages()
        self._set_connection_state(ConnectionState.CONNECTED, detail="Chat cleared")

    async def action_cancel_prompt(self) -> None:
        """Отправляет session/cancel для текущей сессии."""

        chat = self.query_one(ChatView)
        try:
            await self._sessions.cancel()
            chat.finish_agent_message()
            if self._connection.is_ready():
                self._set_connection_state(ConnectionState.CONNECTED, detail="Cancel requested")
            else:
                self._set_connection_state(
                    ConnectionState.RECONNECTING,
                    detail="Cancel requested during reconnect",
                )
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_cancel_prompt_failed", error=str(exc))
            error_state, error_detail = build_error_state_status(
                exc,
                connection_ready=self._connection.is_ready(),
                degraded_prefix="Error cancelling prompt",
            )
            self._set_connection_state(error_state, detail=error_detail)
            chat.add_system_message(f"Ошибка отмены prompt: {exc}")
            self._remember_failed_operation(label="cancel_prompt", action=self.action_cancel_prompt)

    def action_retry_prompt(self) -> None:
        """Повторяет последнюю неуспешную операцию по Ctrl+R."""

        failed_operation = self._pop_failed_operation()
        if failed_operation is None:
            state, detail = build_retry_skipped_status(
                connection_ready=self._connection.is_ready(),
            )
            self._set_connection_state(state, detail=detail)
            return
        state, detail = build_retry_started_status(
            connection_ready=self._connection.is_ready(),
            label=failed_operation.label,
            remaining_count=len(self._failed_operations),
        )
        self._set_connection_state(state, detail=detail)
        self.run_worker(failed_operation.action(), exclusive=True)

    def _on_agent_chunk(self, text: str) -> None:
        """Получает agent chunk и рендерит его в ChatView."""

        self.query_one(ChatView).append_agent_chunk(text)

    def _on_user_chunk(self, text: str) -> None:
        """Получает user chunk из replay/update и добавляет в ChatView."""

        self.query_one(ChatView).add_user_message(text)

    def _on_tool_update(self, update: ToolCallUpdate) -> None:
        """Получает update вызова инструмента и обновляет правую панель."""

        self.query_one(ToolPanel).apply_update(update)

    async def _switch_session(self, *, direction: str) -> None:
        """Переключает активную сессию по направлению и отражает это в UI."""

        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
        tools = self.query_one(ToolPanel)
        try:
            await self._sessions.refresh_sessions()
            if direction == "next":
                switched = await self._sessions.activate_next_session()
            else:
                switched = await self._sessions.activate_previous_session()
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            if switched is None:
                self._set_connection_state(ConnectionState.CONNECTED, detail="No sessions")
                return
            tools.reset()
            chat.clear_messages()
            self._render_replay_updates(self._sessions.last_replay_updates)
            self.query_one(PromptInput).set_active_session(self._sessions.active_session_id)
            self.query_one(PromptInput).text = ""
            self._set_connection_state(
                ConnectionState.CONNECTED,
                detail=f"Active session: {switched}",
            )
            chat.add_system_message(f"Активная сессия: {switched}")
            self._clear_failed_operations()
            self._persist_ui_state()
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_switch_session_failed", error=str(exc))
            error_state, error_detail = build_error_state_status(
                exc,
                connection_ready=self._connection.is_ready(),
                degraded_prefix="Error switching session",
            )
            self._set_connection_state(error_state, detail=error_detail)
            self._remember_failed_operation(
                label=f"switch_session_{direction}",
                action=lambda: self._switch_session(direction=direction),
            )

    async def on_sidebar_session_selected(self, message: Sidebar.SessionSelected) -> None:
        """Активирует сессию, выбранную в sidebar через Enter."""

        await self._activate_session_by_id(message.session_id)

    async def _activate_session_by_id(self, session_id: str) -> None:
        """Активирует указанную сессию и синхронизирует все панели интерфейса."""

        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
        tools = self.query_one(ToolPanel)
        try:
            await self._sessions.activate_session(session_id)
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            self.query_one(PromptInput).set_active_session(self._sessions.active_session_id)
            self.query_one(PromptInput).focus()
            self.query_one(PromptInput).text = ""
            tools.reset()
            chat.clear_messages()
            self._render_replay_updates(self._sessions.last_replay_updates)
            self._set_connection_state(
                ConnectionState.CONNECTED,
                detail=f"Active session: {session_id}",
            )
            chat.add_system_message(f"Выбрана сессия: {session_id}")
            self._clear_failed_operations()
            self._persist_ui_state()
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_sidebar_select_failed", error=str(exc))
            error_state, error_detail = build_error_state_status(
                exc,
                connection_ready=self._connection.is_ready(),
                degraded_prefix="Error selecting session",
            )
            self._set_connection_state(error_state, detail=error_detail)
            self._remember_failed_operation(
                label="select_session",
                action=lambda: self._activate_session_by_id(session_id),
            )

    def _on_reconnect_attempt(self, method: str) -> None:
        """Отмечает состояние reconnect в UI при автоматическом retry."""

        self._set_connection_state(ConnectionState.RECONNECTING, detail=f"retry method={method}")

    def _on_reconnect_recovered(self, method: str) -> None:
        """Возвращает статус connected после успешного retry-запроса."""

        self._set_connection_state(
            ConnectionState.CONNECTED,
            detail=f"Recovered after retry: {method}",
        )

    def _set_connection_state(self, state: ConnectionState, *, detail: str) -> None:
        """Синхронно обновляет Header и Footer на основе единого connection-state."""

        self.query_one(HeaderBar).set_status(state.value)
        self.query_one(FooterBar).set_status(format_footer_status(state=state, detail=detail))

    def _remember_failed_operation(
        self,
        *,
        label: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        """Сохраняет неуспешную операцию в очередь повторных запусков."""

        self._failed_operations = [item for item in self._failed_operations if item.label != label]
        self._failed_operations.append(FailedOperation(label=label, action=action))
        if len(self._failed_operations) > 5:
            self._failed_operations.pop(0)

    def _pop_failed_operation(self) -> FailedOperation | None:
        """Возвращает последнюю неуспешную операцию для повторного запуска."""

        if not self._failed_operations:
            return None
        return self._failed_operations.pop()

    def _clear_failed_operations(self) -> None:
        """Очищает накопленные неуспешные операции после успешного выполнения."""

        self._failed_operations = []

    async def _restore_active_session_from_snapshot(self) -> bool:
        """Восстанавливает активную сессию из сохраненного snapshot, если возможно."""

        session_id = self._loaded_ui_state.last_active_session_id
        if not isinstance(session_id, str) or not session_id:
            return False
        for session in self._sessions.sessions:
            if session.sessionId == session_id:
                await self._sessions.activate_session(session_id)
                return True
        return False

    def _persist_ui_state(self) -> None:
        """Сохраняет активную сессию и текущий черновик prompt в локальный store."""

        draft_text = ""
        try:
            draft_text = self.query_one(PromptInput).text
        except Exception:
            draft_text = ""

        self._ui_state_store.save(
            snapshot=TUIStateSnapshot(
                last_active_session_id=self._sessions.active_session_id,
                draft_prompt_text=draft_text,
                draft_session_id=self._sessions.active_session_id,
            )
        )

    def _render_replay_updates(self, updates: list[SessionUpdateNotification]) -> None:
        """Отрисовывает replay updates сообщений и tool-call статусов."""

        for update in updates:
            tool_update = parse_tool_call_update(update)
            if tool_update is not None:
                self.query_one(ToolPanel).apply_update(tool_update)

            payload = update.params.update.model_dump()
            session_update_type = payload.get("sessionUpdate")
            content = payload.get("content")
            if not isinstance(content, dict):
                continue
            if content.get("type") != "text":
                continue
            text = content.get("text")
            if not isinstance(text, str):
                continue
            if session_update_type == "agent_message_chunk":
                self.query_one(ChatView).append_agent_chunk(text)
                continue
            if session_update_type == "user_message_chunk":
                self.query_one(ChatView).add_user_message(text)

        self.query_one(ChatView).finish_agent_message()

    async def _on_permission_request(self, payload: dict[str, object]) -> str | None:
        """Показывает модальное окно и возвращает выбранный optionId."""

        chat = self.query_one(ChatView)
        parsed_request = parse_request_permission_request(payload)
        if parsed_request is None:
            self._set_connection_state(
                ConnectionState.DEGRADED,
                detail="Permission request parse error",
            )
            return None

        tool_name = (
            parsed_request.params.toolCall.title or parsed_request.params.toolCall.toolCallId
        )
        chat.add_system_message(f"Запрошено разрешение: {tool_name}")
        self._set_connection_state(
            ConnectionState.CONNECTED,
            detail="Waiting permission decision",
        )
        selected_option_id = await self.push_screen_wait(
            self._build_permission_modal(parsed_request)
        )

        if selected_option_id is None:
            self._set_connection_state(ConnectionState.CONNECTED, detail="Permission cancelled")
            chat.add_system_message("Разрешение отклонено или отменено")
            return None

        self._set_connection_state(
            ConnectionState.CONNECTED,
            detail=f"Permission selected: {selected_option_id}",
        )
        chat.add_system_message(f"Выбрано разрешение: {selected_option_id}")
        return selected_option_id

    def _build_permission_modal(self, request: RequestPermissionRequest) -> PermissionModal:
        """Создает модальное окно выбора permission-опции."""

        tool_title = request.params.toolCall.title or request.params.toolCall.toolCallId
        title = f"Разрешить действие: {tool_title}"
        return PermissionModal(title=title, options=request.params.options)


def run_tui_app(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Запускает TUI приложение с указанными параметрами подключения."""

    app = ACPClientApp(host=host, port=port)
    app.run()


def format_footer_error(exc: Exception, *, prefix: str) -> str:
    """Формирует краткий текст ошибки для footer c кодом и сообщением."""

    message = str(exc).strip().replace("\n", " ")
    compact = re.sub(r"\s+", " ", message)

    # Для JSON-RPC ошибок выделяем код и основной текст в коротком формате.
    matched = re.search(r"(?P<code>-?\d+)\s+(?P<reason>.+)", compact)
    if matched is not None:
        code = matched.group("code")
        reason = matched.group("reason")
        return f"{prefix} | code={code} | {reason[:72]}"

    if not compact:
        return f"{prefix} | unknown error"
    return f"{prefix} | {compact[:96]}"


def format_retry_footer_error(
    exc: Exception,
    *,
    action_label: str,
    pending_count: int,
) -> str:
    """Формирует статус ошибки с подсказкой на повтор операции."""

    return (
        f"{format_footer_error(exc, prefix='Error')}"
        f" | Ctrl+R retry {action_label} | queued={pending_count}"
    )


@dataclass(slots=True)
class FailedOperation:
    """Описывает неуспешную операцию, которую можно повторить по Ctrl+R."""

    label: str
    action: Callable[[], Awaitable[None]]
