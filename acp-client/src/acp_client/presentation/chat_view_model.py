"""ChatViewModel для управления чатом и prompt-turn.

Отвечает за:
- Управление сообщениями и tool calls в чате
- Отправку prompts и обработку responses
- Обработку разрешений пользователя
- Отслеживание статуса streaming
"""

from typing import Any, Optional, Callable
from dataclasses import dataclass
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
        event_bus: Optional[Any] = None,
        logger: Optional[Any] = None,
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
        self.messages = Observable([])
        self.tool_calls = Observable([])
        self.is_streaming = Observable(False)
        self.pending_permissions = Observable([])
        self.streaming_text = Observable("")
        self.last_stop_reason = Observable(None)

        # Observable команды
        self.send_prompt_cmd = ObservableCommand(self._send_prompt)
        self.cancel_prompt_cmd = ObservableCommand(self._cancel_prompt)
        self.approve_permission_cmd = ObservableCommand(self._approve_permission)
        self.reject_permission_cmd = ObservableCommand(self._reject_permission)
        self.clear_chat_cmd = ObservableCommand(self._clear_chat)

        # Подписываемся на события (если EventBus доступен)
        try:
            from acp_client.domain.events import (
                PromptStartedEvent,
                PromptCompletedEvent,
                PermissionRequestedEvent,
                ErrorOccurredEvent,
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

        self.is_streaming.value = True
        self.streaming_text.value = ""
        self.last_stop_reason.value = None

        try:
            self.logger.info(
                "Sending prompt",
                session_id=session_id,
                prompt_length=len(prompt_text),
            )

            # Отправить prompt через coordinator
            # SessionCoordinator должен обработать updates и опубликовать события
            await self.coordinator.send_prompt(session_id, prompt_text, **kwargs)

        except Exception as e:
            error_msg = f"Failed to send prompt: {str(e)}"
            self.logger.exception("Error sending prompt", error=str(e))
            raise
        finally:
            self.is_streaming.value = False

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
        self.logger.info("Chat cleared")

    def add_message(self, role: str, content: str) -> None:
        """Добавить сообщение в чат.
        
        Args:
            role: Роль ("user", "assistant", "system")
            content: Содержимое сообщения
        """
        messages = self.messages.value
        messages.append({"role": role, "content": content})
        self.messages.value = list(messages)
        self.logger.debug("Message added", role=role, content_length=len(content))

    def append_streaming_text(self, text: str) -> None:
        """Добавить текст к потоковому выводу.
        
        Args:
            text: Текст для добавления
        """
        self.streaming_text.value += text

    def _remove_pending_permission(self, permission_id: str) -> None:
        """Удалить разрешение из pending.
        
        Args:
            permission_id: ID разрешения
        """
        perms = self.pending_permissions.value
        self.pending_permissions.value = [p for p in perms if p.request_id != permission_id]

    # Event handlers
    def _handle_prompt_started(self, event: Any) -> None:
        """Обработать начало prompt-turn.
        
        Args:
            event: PromptStartedEvent из EventBus
        """
        self.is_streaming.value = True
        self.streaming_text.value = ""
        self.logger.debug(
            "Prompt started event received",
            session_id=getattr(event, 'session_id', 'unknown'),
        )

    def _handle_prompt_completed(self, event: Any) -> None:
        """Обработать завершение prompt-turn.
        
        Args:
            event: PromptCompletedEvent из EventBus
        """
        self.is_streaming.value = False
        self.last_stop_reason.value = getattr(event, 'stop_reason', None)
        self.logger.debug(
            "Prompt completed event received",
            session_id=getattr(event, 'session_id', 'unknown'),
            stop_reason=self.last_stop_reason.value,
        )

    def _handle_permission_requested(self, event: Any) -> None:
        """Обработать запрос разрешения.
        
        Args:
            event: PermissionRequestedEvent из EventBus
        """
        perm = PermissionRequest(
            request_id=getattr(event, 'request_id', 'unknown'),
            session_id=getattr(event, 'session_id', 'unknown'),
            action=getattr(event, 'action', 'unknown'),
            resource=getattr(event, 'resource', 'unknown'),
            description=getattr(event, 'description', ''),
        )
        perms = self.pending_permissions.value
        self.pending_permissions.value = list(perms) + [perm]
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
        self.is_streaming.value = False
        error_msg = getattr(event, 'error_message', 'Unknown error')
        self.logger.error(
            "Error occurred event received",
            error_message=error_msg,
            error_type=getattr(event, 'error_type', 'unknown'),
        )
