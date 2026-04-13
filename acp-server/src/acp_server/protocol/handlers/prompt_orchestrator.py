"""Главный оркестратор обработки prompt-turn.

Интегрирует все компоненты Этапа 2 и Этапа 3 для оркестрации
обработки prompt-turn в системе ACP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from ...messages import ACPMessage, JsonRpcId
from ..state import ProtocolOutcome, SessionState
from .client_rpc_handler import ClientRPCHandler
from .permission_manager import PermissionManager
from .plan_builder import PlanBuilder
from .state_manager import StateManager
from .tool_call_handler import ToolCallHandler
from .turn_lifecycle_manager import TurnLifecycleManager

if TYPE_CHECKING:
    from ...agent.orchestrator import AgentOrchestrator

# Используем structlog для структурированного логирования
logger = structlog.get_logger()


class PromptOrchestrator:
    """Главный оркестратор обработки prompt-turn.

    Интегрирует все компоненты для оркестрации:
    - StateManager: управление состоянием сессии
    - PlanBuilder: построение планов
    - TurnLifecycleManager: управление фазами turn
    - ToolCallHandler (Этап 2): управление tool calls
    - PermissionManager (Этап 2): управление разрешениями
    - ClientRPCHandler (Этап 2): управление client RPC запросами
    """

    def __init__(
        self,
        state_manager: StateManager,
        plan_builder: PlanBuilder,
        turn_lifecycle_manager: TurnLifecycleManager,
        tool_call_handler: ToolCallHandler,
        permission_manager: PermissionManager,
        client_rpc_handler: ClientRPCHandler,
    ):
        """Инициализирует оркестратор со всеми компонентами.

        Args:
            state_manager: Менеджер состояния сессии
            plan_builder: Построитель планов
            turn_lifecycle_manager: Менеджер жизненного цикла turn
            tool_call_handler: Обработчик tool calls
            permission_manager: Менеджер разрешений
            client_rpc_handler: Обработчик client RPC запросов
        """
        self.state_manager = state_manager
        self.plan_builder = plan_builder
        self.turn_lifecycle_manager = turn_lifecycle_manager
        self.tool_call_handler = tool_call_handler
        self.permission_manager = permission_manager
        self.client_rpc_handler = client_rpc_handler

        logger.debug("PromptOrchestrator initialized with all components")

    async def handle_prompt(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        sessions: dict[str, SessionState],
        agent_orchestrator: AgentOrchestrator,
    ) -> ProtocolOutcome:
        """Обрабатывает session/prompt request.

        Оркестрирует весь цикл обработки промпта:
        1. Инициализация active turn
        2. Извлечение текста из prompt blocks
        3. Обработка через LLM-агента
        4. Построение и отправка notifications
        5. Управление tool calls, permissions, client RPC
        6. Финализация turn

        Args:
            request_id: ID входящего request
            params: Параметры (должны содержать prompt array)
            session: Состояние сессии
            sessions: Словарь всех сессий
            agent_orchestrator: LLM-агент для обработки

        Returns:
            ProtocolOutcome с notifications и response
        """
        session_id = session.session_id
        prompt = params.get("prompt", [])
        notifications: list[ACPMessage] = []

        # Шаг 1: Инициализация active turn
        active_turn = self.turn_lifecycle_manager.create_active_turn(
            session_id,
            request_id,
        )
        session.active_turn = active_turn

        # Шаг 2: Извлечение текста из prompt blocks
        text_preview = _extract_text_preview(prompt)
        prompt_text = _extract_full_text(prompt)

        # Шаг 3: Обновление состояния сессии
        self.state_manager.update_session_title(session, text_preview)
        self.state_manager.add_user_message(session, prompt)
        
        # Сохранить каждый user_message_chunk в events_history для полного replay
        # при загрузке сессии через session/load
        for block in prompt:
            self.state_manager.add_event(session, {
                "type": "session_update",
                "update": {
                    "sessionUpdate": "user_message_chunk",
                    "content": block
                }
            })
        
        self.state_manager.update_session_timestamp(session)

        # Шаг 4: Отправить ACK notification
        ack_notification = _build_ack_notification(session_id, text_preview)
        notifications.append(ack_notification)

        # Шаг 5: Обработать через агента и получить ответ
        agent_response_text = ""
        try:
            # Agent Orchestrator теперь возвращает AgentResponse, не SessionState
            agent_response = await agent_orchestrator.process_prompt(
                session,
                prompt_text,
            )
            agent_response_text = agent_response.text if agent_response else ""
        except Exception as e:
            error_message = f"Agent error: {str(e)}"
            error_notification = _build_error_notification(session_id, error_message)
            notifications.append(error_notification)
            logger.error(
                "agent processing failed",
                session_id=session_id,
                error=str(e),
            )

        # Шаг 6: Добавить ответ ассистента в messages_history и создать события
        if agent_response_text:
            # Добавляем assistant message в историю
            self.state_manager.add_assistant_message(session, agent_response_text)
            
            # Сохраняем agent_message_chunk в events_history в соответствии со спецификацией ACP
            # Формат должен соответствовать ContentBlock структуре протокола
            self.state_manager.add_event(session, {
                "type": "session_update",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {
                        "type": "text",
                        "text": agent_response_text
                    }
                }
            })
            
            # Строим notification для отправки клиенту
            final_notification = _build_agent_response_notification(
                session_id,
                agent_response_text,
            )
            notifications.append(final_notification)

        # Шаг 7: Отправить session info update
        summary = self.state_manager.get_session_summary(session)
        session_info_notification = _build_session_info_notification(
            session_id,
            summary,
        )
        notifications.append(session_info_notification)
        
        # Добавляем session_info событие в events_history
        self.state_manager.add_event(session, {
            "type": "session_update",
            "update": {
                "sessionUpdate": "session_info",
                "title": summary.get("title"),
                "updated_at": summary.get("updated_at"),
            }
        })

        # Шаг 8: Построить plan updates если нужно
        # Извлечем directives из параметров (если есть)
        # Для простоты пока не добавляем план
        # В реальном коде здесь была бы обработка directives

        # Шаг 9: Завершить turn и добавить turn_complete событие
        stop_reason = "end_turn"
        final_notification = self.turn_lifecycle_manager.finalize_turn(
            session,
            stop_reason,
        )
        if final_notification:
            notifications.append(final_notification)
            # Добавляем turn_complete событие в events_history
            self.state_manager.add_event(session, {
                "type": "turn_complete",
                "stopReason": stop_reason,
            })

        self.turn_lifecycle_manager.clear_active_turn(session)

        logger.debug(
            "prompt handling completed",
            session_id=session_id,
            notifications_count=len(notifications),
        )

        return ProtocolOutcome(response=None, notifications=notifications)

    def handle_cancel(
        self,
        request_id: JsonRpcId | None,
        params: dict[str, Any],
        session: SessionState,
        sessions: dict[str, SessionState],
    ) -> ProtocolOutcome:
        """Обрабатывает session/cancel request.

        Логика:
        1. Найти сессию если нужна по ID
        2. Если есть active turn, установить cancel_requested флаг
        3. Отменить все активные tool calls
        4. Отметить cancelled permission requests
        5. Отметить cancelled client RPC requests
        6. Завершить turn с stop_reason='cancel'

        Args:
            request_id: ID cancel request
            params: Параметры (sessionId)
            session: Состояние сессии (может быть найдена по sessionId)
            sessions: Словарь всех сессий

        Returns:
            ProtocolOutcome с notifications об отмене
        """
        session_id = params.get("sessionId", session.session_id)
        notifications: list[ACPMessage] = []

        # Проверяем, есть ли active turn
        if session.active_turn is None:
            logger.debug(
                "cancel request with no active turn",
                session_id=session_id,
            )
            return ProtocolOutcome(response=None, notifications=[])

        # Устанавливаем флаг cancel
        self.turn_lifecycle_manager.mark_cancel_requested(session)

        # Отменяем все активные tool calls
        cancel_messages = self.tool_call_handler.cancel_active_tools(
            session,
            session_id,
        )
        notifications.extend(cancel_messages)

        # Отмечаем cancelled permission requests
        if session.active_turn.permission_request_id is not None:
            session.cancelled_permission_requests.add(
                session.active_turn.permission_request_id,
            )

        # Отмечаем cancelled client RPC requests
        if session.active_turn.pending_client_request is not None:
            session.cancelled_client_rpc_requests.add(
                session.active_turn.pending_client_request.request_id,
            )

        # Завершаем turn с stop_reason='cancel'
        final_notification = self.turn_lifecycle_manager.finalize_turn(
            session,
            "cancel",
        )
        if final_notification:
            notifications.append(final_notification)

        self.turn_lifecycle_manager.clear_active_turn(session)

        logger.debug(
            "cancel request handled",
            session_id=session_id,
            notifications_count=len(notifications),
        )

        return ProtocolOutcome(response=None, notifications=notifications)

    def handle_pending_client_rpc_response(
        self,
        session: SessionState,
        session_id: str,
        kind: str,
        result: Any,
        error: dict[str, Any] | None,
    ) -> ProtocolOutcome:
        """Обрабатывает response на pending client RPC request.

        Используется ClientRPCHandler для обработки response
        и обновления состояния tool call.

        Args:
            session: Состояние сессии
            session_id: ID сессии
            kind: Тип RPC ('fs_read', 'fs_write', 'terminal_create')
            result: Результат выполнения
            error: Ошибка (если есть)

        Returns:
            ProtocolOutcome с updates
        """
        notifications: list[ACPMessage] = []

        # Обработать response через ClientRPCHandler
        updates = self.client_rpc_handler.handle_pending_response(
            session,
            session_id,
            kind,
            result,
            error,
        )
        notifications.extend(updates)

        logger.debug(
            "client RPC response handled",
            session_id=session_id,
            kind=kind,
            has_error=error is not None,
        )

        return ProtocolOutcome(response=None, notifications=notifications)

    def handle_permission_response(
        self,
        session: SessionState,
        session_id: str,
        permission_request_id: JsonRpcId,
        result: Any,
    ) -> ProtocolOutcome:
        """Обрабатывает response на permission request.

        Извлекает решение пользователя и обновляет tool call,
        сохраняет policy если необходимо.

        Args:
            session: Состояние сессии
            session_id: ID сессии
            permission_request_id: ID permission request
            result: Ответ пользователя

        Returns:
            ProtocolOutcome с decision updates
        """
        notifications: list[ACPMessage] = []

        # Проверяем, не был ли этот request отменен
        if permission_request_id in session.cancelled_permission_requests:
            logger.debug(
                "ignoring response to cancelled permission request",
                session_id=session_id,
                request_id=permission_request_id,
            )
            return ProtocolOutcome(response=None, notifications=[])

        # Извлекаем решение из ответа
        outcome = self.permission_manager.extract_permission_outcome(result)
        option_id = self.permission_manager.extract_permission_option_id(result)

        if outcome != "selected" or option_id is None:
            logger.warning(
                "invalid permission response",
                session_id=session_id,
                outcome=outcome,
            )
            return ProtocolOutcome(response=None, notifications=[])

        # Получаем tool_call_id из active_turn
        if (
            session.active_turn is None
            or session.active_turn.permission_tool_call_id is None
        ):
            logger.warning(
                "no permission tool call in active turn",
                session_id=session_id,
            )
            return ProtocolOutcome(response=None, notifications=[])

        tool_call_id = session.active_turn.permission_tool_call_id

        # Строим acceptance updates
        acceptance_updates = self.permission_manager.build_permission_acceptance_updates(
            session,
            session_id,
            tool_call_id,
            option_id,
        )
        notifications.extend(acceptance_updates)

        logger.debug(
            "permission response handled",
            session_id=session_id,
            option_id=option_id,
        )

        return ProtocolOutcome(response=None, notifications=notifications)


def _extract_text_preview(prompt: list[dict[str, Any]]) -> str:
    """Извлекает текстовый preview из prompt blocks.

    Args:
        prompt: Массив content blocks

    Returns:
        Текстовый preview или 'Prompt received'
    """
    if not isinstance(prompt, list):
        return "Prompt received"

    for block in prompt:
        if (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            text = block["text"]
            return text if text else "Prompt received"

    return "Prompt received"


def _extract_full_text(prompt: list[dict[str, Any]]) -> str:
    """Извлекает полный текст из prompt blocks.

    Args:
        prompt: Массив content blocks

    Returns:
        Полный текст из всех блоков
    """
    if not isinstance(prompt, list):
        return ""

    text_blocks: list[str] = []
    for block in prompt:
        if (
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ):
            text_blocks.append(block["text"])

    return "\n".join(text_blocks)


def _extract_final_assistant_text(
    history: list[Any],
) -> str | None:
    """Извлекает последний текст ассистента из истории.

    Args:
        history: История сессии

    Returns:
        Текст последнего ответа ассистента или None
    """
    for entry in reversed(history):
        if isinstance(entry, dict) and entry.get("role") == "assistant":
            text = entry.get("text")
            if isinstance(text, str) and text:
                return text
    return None


def _build_ack_notification(session_id: str, text_preview: str) -> ACPMessage:
    """Строит ACK notification для prompt обработки.

    Args:
        session_id: ID сессии
        text_preview: Preview текста для отображения

    Returns:
        ACPMessage с ACK сообщением
    """
    ack_message = f"Processing prompt: {text_preview[:80]}"
    return ACPMessage.notification(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": ack_message,
                },
            },
        },
    )


def _build_error_notification(session_id: str, error_message: str) -> ACPMessage:
    """Строит error notification.

    Args:
        session_id: ID сессии
        error_message: Сообщение об ошибке

    Returns:
        ACPMessage с ошибкой
    """
    return ACPMessage.notification(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": error_message,
                },
            },
        },
    )


def _build_agent_response_notification(
    session_id: str,
    text: str,
) -> ACPMessage:
    """Строит notification с ответом ассистента.

    Args:
        session_id: ID сессии
        text: Текст ответа

    Returns:
        ACPMessage с ответом ассистента
    """
    return ACPMessage.notification(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": text,
                },
            },
        },
    )


def _build_session_info_notification(
    session_id: str,
    summary: dict[str, Any],
) -> ACPMessage:
    """Строит session info update notification.

    Args:
        session_id: ID сессии
        summary: Сводка состояния сессии

    Returns:
        ACPMessage с session info update
    """
    return ACPMessage.notification(
        "session/update",
        {
            "sessionId": session_id,
            "update": {
                "sessionUpdate": "session_info",
                "title": summary.get("title"),
                "updated_at": summary.get("updated_at"),
            },
        },
    )
