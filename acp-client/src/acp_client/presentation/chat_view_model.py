"""ChatViewModel для управления чатом и prompt-turn.

Отвечает за:
- Управление сообщениями и tool calls в чате
- Отправку prompts и обработку responses
- Обработку разрешений пользователя
- Отслеживание статуса streaming
"""

from dataclasses import dataclass
from typing import Any

from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable, ObservableCommand


@dataclass
class PermissionRequest:
    """Запрос разрешения от сервера."""

    request_id: str
    session_id: str
    action: str
    resource: str
    description: str = ""


@dataclass
class ChatSessionState:
    """Состояние чата, привязанное к конкретной сессии."""

    messages: list[Any]
    tool_calls: list[Any]
    pending_permissions: list[Any]
    streaming_text: str
    is_streaming: bool
    last_stop_reason: str | None


class ChatViewModel(BaseViewModel):
    """ViewModel для управления чатом в активной сессии.

    Хранит состояние чата:
    - messages: история сообщений
    - tool_calls: список tool calls
    - pending_permissions: запросы разрешений в ожидании
    - is_streaming: флаг активного streaming

    Пример использования:
        >>> coordinator = SessionCoordinator(...)
        >>> vm = ChatViewModel(coordinator, event_bus)
        >>>
        >>> # Подписаться на сообщения
        >>> vm.messages.subscribe(lambda m: print(f"Messages: {m}"))
        >>>
        >>> # Отправить prompt
        >>> await vm.send_prompt_cmd.execute("session_1", "Привет!")
        >>>
        >>> # Обработать разрешение
        >>> await vm.approve_permission_cmd.execute(
        ...     "session_1",
        ...     "permission_123",
        ...     approved=True
        ... )
    """

    def __init__(
        self,
        coordinator: Any,  # SessionCoordinator
        event_bus: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        """Инициализировать ChatViewModel.

        Args:
            coordinator: SessionCoordinator для работы с prompt-turn
            event_bus: EventBus для публикации/подписки на события
            logger: Logger для логирования
        """
        super().__init__(event_bus, logger)
        self.coordinator = coordinator

        # Observable свойства
        self.messages: Observable[list[Any]] = Observable([])
        self.tool_calls: Observable[list[Any]] = Observable([])
        self.is_streaming: Observable[bool] = Observable(False)
        self.pending_permissions: Observable[list[Any]] = Observable([])
        self.streaming_text: Observable[str] = Observable("")
        self.last_stop_reason: Observable[str | None] = Observable(None)

        # Активная сессия и кэш UI-состояния по session_id.
        self._active_session_id: str | None = None
        self._session_states: dict[str, ChatSessionState] = {}

        # Observable команды
        self.send_prompt_cmd = ObservableCommand(self._send_prompt)
        self.cancel_prompt_cmd = ObservableCommand(self._cancel_prompt)
        self.approve_permission_cmd = ObservableCommand(self._approve_permission)
        self.reject_permission_cmd = ObservableCommand(self._reject_permission)
        self.clear_chat_cmd = ObservableCommand(self._clear_chat)

        # Подписываемся на события (если EventBus доступен)
        try:
            from acp_client.domain.events import (
                ErrorOccurredEvent,
                PermissionRequestedEvent,
                PromptCompletedEvent,
                PromptStartedEvent,
            )

            self.on_event(PromptStartedEvent, self._handle_prompt_started)
            self.on_event(PromptCompletedEvent, self._handle_prompt_completed)
            self.on_event(PermissionRequestedEvent, self._handle_permission_requested)
            self.on_event(ErrorOccurredEvent, self._handle_error_occurred)
        except ImportError:
            self.logger.debug("DomainEvents not available, skipping event subscriptions")

    async def _send_prompt(self, session_id: str, prompt_text: str, **kwargs: Any) -> None:
        """Отправить prompt в сессию.

        Args:
            session_id: ID сессии
            prompt_text: Текст prompt
            **kwargs: Дополнительные параметры
        """
        if not session_id:
            self.logger.warning("Cannot send prompt: session_id is empty")
            return

        # Гарантируем что prompt отправляется в активную сессию
        # и обновления пишутся в её состояние.
        self.set_active_session(session_id)

        self._set_streaming_state(session_id, is_streaming=True, clear_text=True)
        self._set_last_stop_reason(session_id, None)

        try:
            # Отправить prompt через coordinator с callback для обработки обновлений
            # SessionCoordinator должен обработать updates и опубликовать события
            await self.coordinator.send_prompt(
                session_id, prompt_text, on_update=self._handle_session_update, **kwargs
            )

            # Гарантированное добавление streaming текста в историю после завершения
            # (на случай, если PromptCompletedEvent не был опубликован)
            session_state = self._get_or_create_session_state(session_id)
            streaming_text = session_state.streaming_text
            if streaming_text:
                session_state.messages.append({"role": "assistant", "content": streaming_text})
                session_state.streaming_text = ""
                session_state.is_streaming = False
                self._session_states[session_id] = session_state
                if self._active_session_id == session_id:
                    self.messages.value = list(session_state.messages)
                    self.streaming_text.value = ""
                    self.is_streaming.value = False
                self.logger.info(
                    "Agent response added to message history (fallback)",
                    text_length=len(streaming_text),
                )

        except Exception as e:
            self.logger.exception("Error sending prompt", error=str(e))
            raise
        finally:
            # Очищаем streaming состояние
            self._set_streaming_state(session_id, is_streaming=False, clear_text=True)

    def _handle_session_update(self, update_data: dict[str, Any]) -> None:
        """Обработать session/update от сервера.

        Обрабатывает различные типы обновлений сессии:
        - agent_message_chunk: добавляет текст ответа агента к streaming_text
        - user_message_chunk: обрабатывает фрагменты сообщений пользователя
        - session_info_update: обновляет информацию о сессии
        - и другие типы согласно протоколу ACP

        Args:
            update_data: Данные обновления сессии от сервера
        """
        try:
            params = update_data.get("params", {})
            update = params.get("update", {})
            session_update_type = update.get("sessionUpdate")
            session_id = params.get("sessionId")

            self.logger.debug(
                "session_update_received",
                update_type=session_update_type,
                update=update,
            )

            # Обработка agent_message_chunk - добавляем текст ответа агента
            if session_update_type == "agent_message_chunk":
                content = update.get("content", {})
                text = content.get("text", "")

                if text:
                    # Добавляем текст в состояние той сессии, откуда пришёл update.
                    target_session_id = (
                        session_id if isinstance(session_id, str) else self._active_session_id
                    )
                    if target_session_id is not None:
                        self._append_streaming_text_to_session(target_session_id, text)

                    self.logger.debug("agent_message_chunk_processed", text_length=len(text))

            # Обработка user_message_chunk если нужно
            elif session_update_type == "user_message_chunk":
                # Пока не требуется обработка
                pass

            # Можно добавить обработку других типов: tool_call, plan_update и т.д.

        except Exception as e:
            self.logger.error(
                "Error handling session update",
                error=str(e),
                update_data=update_data,
            )

    async def _cancel_prompt(self, session_id: str) -> None:
        """Отменить текущий prompt.

        Args:
            session_id: ID сессии
        """
        if not session_id:
            self.logger.warning("Cannot cancel prompt: session_id is empty")
            return

        try:
            self.logger.info("Canceling prompt", session_id=session_id)
            await self.coordinator.cancel_prompt(session_id)
            self.is_streaming.value = False
        except Exception as e:
            self.logger.exception("Error canceling prompt", error=str(e))
            raise

    async def _approve_permission(
        self,
        session_id: str,
        permission_id: str,
        **kwargs: Any,
    ) -> None:
        """Утвердить разрешение.

        Args:
            session_id: ID сессии
            permission_id: ID разрешения
            **kwargs: Дополнительные параметры
        """
        try:
            self.logger.info(
                "Approving permission",
                session_id=session_id,
                permission_id=permission_id,
            )
            await self.coordinator.handle_permission(
                session_id,
                permission_id,
                approved=True,
                **kwargs,
            )
            # Удалить из pending
            self._remove_pending_permission(permission_id)
        except Exception as e:
            self.logger.exception("Error approving permission", error=str(e))
            raise

    async def _reject_permission(
        self,
        session_id: str,
        permission_id: str,
        **kwargs: Any,
    ) -> None:
        """Отклонить разрешение.

        Args:
            session_id: ID сессии
            permission_id: ID разрешения
            **kwargs: Дополнительные параметры
        """
        try:
            self.logger.info(
                "Rejecting permission",
                session_id=session_id,
                permission_id=permission_id,
            )
            await self.coordinator.handle_permission(
                session_id,
                permission_id,
                approved=False,
                **kwargs,
            )
            # Удалить из pending
            self._remove_pending_permission(permission_id)
        except Exception as e:
            self.logger.exception("Error rejecting permission", error=str(e))
            raise

    async def _clear_chat(self) -> None:
        """Очистить чат (все сообщения и tool calls)."""
        self.messages.value = []
        self.tool_calls.value = []
        self.pending_permissions.value = []
        self.streaming_text.value = ""
        self.last_stop_reason.value = None
        self._persist_active_state()
        self.logger.info("Chat cleared")

    def add_message(self, role: str, content: str, session_id: str | None = None) -> None:
        """Добавить сообщение в чат.

        Args:
            role: Роль ("user", "assistant", "system")
            content: Содержимое сообщения
            session_id: ID сессии, для которой добавляется сообщение
        """
        if session_id is not None:
            state = self._get_or_create_session_state(session_id)
            state.messages.append({"role": role, "content": content})
            self._session_states[session_id] = state
            if self._active_session_id == session_id:
                self.messages.value = list(state.messages)
        else:
            messages = self.messages.value
            messages.append({"role": role, "content": content})
            self.messages.value = list(messages)
            self._persist_active_state()
        self.logger.debug("Message added", role=role, content_length=len(content))

    def append_streaming_text(self, text: str) -> None:
        """Добавить текст к потоковому выводу.

        Args:
            text: Текст для добавления
        """
        self.streaming_text.value += text
        self._persist_active_state()

    def _remove_pending_permission(self, permission_id: str) -> None:
        """Удалить разрешение из pending.

        Args:
            permission_id: ID разрешения
        """
        perms = self.pending_permissions.value
        self.pending_permissions.value = [p for p in perms if p.request_id != permission_id]
        self._persist_active_state()

    def set_active_session(self, session_id: str | None) -> None:
        """Переключает ChatViewModel на состояние выбранной сессии."""

        # Сохраняем текущее состояние перед переключением.
        self._persist_active_state()
        self._active_session_id = session_id

        if session_id is None:
            self.messages.value = []
            self.tool_calls.value = []
            self.pending_permissions.value = []
            self.streaming_text.value = ""
            self.is_streaming.value = False
            self.last_stop_reason.value = None
            return

        state = self._get_or_create_session_state(session_id)

        self.messages.value = list(state.messages)
        self.tool_calls.value = list(state.tool_calls)
        self.pending_permissions.value = list(state.pending_permissions)
        self.streaming_text.value = state.streaming_text
        self.is_streaming.value = state.is_streaming
        self.last_stop_reason.value = state.last_stop_reason

    def _persist_active_state(self) -> None:
        """Сохраняет текущее состояние чата для активной сессии."""

        if self._active_session_id is None:
            return

        self._session_states[self._active_session_id] = ChatSessionState(
            messages=list(self.messages.value),
            tool_calls=list(self.tool_calls.value),
            pending_permissions=list(self.pending_permissions.value),
            streaming_text=self.streaming_text.value,
            is_streaming=self.is_streaming.value,
            last_stop_reason=self.last_stop_reason.value,
        )

    def _get_or_create_session_state(self, session_id: str) -> ChatSessionState:
        """Возвращает состояние сессии или создаёт пустое."""

        state = self._session_states.get(session_id)
        if state is not None:
            return state

        state = ChatSessionState(
            messages=[],
            tool_calls=[],
            pending_permissions=[],
            streaming_text="",
            is_streaming=False,
            last_stop_reason=None,
        )
        self._session_states[session_id] = state
        return state

    def _append_streaming_text_to_session(self, session_id: str, text: str) -> None:
        """Добавляет streaming chunk в состояние указанной сессии."""

        state = self._get_or_create_session_state(session_id)
        state.streaming_text += text
        state.is_streaming = True
        self._session_states[session_id] = state

        if self._active_session_id == session_id:
            self.streaming_text.value = state.streaming_text
            self.is_streaming.value = True

    def _set_streaming_state(
        self, session_id: str, *, is_streaming: bool, clear_text: bool
    ) -> None:
        """Обновляет флаг streaming и буфер текста для сессии."""

        state = self._get_or_create_session_state(session_id)
        state.is_streaming = is_streaming
        if clear_text:
            state.streaming_text = ""
        self._session_states[session_id] = state

        if self._active_session_id == session_id:
            self.is_streaming.value = is_streaming
            if clear_text:
                self.streaming_text.value = ""

    def _set_last_stop_reason(self, session_id: str, stop_reason: str | None) -> None:
        """Сохраняет stop reason для сессии и синхронизирует активный UI."""

        state = self._get_or_create_session_state(session_id)
        state.last_stop_reason = stop_reason
        self._session_states[session_id] = state

        if self._active_session_id == session_id:
            self.last_stop_reason.value = stop_reason

    # Event handlers
    def _handle_prompt_started(self, event: Any) -> None:
        """Обработать начало prompt-turn.

        Args:
            event: PromptStartedEvent из EventBus
        """
        self.logger.debug(
            "Prompt started event received - CLEARING streaming_text",
            session_id=getattr(event, "session_id", "unknown"),
        )
        session_id = getattr(event, "session_id", None)
        if isinstance(session_id, str):
            self._set_streaming_state(session_id, is_streaming=True, clear_text=True)

    def _handle_prompt_completed(self, event: Any) -> None:
        """Обработать завершение prompt-turn.

        После завершения streaming сохраняет накопленный текст агента в историю сообщений.

        Args:
            event: PromptCompletedEvent из EventBus
        """
        self.logger.debug(
            "Prompt completed event received - STOPPING streaming",
            session_id=getattr(event, "session_id", "unknown"),
            stop_reason=getattr(event, "stop_reason", None),
            final_streaming_text_length=len(self.streaming_text.value),
        )

        session_id = getattr(event, "session_id", None)
        if not isinstance(session_id, str):
            return

        state = self._get_or_create_session_state(session_id)
        streaming_text = state.streaming_text
        if streaming_text:
            state.messages.append({"role": "assistant", "content": streaming_text})
            self._session_states[session_id] = state
            if self._active_session_id == session_id:
                self.messages.value = list(state.messages)
            self.logger.debug(
                "Agent response saved to message history",
                text_length=len(streaming_text),
            )

        # Отключаем streaming и очищаем буфер
        self._set_streaming_state(session_id, is_streaming=False, clear_text=True)
        self._set_last_stop_reason(session_id, getattr(event, "stop_reason", None))

    def _handle_permission_requested(self, event: Any) -> None:
        """Обработать запрос разрешения.

        Args:
            event: PermissionRequestedEvent из EventBus
        """
        perm = PermissionRequest(
            request_id=getattr(event, "request_id", "unknown"),
            session_id=getattr(event, "session_id", "unknown"),
            action=getattr(event, "action", "unknown"),
            resource=getattr(event, "resource", "unknown"),
            description=getattr(event, "description", ""),
        )
        perms = self.pending_permissions.value
        self.pending_permissions.value = list(perms) + [perm]
        self._persist_active_state()
        self.logger.debug(
            "Permission requested event received",
            request_id=perm.request_id,
            action=perm.action,
        )

    def _handle_error_occurred(self, event: Any) -> None:
        """Обработать ошибку.

        Args:
            event: ErrorOccurredEvent из EventBus
        """
        session_id = getattr(event, "session_id", None)
        if isinstance(session_id, str):
            self._set_streaming_state(session_id, is_streaming=False, clear_text=False)
        else:
            self.is_streaming.value = False
            self._persist_active_state()
        error_msg = getattr(event, "error_message", "Unknown error")
        self.logger.error(
            "Error occurred event received",
            error_message=error_msg,
            error_type=getattr(event, "error_type", "unknown"),
        )
