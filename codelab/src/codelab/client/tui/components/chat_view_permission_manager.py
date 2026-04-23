"""Менеджер встроенного виджета разрешения в ChatView.

Управляет жизненным циклом InlinePermissionWidget:
- Создание и монтирование в ChatView
- Скрытие и удаление
- Синхронизация с PermissionViewModel
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from codelab.client.tui.components.inline_permission_widget import InlinePermissionWidget
from codelab.client.messages import PermissionOption, PermissionToolCall

if TYPE_CHECKING:
    from codelab.client.presentation.permission_view_model import PermissionViewModel
    from codelab.client.tui.components.chat_view import ChatView


class ChatViewPermissionManager:
    """Менеджер встроенного виджета разрешения в ChatView.

    Ответственность:
    - Управление жизненным циклом InlinePermissionWidget
    - Интеграция с ChatView._content_container
    - Синхронизация с PermissionViewModel через Observable паттерн
    - Показ/скрытие виджета разрешения
    """

    def __init__(
        self,
        chat_view: ChatView,
        permission_vm: PermissionViewModel,
    ) -> None:
        """Инициализирует менеджер разрешений.

        Args:
            chat_view: ChatView компонент для монтирования виджета
            permission_vm: PermissionViewModel для управления состоянием
        """
        self.chat_view = chat_view
        self.permission_vm = permission_vm
        self._current_widget: InlinePermissionWidget | None = None
        self._logger = structlog.get_logger("chat_view_permission_manager")

        # Подписаться на изменения видимости в ViewModel
        permission_vm.is_visible.subscribe(self._on_visibility_changed)

    def show_permission_request(
        self,
        request_id: str | int,
        tool_call: PermissionToolCall,
        options: list[PermissionOption],
        on_choice: Callable[[str | int, str], None],
    ) -> None:
        """Показать встроенный виджет разрешения в ChatView.

        Монтирует новый InlinePermissionWidget в контейнер ChatView
        и выполняет автоскролл к нему.

        Args:
            request_id: ID permission request
            tool_call: Информация о tool call
            options: Доступные опции для выбора
            on_choice: Callback при выборе (request_id, option_id)
        """
        # Если виджет уже показан, скрыть его перед созданием нового
        if self._current_widget is not None:
            self.hide_permission_request()

        # Создать новый виджет разрешения
        self._current_widget = InlinePermissionWidget(
            permission_vm=self.permission_vm,
            request_id=request_id,
            tool_call=tool_call,
            options=options,
            on_choice=on_choice,
        )

        # Монтировать в контейнер ChatView если он доступен
        if self.chat_view._content_container is not None:
            self.chat_view._content_container.mount(self._current_widget)
            # Автоскролл к виджету для видимости
            self.chat_view.scroll_end()
            self._logger.info(
                "permission_widget_mounted",
                request_id=request_id,
                tool_call_kind=tool_call.kind,
            )
        else:
            self._logger.error(
                "chat_view_content_container_not_available",
                request_id=request_id,
            )

    def hide_permission_request(self) -> None:
        """Скрыть и удалить встроенный виджет разрешения.

        Удаляет текущий виджет из DOM и очищает ссылку.
        """
        if self._current_widget is not None:
            try:
                self._current_widget.remove()
            except Exception as e:
                # Виджет уже удален или произошла ошибка
                self._logger.warning(
                    "failed_to_remove_permission_widget",
                    error=str(e),
                )
            finally:
                self._current_widget = None
            self._logger.info("permission_widget_hidden")

    def is_widget_visible(self) -> bool:
        """Проверить видимость встроенного виджета.

        Returns:
            True если виджет смонтирован, False иначе
        """
        return self._current_widget is not None

    def _on_visibility_changed(self, is_visible: bool) -> None:
        """Обработчик изменения видимости в PermissionViewModel.

        Скрывает виджет когда ViewModel.is_visible становится False.

        Args:
            is_visible: Новое значение видимости
        """
        if not is_visible:
            self.hide_permission_request()
