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
        ("a", "allow_once", "Allow"),
        ("r", "reject_once", "Reject"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, *, title: str, options: list[PermissionOption]) -> None:
        """Принимает заголовок запроса и варианты выбора от сервера."""

        super().__init__()
        self._title = title
        self._options = options
        self._option_by_id: dict[str, PermissionOption] = {
            option.optionId: option for option in options
        }

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
            option_id = pressed_id.removeprefix("permission-")
            if option_id in self._option_by_id:
                self.dismiss(option_id)

    def action_cancel(self) -> None:
        """Отменяет выбор разрешения клавишей Escape."""

        self.dismiss(None)

    def action_allow_once(self) -> None:
        """Выбирает разрешение по горячей клавише A."""

        self._dismiss_by_kinds(["allow_once", "allow_always"])

    def action_reject_once(self) -> None:
        """Выбирает отклонение по горячей клавише R."""

        self._dismiss_by_kinds(["reject_once", "reject_always"])

    def on_mount(self) -> None:
        """Ставит фокус на безопасный вариант выбора при открытии модала."""

        default_button_id = self._default_focus_button_id()
        if default_button_id is None:
            return
        self.query_one(f"#{default_button_id}", Button).focus()

    def on_key(self, event: events.Key) -> None:
        """Оставляет стандартную клавиатурную навигацию между кнопками."""

        if event.key in {"up", "down", "tab", "shift+tab", "enter"}:
            return

    def _dismiss_by_kinds(self, preferred_kinds: list[str]) -> None:
        """Закрывает модал, выбрав первую доступную option по списку kind."""

        self.dismiss(self._resolve_option_id_by_kinds(preferred_kinds))

    def _resolve_option_id_by_kinds(self, preferred_kinds: list[str]) -> str | None:
        """Подбирает optionId по приоритетному списку kind без dismiss."""

        for option in self._options:
            if option.kind in preferred_kinds:
                return option.optionId
        return None

    def _default_focus_button_id(self) -> str | None:
        """Возвращает id кнопки для безопасного дефолтного фокуса."""

        for option in self._options:
            if option.kind == "reject_once":
                return f"permission-{option.optionId}"
        for option in self._options:
            if option.kind == "reject_always":
                return f"permission-{option.optionId}"
        if self._options:
            return f"permission-{self._options[0].optionId}"
        return "permission-cancel"
