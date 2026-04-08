"""Главное Textual приложение ACP-Client TUI."""

from __future__ import annotations

import re
from pathlib import Path

import structlog
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical

from acp_client.messages import SessionUpdateNotification

from .components import ChatView, FooterBar, HeaderBar, PromptInput, Sidebar
from .managers import ACPConnectionManager, SessionManager, UpdateMessageHandler


class ACPClientApp(App[None]):
    """Главное TUI приложение с базовой ACP интеграцией."""

    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+n", "new_session", "New Session"),
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
        self._connection = ACPConnectionManager(host=host, port=port)
        self._sessions = SessionManager(self._connection)
        self._updates = UpdateMessageHandler(
            on_agent_chunk=self._on_agent_chunk,
            on_user_chunk=self._on_user_chunk,
        )

    def compose(self) -> ComposeResult:
        """Собирает базовый layout приложения."""

        yield HeaderBar()
        with Horizontal(id="body"):
            yield Sidebar()
            yield ChatView()
        with Vertical(id="bottom"):
            yield PromptInput()
            yield FooterBar()

    def on_mount(self) -> None:
        """Запускает начальную инициализацию после старта приложения."""

        self.run_worker(self._bootstrap(), exclusive=True)

    async def on_unmount(self) -> None:
        """Закрывает persistent WS-соединение при завершении приложения."""

        await self._connection.close()

    async def _bootstrap(self) -> None:
        """Инициализирует соединение и обеспечивает активную сессию."""

        header = self.query_one(HeaderBar)
        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)
        sidebar = self.query_one(Sidebar)
        try:
            header.set_status("Connected")
            await self._connection.initialize()
            await self._sessions.refresh_sessions()
            await self._sessions.ensure_active_session()
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            footer.set_status(
                "Connected | Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch"
            )
            chat.add_system_message("TUI ready")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_bootstrap_failed", error=str(exc))
            header.set_status("Error")
            footer.set_status(format_footer_error(exc, prefix="Connection error"))
            chat.add_system_message(f"Ошибка подключения: {exc}")

    async def on_prompt_input_submitted(self, message: PromptInput.Submitted) -> None:
        """Отправляет введенный prompt и запускает обработку update-потока."""

        prompt_input = self.query_one(PromptInput)
        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)

        chat.add_user_message(message.text)
        prompt_input.text = ""
        footer.set_status("Connected | Sending prompt...")
        self.run_worker(self._send_prompt(message.text), exclusive=True)

    async def _send_prompt(self, text: str) -> None:
        """Выполняет session/prompt и завершает streaming состояние."""

        chat = self.query_one(ChatView)
        footer = self.query_one(FooterBar)
        try:
            await self._sessions.send_prompt(text, self._updates.handle)
            chat.finish_agent_message()
            footer.set_status(
                "Connected | Ready | Ctrl+B focus sessions | Ctrl+Enter send | Ctrl+J/K switch"
            )
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_prompt_failed", error=str(exc))
            chat.finish_agent_message()
            chat.add_system_message(f"Ошибка отправки prompt: {exc}")
            footer.set_status(format_footer_error(exc, prefix="Connected | Error"))

    async def action_new_session(self) -> None:
        """Создает новую сессию и обновляет sidebar состояние."""

        footer = self.query_one(FooterBar)
        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
        try:
            new_session_id = await self._sessions.create_and_activate_session(str(Path.cwd()))
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            footer.set_status(f"Connected | New session created: {new_session_id}")
            chat.add_system_message(f"Создана новая сессия: {new_session_id}")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_new_session_failed", error=str(exc))
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

    def _on_agent_chunk(self, text: str) -> None:
        """Получает agent chunk и рендерит его в ChatView."""

        self.query_one(ChatView).append_agent_chunk(text)

    def _on_user_chunk(self, text: str) -> None:
        """Получает user chunk из replay/update и добавляет в ChatView."""

        self.query_one(ChatView).add_user_message(text)

    async def _switch_session(self, *, direction: str) -> None:
        """Переключает активную сессию по направлению и отражает это в UI."""

        footer = self.query_one(FooterBar)
        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
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
            self._render_replay_updates(self._sessions.last_replay_updates)
            footer.set_status(f"Connected | Active session: {switched}")
            chat.add_system_message(f"Активная сессия: {switched}")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_switch_session_failed", error=str(exc))
            footer.set_status(
                format_footer_error(exc, prefix="Connected | Error switching session")
            )

    async def on_sidebar_session_selected(self, message: Sidebar.SessionSelected) -> None:
        """Активирует сессию, выбранную в sidebar через Enter."""

        footer = self.query_one(FooterBar)
        sidebar = self.query_one(Sidebar)
        chat = self.query_one(ChatView)
        try:
            await self._sessions.activate_session(message.session_id)
            sidebar.set_sessions(self._sessions.sessions, self._sessions.active_session_id)
            self.query_one(PromptInput).focus()
            self._render_replay_updates(self._sessions.last_replay_updates)
            footer.set_status(f"Connected | Active session: {message.session_id}")
            chat.add_system_message(f"Выбрана сессия: {message.session_id}")
        except Exception as exc:  # pragma: no cover - safety net for runtime UX
            self._app_logger.error("tui_sidebar_select_failed", error=str(exc))
            footer.set_status(
                format_footer_error(exc, prefix="Connected | Error selecting session")
            )

    def _render_replay_updates(self, updates: list[SessionUpdateNotification]) -> None:
        """Отрисовывает текстовые replay updates после загрузки сессии."""

        for update in updates:
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
