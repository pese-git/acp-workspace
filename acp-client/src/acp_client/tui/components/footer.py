"""Нижняя строка статуса приложения."""

from __future__ import annotations

from textual.widgets import Static


class FooterBar(Static):
    """Отображает соединение и подсказки по управлению."""

    def __init__(self) -> None:
        """Создает footer с базовым текстом статуса."""

        super().__init__("Disconnected | Ctrl+Enter send | Ctrl+N new | Ctrl+Q quit", id="footer")

    def set_status(self, text: str) -> None:
        """Обновляет строку статуса в footer."""

        self.update(text)
