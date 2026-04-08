"""Верхняя информационная панель приложения."""

from __future__ import annotations

from textual.widgets import Static


class HeaderBar(Static):
    """Простой header с названием клиента и статусом подключения."""

    def __init__(self) -> None:
        """Создает header в состоянии ожидания подключения."""

        super().__init__("ACP-Client TUI | Connecting...", id="header")

    def set_status(self, status: str) -> None:
        """Обновляет текст статуса подключения в header."""

        self.update(f"ACP-Client TUI | {status}")
