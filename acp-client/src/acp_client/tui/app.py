"""Главное Textual приложение ACP-Client TUI."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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


class ACPClientApp(App[None]):
    """Главное TUI приложение с базовой ACP интеграцией."""

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
        ("ctrl+r", "retry_prompt", "Retry Prompt"),
        ("ctrl+b", "focus_sidebar", "Focus Sessions"),
        ("ctrl+j", "next_session", "Next Session"),
        ("ctrl+k", "previous_session", "Prev Session"),
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

        header = self.query_one(HeaderBar)
        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)
        sidebar = self.query_one(Sidebar)
        tools = self.query_one(ToolPanel)
        try:
            header.set_status("Connected")
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
            footer.set_status(
                "Connected | Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch"
            )
            chat.add_system_message("TUI ready")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_bootstrap_failed", error=str(exc))
            header.set_status("Degraded")
            footer.set_status(format_footer_error(exc, prefix="Connection error"))
            chat.add_system_message(f"Ошибка подключения: {exc}")

    async def on_prompt_input_submitted(self, message: PromptInput.Submitted) -> None:
        """Отправляет введенный prompt и запускает обработку update-потока."""

        prompt_input = self.query_one(PromptInput)
        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)

        chat.add_user_message(message.text)
        prompt_input.remember_prompt(message.text)
        prompt_input.text = ""
        self._persist_ui_state()
        footer.set_status("Connected | Sending prompt...")
        self.run_worker(self._send_prompt(message.text), exclusive=True)

    async def _send_prompt(self, text: str) -> None:
        """Выполняет session/prompt и завершает streaming состояние."""

        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)
        try:
            await self._sessions.send_prompt(
                text,
                self._updates.handle,
                self._on_permission_request,
            )
            chat.finish_agent_message()
            self._clear_failed_operations()
            self._persist_ui_state()
            footer.set_status(
                "Connected | Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch"
            )
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_prompt_failed", error=str(exc))
            self.query_one(HeaderBar).set_status("Degraded")
            chat.finish_agent_message()
            chat.add_system_message(f"Ошибка отправки prompt: {exc}")
            self._remember_failed_operation(
                label="prompt",
                action=lambda: self._send_prompt(text),
            )
            footer.set_status(
                format_retry_footer_error(
                    exc,
                    action_label="prompt",
                    pending_count=len(self._failed_operations),
                )
            )

    async def action_new_session(self) -> None:
        """Создает новую сессию и обновляет sidebar состояние."""

        footer = self.query_one(FooterBar)
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
            footer.set_status(f"Connected | New session created: {new_session_id}")
            chat.add_system_message(f"Создана новая сессия: {new_session_id}")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_new_session_failed", error=str(exc))
            self.query_one(HeaderBar).set_status("Degraded")
            self._remember_failed_operation(label="new_session", action=self.action_new_session)
            footer.set_status(format_footer_error(exc, prefix="Connected | Error creating session"))

    async def action_next_session(self) -> None:
        """Переключает активную сессию на следующую и обновляет sidebar."""

        await self._switch_session(direction="next")

    async def action_previous_session(self) -> None:
        """Переключает активную сессию на предыдущую и обновляет sidebar."""

        await self._switch_session(direction="previous")

    def action_focus_sidebar(self) -> None:
        """Переводит фокус в sidebar для выбора сессии по Enter."""

        self.query_one(Sidebar).focus()

    async def action_cancel_prompt(self) -> None:
        """Отправляет session/cancel для текущей сессии."""

        footer = self.query_one(FooterBar)
        chat = self.query_one(ChatView)
        await self._sessions.cancel()
        chat.finish_agent_message()
        footer.set_status("Connected | Cancel requested")

    def action_retry_prompt(self) -> None:
        """Повторяет последнюю неуспешную операцию по Ctrl+R."""

        footer = self.query_one(FooterBar)
        failed_operation = self._pop_failed_operation()
        if failed_operation is None:
            footer.set_status("Connected | Retry skipped: no failed operation")
            return
        footer.set_status(
            "Connected | Retrying failed operation: "
            f"{failed_operation.label} ({len(self._failed_operations)} remaining)"
        )
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

        footer = self.query_one(FooterBar)
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
                footer.set_status("Connected | No sessions")
                return
            tools.reset()
            chat.clear_messages()
            self._render_replay_updates(self._sessions.last_replay_updates)
            self.query_one(PromptInput).set_active_session(self._sessions.active_session_id)
            self.query_one(PromptInput).text = ""
            footer.set_status(f"Connected | Active session: {switched}")
            chat.add_system_message(f"Активная сессия: {switched}")
            self._clear_failed_operations()
            self._persist_ui_state()
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_switch_session_failed", error=str(exc))
            self.query_one(HeaderBar).set_status("Degraded")
            self._remember_failed_operation(
                label=f"switch_session_{direction}",
                action=lambda: self._switch_session(direction=direction),
            )
            footer.set_status(
                format_footer_error(exc, prefix="Connected | Error switching session")
            )

    async def on_sidebar_session_selected(self, message: Sidebar.SessionSelected) -> None:
        """Активирует сессию, выбранную в sidebar через Enter."""

        await self._activate_session_by_id(message.session_id)

    async def _activate_session_by_id(self, session_id: str) -> None:
        """Активирует указанную сессию и синхронизирует все панели интерфейса."""

        footer = self.query_one(FooterBar)
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
            footer.set_status(f"Connected | Active session: {session_id}")
            chat.add_system_message(f"Выбрана сессия: {session_id}")
            self._clear_failed_operations()
            self._persist_ui_state()
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_sidebar_select_failed", error=str(exc))
            self.query_one(HeaderBar).set_status("Degraded")
            self._remember_failed_operation(
                label="select_session",
                action=lambda: self._activate_session_by_id(session_id),
            )
            footer.set_status(
                format_footer_error(exc, prefix="Connected | Error selecting session")
            )

    def _on_reconnect_attempt(self, method: str) -> None:
        """Отмечает состояние reconnect в UI при автоматическом retry."""

        self.query_one(HeaderBar).set_status("Reconnecting")
        self.query_one(FooterBar).set_status(f"Reconnecting | retry method={method}")

    def _on_reconnect_recovered(self, method: str) -> None:
        """Возвращает статус connected после успешного retry-запроса."""

        self.query_one(HeaderBar).set_status("Connected")
        self.query_one(FooterBar).set_status(f"Connected | Recovered after retry: {method}")

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

        footer = self.query_one(FooterBar)
        chat = self.query_one(ChatView)
        parsed_request = parse_request_permission_request(payload)
        if parsed_request is None:
            footer.set_status("Connected | Permission request parse error")
            return None

        tool_name = (
            parsed_request.params.toolCall.title or parsed_request.params.toolCall.toolCallId
        )
        chat.add_system_message(f"Запрошено разрешение: {tool_name}")
        footer.set_status("Connected | Waiting permission decision")
        selected_option_id = await self.push_screen_wait(
            self._build_permission_modal(parsed_request)
        )

        if selected_option_id is None:
            footer.set_status("Connected | Permission cancelled")
            chat.add_system_message("Разрешение отклонено или отменено")
            return None

        footer.set_status(f"Connected | Permission selected: {selected_option_id}")
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
        f"{format_footer_error(exc, prefix='Connected | Error')}"
        f" | Ctrl+R retry {action_label} | queued={pending_count}"
    )


@dataclass(slots=True)
class FailedOperation:
    """Описывает неуспешную операцию, которую можно повторить по Ctrl+R."""

    label: str
    action: Callable[[], Awaitable[None]]
