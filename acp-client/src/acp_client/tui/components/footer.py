"""Нижняя строка статуса приложения с MVVM интеграцией.

Отвечает за:
- Отображение статуса соединения
- Показ ошибок и уведомлений
- Показ информационных сообщений
- Подсказки по управлению
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Static

if TYPE_CHECKING:
    from acp_client.presentation.ui_view_model import ConnectionStatus, UIViewModel


class FooterBar(Static):
    """Нижняя строка статуса с MVVM интеграцией.

    Обязательно требует UIViewModel для работы. Подписывается на Observable свойства:
    - connection_status: статус соединения
    - error_message: последняя ошибка
    - info_message: информационное сообщение
    - warning_message: предупреждение

    Примеры использования:
        >>> from acp_client.presentation.ui_view_model import UIViewModel
        >>> ui_vm = UIViewModel(event_bus)
        >>> footer = FooterBar(ui_vm)
        >>>
        >>> # Когда UIViewModel обновляется, footer обновляется автоматически
        >>> ui_vm.error_message.value = "Connection failed"
    """

    def __init__(self, ui_vm: UIViewModel) -> None:
        """Инициализирует FooterBar с обязательным UIViewModel.

        Args:
            ui_vm: UIViewModel для управления состояниями
        """
        super().__init__("", id="footer")
        self.ui_vm = ui_vm

        # Подписываемся на изменения в UIViewModel
        self.ui_vm.connection_status.subscribe(self._on_connection_status_changed)
        self.ui_vm.is_loading.subscribe(self._on_loading_changed)
        self.ui_vm.loading_message.subscribe(self._on_loading_message_changed)
        self.ui_vm.error_message.subscribe(self._on_error_message_changed)
        self.ui_vm.info_message.subscribe(self._on_info_message_changed)
        self.ui_vm.warning_message.subscribe(self._on_warning_message_changed)

        # Инициализируем UI с текущим состоянием
        self._update_display()

    def _on_connection_status_changed(self, status: object) -> None:
        """Обновить footer при изменении статуса соединения.

        Args:
            status: Новый статус соединения
        """
        self._update_display()

    def _on_loading_changed(self, is_loading: bool) -> None:
        """Обновить footer при изменении глобальной загрузки."""

        self._update_display()

    def _on_loading_message_changed(self, message: str | None) -> None:
        """Обновить footer при изменении сообщения загрузки."""

        self._update_display()

    def _on_error_message_changed(self, message: str | None) -> None:
        """Обновить footer при появлении ошибки.

        Args:
            message: Текст ошибки или None
        """
        self._update_display()

    def _on_info_message_changed(self, message: str | None) -> None:
        """Обновить footer при появлении информационного сообщения.

        Args:
            message: Информационное сообщение или None
        """
        self._update_display()

    def _on_warning_message_changed(self, message: str | None) -> None:
        """Обновить footer при появлении предупреждения.

        Args:
            message: Текст предупреждения или None
        """
        self._update_display()

    def _update_display(self) -> None:
        """Обновить отображение footer'а на основе текущего состояния UIViewModel."""
        if self.ui_vm is None:
            return

        # Приоритет: ошибка > предупреждение > информация > статус соединения
        if self.ui_vm.error_message.value:
            display_text = f"❌ Error: {self.ui_vm.error_message.value}"
        elif self.ui_vm.warning_message.value:
            display_text = f"⚠️ Warning: {self.ui_vm.warning_message.value}"
        elif self.ui_vm.info_message.value:
            display_text = f"ℹ️ {self.ui_vm.info_message.value}"
        else:
            display_text = self._build_status_line()

        self.update(display_text)

    def _build_status_line(self) -> str:
        """Собрать основную статусную строку с учетом loading и hotkeys."""

        connection_status = self.ui_vm.connection_status.value
        status_prefix = self._status_prefix(connection_status)
        status_text = connection_status.value
        if self.ui_vm.is_loading.value:
            loading_text = self.ui_vm.loading_message.value or "processing..."
            hotkeys = "F1 help | ? hotkeys | Ctrl+Q quit"
            return f"{status_prefix} {status_text} | {loading_text} | {hotkeys}"

        hotkeys = "F1 help | ? hotkeys | Ctrl+Tab sidebar | Ctrl+Q quit"
        return f"{status_prefix} {status_text} | {hotkeys}"

    @staticmethod
    def _status_prefix(status: ConnectionStatus) -> str:
        """Вернуть короткий индикатор для статуса подключения."""

        if status.value == "connected":
            return "✓"
        if status.value in {"connecting", "reconnecting"}:
            return "⟳"
        if status.value == "error":
            return "✗"
        return "○"
