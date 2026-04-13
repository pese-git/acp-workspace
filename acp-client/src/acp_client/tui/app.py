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
from pathlib import Path

import structlog
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical

from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
from acp_client.presentation.chat_view_model import ChatViewModel
from acp_client.presentation.file_viewer_view_model import FileViewerViewModel
from acp_client.presentation.filesystem_view_model import FileSystemViewModel
from acp_client.presentation.permission_view_model import PermissionViewModel
from acp_client.presentation.plan_view_model import PlanViewModel
from acp_client.presentation.session_view_model import SessionViewModel
from acp_client.presentation.terminal_log_view_model import TerminalLogViewModel
from acp_client.presentation.terminal_view_model import TerminalViewModel
from acp_client.presentation.ui_view_model import UIViewModel
from acp_client.tui.navigation import NavigationManager

from .components import (
    ChatView,
    FileTree,
    FooterBar,
    HeaderBar,
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
        ("ctrl+t", "open_terminal_output", "Terminal Output"),
        ("tab", "cycle_focus", "Cycle Focus"),
        ("ctrl+c", "cancel_prompt", "Cancel"),
    ]

    CSS_PATH = str(Path(__file__).with_name("styles") / "app.tcss")

    def __init__(self, *, host: str, port: int, cwd: str | None = None) -> None:
        """Инициализирует приложение с Clean Architecture.

        Все компоненты инициализируются через DI контейнер.

        Args:
            host: Адрес сервера ACP
            port: Порт сервера ACP
            cwd: Путь к проекту (если None, используется текущая рабочая директория)
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
                yield Sidebar(self._session_vm)
                # Передаем cwd в FileTree для отображения структуры проекта
                yield FileTree(
                    filesystem_vm=self._filesystem_vm,
                    root_path=self._cwd,
                )
            with Vertical(id="main-column"):
                yield ChatView(self._chat_vm)
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

    async def _initialize_connection(self) -> None:
        """Инициализирует подключение к серверу."""
        from acp_client.presentation.ui_view_model import ConnectionStatus

        self._app_logger.info("connection_worker_started")
        try:
            from acp_client.application.session_coordinator import SessionCoordinator

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
                from acp_client.application.session_coordinator import SessionCoordinator

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

    async def on_unmount(self) -> None:
        """Очистка ресурсов при завершении приложения."""
        self._app_logger.info("app_unmounting")

        # Закрываем WebSocket соединение
        try:
            from acp_client.infrastructure.services.acp_transport_service import (
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
) -> None:
    """Запускает TUI приложение с параметрами подключения и рабочей директории.

    Args:
        host: Адрес сервера ACP (если None, используется значение по умолчанию)
        port: Порт сервера ACP (если None, используется значение по умолчанию)
        cwd: Путь к проекту (если None, используется текущая рабочая директория)
    """
    resolved_host, resolved_port = resolve_tui_connection(host=host, port=port)
    app = ACPClientApp(host=resolved_host, port=resolved_port, cwd=cwd)
    app.run()
