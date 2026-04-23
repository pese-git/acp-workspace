"""Главное Textual приложение ACP-Client TUI с Clean Architecture.

Приложение использует новую архитектуру:
- DIBootstrapper для инициализации контейнера зависимостей
- ViewModels для управления состоянием UI
- Use Cases для бизнес-логики
- Event Bus для слабо связанной коммуникации между компонентами
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from pathlib import Path

import structlog
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical

from codelab.client.infrastructure.di_bootstrapper import DIBootstrapper
from codelab.client.presentation.chat_view_model import ChatViewModel
from codelab.client.presentation.file_viewer_view_model import FileViewerViewModel
from codelab.client.presentation.filesystem_view_model import FileSystemViewModel
from codelab.client.presentation.permission_view_model import PermissionViewModel
from codelab.client.presentation.plan_view_model import PlanViewModel
from codelab.client.presentation.session_view_model import SessionViewModel
from codelab.client.presentation.terminal_log_view_model import TerminalLogViewModel
from codelab.client.presentation.terminal_view_model import TerminalViewModel
from codelab.client.presentation.ui_view_model import ConnectionStatus, SidebarTab, UIViewModel
from codelab.client.tui.navigation import NavigationManager
from codelab.shared.messages import PermissionOption, PermissionToolCall

from .components import (
    ChatView,
    FileTree,
    FooterBar,
    HeaderBar,
    HelpModal,
    PermissionModal,
    PlanPanel,
    PromptInput,
    Sidebar,
    ToolPanel,
)
from .config import TUIConfigStore, resolve_tui_connection


class ACPClientApp(App[None]):
    """Главное TUI приложение с Clean Architecture.

    Все компоненты инициализируются через DIBootstrapper.
    State management осуществляется через ViewModels.
    """

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
        ("?", "show_hotkeys", "Hotkeys"),
        ("ctrl+tab", "next_sidebar_tab", "Next Sidebar Tab"),
        ("ctrl+shift+tab", "previous_sidebar_tab", "Prev Sidebar Tab"),
        ("ctrl+t", "open_terminal_output", "Terminal Output"),
        ("tab", "cycle_focus", "Cycle Focus"),
        ("ctrl+c", "cancel_prompt", "Cancel"),
    ]

    CSS_PATH = str(Path(__file__).with_name("styles") / "app.tcss")

    def __init__(
        self,
        *,
        host: str,
        port: int,
        cwd: str | None = None,
        history_dir: str | None = None,
    ) -> None:
        """Инициализирует приложение с Clean Architecture.

        Все компоненты инициализируются через DI контейнер.

        Args:
            host: Адрес сервера ACP
            port: Порт сервера ACP
            cwd: Путь к проекту (если None, используется текущая рабочая директория)
            history_dir: Путь к директории локальной истории чата (опционально)
        """
        super().__init__()
        self._host = host
        self._port = port
        # Если cwd не передан, используем текущую директорию
        # Преобразуем в абсолютный путь и проверяем существование
        cwd = os.getcwd() if cwd is None else os.path.abspath(os.path.expanduser(cwd))

        # Проверяем что директория существует
        if not os.path.exists(cwd) or not os.path.isdir(cwd):
            raise ValueError(f"Путь {cwd} не является доступной директорией")

        self._cwd = cwd
        self._config_store = TUIConfigStore()
        self._app_logger = structlog.get_logger("acp_client.tui.app")

        # NavigationManager будет инициализирован в on_mount
        self._navigation_manager: NavigationManager | None = None

        # Блокировка предотвращает параллельные `session/load`, которые могут
        # перемешивать `session/update` между конкурентными запросами.
        self._session_history_load_lock = asyncio.Lock()

        # Инициализируем DIContainer
        try:
            self._container = DIBootstrapper.build(
                host=host,
                port=port,
                cwd=cwd,
                history_dir=history_dir,
                logger=self._app_logger,
            )
            self._app_logger.info("di_container_built_successfully", cwd=cwd)
        except Exception as e:
            self._app_logger.error(
                "failed_to_build_di_container",
                error=str(e),
            )
            raise RuntimeError(f"Failed to initialize DI container: {e}") from e

        # Разрешаем все ViewModels
        try:
            self._ui_vm = self._container.resolve(UIViewModel)
            self._session_vm = self._container.resolve(SessionViewModel)
            self._chat_vm = self._container.resolve(ChatViewModel)
            self._plan_vm = self._container.resolve(PlanViewModel)
            self._filesystem_vm = self._container.resolve(FileSystemViewModel)
            self._terminal_log_vm = self._container.resolve(TerminalLogViewModel)
            self._file_viewer_vm = self._container.resolve(FileViewerViewModel)
            self._permission_vm = self._container.resolve(PermissionViewModel)
            self._terminal_vm = self._container.resolve(TerminalViewModel)

            self._app_logger.info("all_view_models_resolved")

            # Синхронизируем ChatViewModel с выбранной сессией.
            self._session_vm.selected_session_id.subscribe(self._on_selected_session_changed)
            self._chat_vm.set_active_session(self._session_vm.selected_session_id.value)

            # Синхронизируем layout левой колонки с глобальным UI состоянием.
            self._ui_vm.sidebar_tab.subscribe(self._on_sidebar_state_changed)
            self._ui_vm.files_expanded.subscribe(self._on_sidebar_state_changed)
        except Exception as e:
            self._app_logger.error(
                "failed_to_resolve_view_models",
                error=str(e),
            )
            raise RuntimeError(f"Failed to initialize ViewModels: {e}") from e

    def compose(self) -> ComposeResult:
        """Собирает базовый layout приложения."""
        yield HeaderBar(self._ui_vm)
        with Horizontal(id="body"):
            with Vertical(id="sidebar-column"):
                yield Sidebar(self._session_vm, self._ui_vm)
                # Передаем cwd в FileTree для отображения структуры проекта
                yield FileTree(
                    filesystem_vm=self._filesystem_vm,
                    root_path=self._cwd,
                )
            with Vertical(id="main-column"):
                # Передаем permission_vm в ChatView для встроенного виджета разрешения
                self._chat_view = ChatView(self._chat_vm, self._permission_vm)
                yield self._chat_view
                yield PlanPanel(self._plan_vm)
            yield ToolPanel(self._chat_vm, self._terminal_vm)
        with Vertical(id="bottom"):
            yield PromptInput(self._chat_vm)
            yield FooterBar(self._ui_vm)

    def on_ready(self) -> None:
        """Запускается когда приложение готово к работе."""
        self._app_logger.info("app_ready")

        # Инициализируем NavigationManager
        try:
            self._navigation_manager = NavigationManager(self)
            self._app_logger.debug("navigation_manager_initialized")
        except Exception as e:
            self._app_logger.error(
                "failed_to_initialize_navigation_manager",
                error=str(e),
            )

        # Инициализируем подключение к серверу
        self._app_logger.info("starting_connection_worker")
        self.run_worker(self._initialize_connection(), exclusive=False)
        self._on_sidebar_state_changed(None)

    async def _initialize_connection(self) -> None:
        """Инициализирует подключение к серверу."""
        self._app_logger.info("connection_worker_started")
        self._ui_vm.set_connection_status(ConnectionStatus.CONNECTING)
        self._ui_vm.set_loading(True, "connecting to server")
        try:
            from codelab.client.application.session_coordinator import SessionCoordinator

            # Получаем SessionCoordinator из DI контейнера
            self._app_logger.debug("resolving_session_coordinator")
            coordinator = self._container.resolve(SessionCoordinator)

            # Инициализируем подключение
            self._app_logger.info("initializing_server_connection")
            server_info = await coordinator.initialize()

            self._app_logger.info(
                "server_connection_initialized",
                protocol_version=server_info.get("protocol_version"),
                auth_methods=len(server_info.get("available_auth_methods", [])),
            )

            # Обновляем статус подключения в UI
            self._ui_vm.set_connection_status(ConnectionStatus.CONNECTED)
            self._ui_vm.set_loading(False)

            # Устанавливаем callback для показа permission modal в UI.
            # Это необходимо, чтобы при получении session/request_permission от сервера
            # TUI приложение показало модальное окно для выбора разрешения.
            try:
                from codelab.client.infrastructure.services.acp_transport_service import (
                    ACPTransportService,
                )

                transport = self._container.resolve(ACPTransportService)
                transport.set_permission_callback(self.show_permission_modal)
                self._app_logger.info("permission_callback_registered_in_transport")
            except Exception as e:
                self._app_logger.warning(
                    "failed_to_set_permission_callback",
                    error=str(e),
                )

            # После успешного подключения запрашиваем список сессий с сервера,
            # чтобы sidebar отображал сохраненные сессии сразу при старте.
            await self._session_vm.load_sessions_cmd.execute()
            loaded_count = self._session_vm.session_count.value
            self._app_logger.info(
                "sessions_loaded_on_startup",
                count=loaded_count,
                host=self._host,
                port=self._port,
            )
            if loaded_count == 0:
                # Явный warning помогает сразу понять, что сервер вернул пустой session/list.
                self._app_logger.warning(
                    "session_list_is_empty_on_startup",
                    hint="Проверьте, что сервер запущен с persistent --storage json:<path>",
                )

        except Exception as e:
            self._app_logger.error(
                "failed_to_initialize_connection",
                error=str(e),
                exc_info=True,
            )
            # Обновляем статус подключения в UI
            self._ui_vm.set_connection_status(ConnectionStatus.DISCONNECTED)
            self._ui_vm.set_loading(False)

    def _on_sidebar_state_changed(self, _: object) -> None:
        """Синхронизировать видимость FileTree с активной вкладкой sidebar."""

        try:
            file_tree = self.query_one(FileTree)
        except Exception:
            return

        is_files_tab = self._ui_vm.sidebar_tab.value == SidebarTab.FILES
        should_show = is_files_tab and self._ui_vm.files_expanded.value
        file_tree.display = should_show

    def action_next_sidebar_tab(self) -> None:
        """Переключить вкладку sidebar вперед по кругу."""

        self._ui_vm.cycle_sidebar_tab()

    def action_previous_sidebar_tab(self) -> None:
        """Переключить вкладку sidebar назад по кругу."""

        self._ui_vm.cycle_sidebar_tab(reverse=True)

    def action_new_session(self) -> None:
        """Создает новую сессию по горячей клавише Ctrl+N."""
        self._app_logger.info("new_session_requested", cwd=self._cwd)
        # Передаем cwd при создании новой сессии для инициализации рабочей директории
        self.run_worker(
            self._session_vm.create_session_cmd.execute(
                self._host,
                self._port,
                cwd=self._cwd,
            ),
            exclusive=False,
        )

    def action_focus_sidebar(self) -> None:
        """Переводит фокус в список сессий."""

        sidebar = self.query_one(Sidebar)
        sidebar.focus()

    def action_focus_session_list(self) -> None:
        """Алиас для перевода фокуса в список сессий."""

        self.action_focus_sidebar()

    def action_open_help(self) -> None:
        """Открыть контекстную справку по текущему фокусу."""

        focused = self.focused
        context = "global"
        if isinstance(focused, Sidebar):
            context = "sidebar"
        elif isinstance(focused, FileTree):
            context = "file-tree"
        elif isinstance(focused, PromptInput):
            context = "prompt-input"
        self.push_screen(HelpModal(context=context, show_hotkeys=False))

    def action_show_hotkeys(self) -> None:
        """Показать отдельный экран со списком горячих клавиш."""

        self.push_screen(HelpModal(context="global", show_hotkeys=True))

    def action_next_session(self) -> None:
        """Выбирает следующую сессию в sidebar и применяет выбор."""

        sidebar = self.query_one(Sidebar)
        sidebar.select_next()
        selected_session_id = sidebar.get_selected_session_id()
        if selected_session_id is None:
            return
        self.run_worker(
            self._session_vm.switch_session_cmd.execute(selected_session_id),
            exclusive=False,
        )

    def action_previous_session(self) -> None:
        """Выбирает предыдущую сессию в sidebar и применяет выбор."""

        sidebar = self.query_one(Sidebar)
        sidebar.select_previous()
        selected_session_id = sidebar.get_selected_session_id()
        if selected_session_id is None:
            return
        self.run_worker(
            self._session_vm.switch_session_cmd.execute(selected_session_id),
            exclusive=False,
        )

    def on_sidebar_session_selected(self, event: Sidebar.SessionSelected) -> None:
        """Применяет выбор сессии по Enter в sidebar."""

        self.run_worker(
            self._session_vm.switch_session_cmd.execute(event.session_id),
            exclusive=False,
        )

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        """Обработать отправку промпта пользователем.

        Args:
            event: Событие с текстом промпта
        """
        # Получаем ID активной сессии
        session_id = self._session_vm.selected_session_id.value

        if not session_id:
            self._app_logger.warning("prompt_submitted_without_active_session")
            # Можно показать уведомление пользователю
            return

        self._app_logger.info(
            "prompt_submitted",
            session_id=session_id,
            prompt_length=len(event.text),
        )

        # Добавляем сообщение пользователя в чат
        self._chat_vm.add_message("user", event.text, session_id=session_id)

        # Запускаем отправку промпта асинхронно
        self.run_worker(
            self._chat_vm.send_prompt_cmd.execute(session_id, event.text),
            exclusive=False,
        )

    def _on_selected_session_changed(self, session_id: str | None) -> None:
        """Обновляет ChatView при смене активной сессии."""

        self._chat_vm.set_active_session(session_id)
        if session_id is None:
            return

        # При выборе сессии сразу запрашиваем `session/load`, чтобы UI получил
        # историю из серверного persistence даже при пустом локальном кэше.
        self.run_worker(
            self._load_selected_session_history(session_id),
            exclusive=False,
        )

    async def _load_selected_session_history(self, session_id: str) -> None:
        """Загружает историю выбранной сессии через `session/load`."""

        async with self._session_history_load_lock:
            try:
                from codelab.client.application.session_coordinator import SessionCoordinator

                coordinator = self._container.resolve(SessionCoordinator)
                loaded = await coordinator.load_session(
                    session_id,
                    self._host,
                    self._port,
                    cwd=self._cwd,
                    mcp_servers=[],
                )
                replay_updates = loaded.get("replay_updates", [])
                if isinstance(replay_updates, list):
                    self._chat_vm.restore_session_from_replay(session_id, replay_updates)

                self._app_logger.info(
                    "session_history_loaded",
                    session_id=session_id,
                    replay_updates_count=(
                        len(replay_updates) if isinstance(replay_updates, list) else 0
                    ),
                )
            except Exception as error:
                self._app_logger.warning(
                    "session_history_load_failed",
                    session_id=session_id,
                    error=str(error),
                )

    def show_permission_modal(
        self,
        request_id: str | int,
        tool_call: PermissionToolCall,
        options: list[PermissionOption],
        on_choice: Callable[[str | int, str], None],
    ) -> None:
        """Показывает встроенный виджет разрешения в ChatView.

        Заменяет модальное окно на встроенный виджет для лучшей видимости.
        Интегрирует InlinePermissionWidget с SessionCoordinator через callback pattern.

        Args:
            request_id: ID permission request от сервера
            tool_call: Информация о tool call (kind, title, toolCallId)
            options: Доступные опции для выбора (allow_once, reject_once, и т.д.)
            on_choice: Callback для обработки выбора (request_id, option_id)
        """
        self._app_logger.debug(
            "show_permission_modal_called",
            request_id=request_id,
            tool_call_kind=tool_call.kind,
            tool_call_title=tool_call.title,
            options_count=len(options),
        )

        try:
            # Показать встроенный виджет в ChatView
            if hasattr(self, "_chat_view") and self._chat_view is not None:
                self._app_logger.debug(
                    "showing_inline_permission_widget",
                    request_id=request_id,
                    tool_call_kind=tool_call.kind,
                    tool_call_title=tool_call.title,
                    options_count=len(options),
                )
                self._chat_view.show_permission_request(
                    request_id, tool_call, options, on_choice
                )
            else:
                self._app_logger.warning(
                    "chat_view_not_available_for_permission_widget",
                    request_id=request_id,
                    fallback="showing_modal_instead",
                )
                # Fallback на модальное окно если ChatView недоступна
                title = f"{tool_call.kind}: {tool_call.title}"
                modal = PermissionModal(
                    permission_vm=self._permission_vm,
                    request_id=request_id,
                    title=title,
                    options=options,
                    on_choice=on_choice,
                )
                self.push_screen(modal)

        except Exception as e:
            self._app_logger.error(
                "failed_to_show_permission_widget",
                request_id=request_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Fallback: вызвать on_choice с cancelled при ошибке
            try:
                on_choice(request_id, "cancelled")
            except Exception as fallback_error:
                self._app_logger.error(
                    "failed_to_call_on_choice_callback",
                    request_id=request_id,
                    error=str(fallback_error),
                )

    async def on_unmount(self) -> None:
        """Очистка ресурсов при завершении приложения."""
        self._app_logger.info("app_unmounting")

        # Закрываем WebSocket соединение
        try:
            from codelab.client.infrastructure.services.acp_transport_service import (
                ACPTransportService,
            )

            transport_service = self._container.resolve(ACPTransportService)
            await transport_service.disconnect()
            self._app_logger.info("websocket_disconnected")
        except Exception as e:
            self._app_logger.error("websocket_disconnect_failed", error=str(e))

        # Dispose DI контейнера
        try:
            self._container.dispose()
            self._app_logger.info("di_container_disposed")
        except Exception as e:
            self._app_logger.error("di_container_dispose_failed", error=str(e))

        self._app_logger.info("app_unmounted")


def run_tui_app(
    *,
    host: str | None = None,
    port: int | None = None,
    cwd: str | None = None,
    history_dir: str | None = None,
) -> None:
    """Запускает TUI приложение с параметрами подключения и рабочей директории.

    Args:
        host: Адрес сервера ACP (если None, используется значение по умолчанию)
        port: Порт сервера ACP (если None, используется значение по умолчанию)
        cwd: Путь к проекту (если None, используется текущая рабочая директория)
        history_dir: Путь к директории локальной истории чата (опционально)
    """
    resolved_host, resolved_port = resolve_tui_connection(host=host, port=port)
    app = ACPClientApp(host=resolved_host, port=resolved_port, cwd=cwd, history_dir=history_dir)
    app.run()
