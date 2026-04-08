"""Модальное окно выбора решения для session/request_permission."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from acp_client.messages import PermissionOption


class PermissionModal(ModalScreen[str | None]):
    """Показывает список permission-опций и возвращает выбранный optionId."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, title: str, options: list[PermissionOption]) -> None:
        """Принимает заголовок запроса и варианты выбора от сервера."""

        super().__init__()
        self._title = title
        self._options = options

    def compose(self) -> ComposeResult:
        """Рендерит заголовок и кнопки выбора разрешения."""

        with Vertical(id="permission-modal"):
            yield Static(self._title, id="permission-title")
            for option in self._options:
                label = f"{option.name} ({option.kind})"
                yield Button(label, id=f"permission-{option.optionId}")
            yield Button("Cancel", id="permission-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Закрывает модал с выбранной опцией или отменой."""

        pressed_id = event.button.id
        if pressed_id == "permission-cancel":
            self.dismiss(None)
            return
        if isinstance(pressed_id, str) and pressed_id.startswith("permission-"):
            self.dismiss(pressed_id.removeprefix("permission-"))

    def action_cancel(self) -> None:
        """Отменяет выбор разрешения клавишей Escape."""

        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Оставляет стандартную клавиатурную навигацию между кнопками."""

        if event.key in {"up", "down", "tab", "shift+tab", "enter"}:
            return
