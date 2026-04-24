"""Главный оркестратор обработки prompt-turn.

Интегрирует все компоненты Этапа 2 и Этапа 3 для оркестрации
обработки prompt-turn в системе ACP.
Включает регистрацию и выполнение инструментов через tool registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

import structlog

from ...client_rpc.service import ClientRPCService
from ...messages import ACPMessage, JsonRpcId
from ...tools.base import ToolRegistry
from ..content.extractor import ContentExtractor
from ..content.formatter import ContentFormatter
from ..content.validator import ContentValidator
from ..state import LLMLoopResult, ProtocolOutcome, SessionState, ToolResult
from .client_rpc_handler import ClientRPCHandler
from .permission_manager import PermissionManager
from .plan_builder import PlanBuilder
from .replay_manager import ReplayManager
from .slash_commands import CommandRegistry, SlashCommandRouter
from .slash_commands.builtin import (
    HelpCommandHandler,
    ModeCommandHandler,
    StatusCommandHandler,
)
from .state_manager import StateManager
from .tool_call_handler import ToolCallHandler
from .turn_lifecycle_manager import TurnLifecycleManager

if TYPE_CHECKING:
    from ...agent.orchestrator import AgentOrchestrator
    from .global_policy_manager import GlobalPolicyManager

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
        tool_registry: ToolRegistry,
        client_rpc_service: ClientRPCService | None = None,
        global_policy_manager: GlobalPolicyManager | None = None,
    ):
        """Инициализирует оркестратор со всеми компонентами.

        Регистрирует встроенные инструменты (fs/*, terminal/*) и их executors.

        Args:
            state_manager: Менеджер состояния сессии
            plan_builder: Построитель планов
            turn_lifecycle_manager: Менеджер жизненного цикла turn
            tool_call_handler: Обработчик tool calls
            permission_manager: Менеджер разрешений
            client_rpc_handler: Обработчик client RPC запросов
            tool_registry: Реестр инструментов для регистрации tools
            client_rpc_service: Сервис ClientRPC для выполнения инструментов (опционально)
            global_policy_manager: GlobalPolicyManager для fallback chain (опционально)
        """
        self.state_manager = state_manager
        self.plan_builder = plan_builder
        self.turn_lifecycle_manager = turn_lifecycle_manager
        self.tool_call_handler = tool_call_handler
        self.permission_manager = permission_manager
        self.client_rpc_handler = client_rpc_handler
        self.tool_registry = tool_registry
        self.client_rpc_service = client_rpc_service
        # Сохранить GlobalPolicyManager для fallback chain в _decide_tool_execution
        self._global_policy_manager = global_policy_manager

        # Content processing (Фаза 2 и Фаза 3)
        self.content_extractor = ContentExtractor()
        self.content_validator = ContentValidator()
        self.content_formatter = ContentFormatter()  # Фаза 3: LLM formatting

        # Replay manager для сохранения истории session/update (Этап 6)
        self.replay_manager = ReplayManager()

        # Создать bridge и permission checker для executors только если RPC service доступен
        if client_rpc_service is not None:
            # Импортировать только при необходимости для избежания циклических импортов
            from ...tools.definitions import (
                FileSystemToolDefinitions,
                PlanToolDefinitions,
                TerminalToolDefinitions,
            )
            from ...tools.executors.filesystem_executor import FileSystemToolExecutor
            from ...tools.executors.plan_executor import PlanToolExecutor
            from ...tools.executors.terminal_executor import TerminalToolExecutor
            from ...tools.integrations.client_rpc_bridge import ClientRPCBridge
            from ...tools.integrations.permission_checker import PermissionChecker

            bridge = ClientRPCBridge(client_rpc_service)
            checker = PermissionChecker(permission_manager)

            # Создать executors для встроенных инструментов
            fs_executor = FileSystemToolExecutor(bridge, checker)
            terminal_executor = TerminalToolExecutor(bridge, checker)
            plan_executor = PlanToolExecutor()

            # Зарегистрировать встроенные инструменты
            FileSystemToolDefinitions.register_all(tool_registry, fs_executor)
            TerminalToolDefinitions.register_all(tool_registry, terminal_executor)
            PlanToolDefinitions.register_all(tool_registry, plan_executor)

            logger.debug(
                "PromptOrchestrator initialized with tool executors",
                tools_registered=len(tool_registry.get_available_tools("")),
            )
        else:
            # Даже без client_rpc_service, регистрируем plan tool
            # так как он не требует client_rpc
            from ...tools.definitions import PlanToolDefinitions
            from ...tools.executors.plan_executor import PlanToolExecutor

            plan_executor = PlanToolExecutor()
            PlanToolDefinitions.register_all(tool_registry, plan_executor)

            logger.debug(
                "PromptOrchestrator initialized with plan tool only (client_rpc_service is None)"
            )

        # Инициализация slash commands
        self._command_registry = CommandRegistry()
        self._slash_router = SlashCommandRouter(self._command_registry)

        # Регистрация встроенных команд
        self._command_registry.register(StatusCommandHandler())
        self._command_registry.register(ModeCommandHandler())
        # HelpCommandHandler требует registry для отображения всех команд
        self._command_registry.register(HelpCommandHandler(self._command_registry))

        logger.debug(
            "Slash commands initialized",
            commands=self._command_registry.registered_commands,
        )

    def set_global_policy_manager(
        self, manager: GlobalPolicyManager | None
    ) -> None:
        """Установить GlobalPolicyManager после инициализации.
        
        Используется для инъекции manager'а в оркестратор, если он был создан
        после инициализации (например, в ACPProtocol).
        
        Args:
            manager: GlobalPolicyManager для fallback chain или None для отключения
        """
        self._global_policy_manager = manager
        if manager:
            logger.debug("GlobalPolicyManager injected into PromptOrchestrator")

    def _try_handle_slash_command(
        self,
        prompt_text: str,
        session: SessionState,
    ) -> ProtocolOutcome | None:
        """Проверяет и обрабатывает slash-команду.

        Если prompt_text начинается с '/', пытается найти handler
        и выполнить команду. Возвращает None если команда не найдена
        (для fallback в LLM) или если prompt_text не является командой.

        Args:
            prompt_text: Текст промпта
            session: Состояние сессии

        Returns:
            ProtocolOutcome если команда обработана, None для fallback
        """
        prompt_stripped = prompt_text.strip()

        # Проверяем, начинается ли с '/'
        if not prompt_stripped.startswith("/"):
            return None

        # Парсим команду и аргументы
        parts = prompt_stripped[1:].split(maxsplit=1)
        if not parts:
            return None

        command_name = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        # Пробуем обработать через router
        return self._slash_router.route(command_name, args, session)

    @property
    def command_registry(self) -> CommandRegistry:
        """Возвращает реестр slash-команд для динамического управления."""
        return self._command_registry

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
            self.state_manager.add_event(
                session,
                {
                    "type": "session_update",
                    "update": {"sessionUpdate": "user_message_chunk", "content": block},
                },
            )

        self.state_manager.update_session_timestamp(session)

        # Шаг 4: Отправить ACK notification
        ack_notification = _build_ack_notification(session_id, text_preview)
        notifications.append(ack_notification)

        # Шаг 4.5: Проверить, является ли prompt slash-командой
        # Согласно спецификации ACP (14-Slash Commands.md):
        # "Commands are included as regular user messages in prompt requests"
        # "The Agent recognizes the command prefix and processes it accordingly"
        slash_outcome = self._try_handle_slash_command(prompt_text, session)
        if slash_outcome is not None:
            logger.info(
                "Slash command executed",
                prompt=prompt_text[:50],
                session_id=session_id,
            )
            # Добавляем ACK notification к результату slash-команды
            all_notifications = notifications + list(slash_outcome.notifications)
            # Финализируем turn
            session.active_turn = None
            # Формируем response
            response = ACPMessage.response(
                request_id,
                {"stop": {"reason": "end_turn"}},
            )
            return ProtocolOutcome(
                response=response,
                notifications=all_notifications,
            )

        # Шаг 5: Запустить LLM loop для обработки промпта и tool calls
        # Согласно ACP протоколу (05-Prompt Turn.md):
        # "The cycle returns to step 2, continuing until the language model completes
        # its response without requesting additional tool calls or the turn gets stopped"
        llm_loop_result = await self._run_llm_loop(
            session=session,
            session_id=session_id,
            agent_orchestrator=agent_orchestrator,
            initial_prompt_text=prompt_text,
        )
        
        # Добавить notifications из LLM loop
        notifications.extend(llm_loop_result.notifications)

        # Шаг 6: Отправить session info update
        summary = self.state_manager.get_session_summary(session)
        session_info_notification = _build_session_info_notification(
            session_id,
            summary,
        )
        notifications.append(session_info_notification)

        # Добавляем session_info событие в events_history
        self.state_manager.add_event(
            session,
            {
                "type": "session_update",
                "update": {
                    "sessionUpdate": "session_info",
                    "title": summary.get("title"),
                    "updated_at": summary.get("updated_at"),
                },
            },
        )

        # Шаг 7: Построить plan updates если нужно
        # Извлечем directives из параметров (если есть)
        # Для простоты пока не добавляем план
        # В реальном коде здесь была бы обработка directives

        # Шаг 8: Завершить turn на основе результата LLM loop
        # Согласно протоколу ACP (doc/Agent Client Protocol/protocol/05-Prompt Turn.md),
        # response на session/prompt должен отправляться ПОСЛЕ завершения всех операций
        
        # Если LLM loop deferred для permission - не завершаем turn
        if llm_loop_result.pending_permission:
            logger.debug(
                "turn deferred, awaiting permission response",
                session_id=session_id,
                permission_request_id=(
                    session.active_turn.permission_request_id
                    if session.active_turn else None
                ),
            )
            return ProtocolOutcome(notifications=notifications)
        
        # Определить stop_reason из результата LLM loop
        stop_reason = llm_loop_result.stop_reason or "end_turn"
        
        # Финализировать turn
        self.turn_lifecycle_manager.finalize_turn(session, stop_reason)
        self.turn_lifecycle_manager.clear_active_turn(session)

        logger.debug(
            "prompt handling completed",
            session_id=session_id,
            stop_reason=stop_reason,
            notifications_count=len(notifications),
        )

        response = (
            ACPMessage.response(request_id, {"stopReason": stop_reason})
            if request_id is not None
            else None
        )
        return ProtocolOutcome(response=response, notifications=notifications)

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

        # Отменяем все pending RPC requests через ClientRPCService
        # Это немедленно завершит все ожидающие RPC вызовы с ClientRPCCancelledError
        if self.client_rpc_service is not None:
            cancelled_rpc_count = self.client_rpc_service.cancel_all_pending_requests(
                reason="session/cancel requested",
            )
            if cancelled_rpc_count > 0:
                logger.debug(
                    "cancelled pending RPC requests",
                    session_id=session_id,
                    cancelled_count=cancelled_rpc_count,
                )

        # Фиксируем отмену turn с ACP-совместимым stopReason.
        self.turn_lifecycle_manager.finalize_turn(session, "cancelled")

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

    async def _process_tool_calls(
        self,
        session: SessionState,
        session_id: str,
        tool_calls: list[Any],
        notifications: list[ACPMessage],
    ) -> None:
        """Обработать tool_calls из AgentResponse.

        Для каждого tool call:
        1. Создать tool call через tool_call_handler
        2. Отправить notification о создании tool_call
        3. Проверить режим (ask/auto) и разрешения
        4. Выполнить tool через tool_registry
        5. Обновить статус и отправить notification

        Args:
            session: Состояние сессии
            session_id: ID сессии
            tool_calls: Список tool_calls из agent_response
            notifications: Список уведомлений для отправки клиенту
        """
        logger.info(
            "processing tool calls through permission flow",
            session_id=session_id,
            num_tool_calls=len(tool_calls),
            tool_names=[getattr(tc, "name", "unknown") for tc in tool_calls],
        )

        for tool_call in tool_calls:
            # Получить информацию о tool call
            tool_name = getattr(tool_call, "name", None)
            tool_arguments = getattr(tool_call, "arguments", {})

            if not tool_name:
                logger.warning(
                    "tool_call has no name",
                    session_id=session_id,
                )
                continue

            # Определить kind из ToolDefinition (если зарегистрирован в реестре)
            tool_kind = "other"
            tool_definition = self.tool_registry.get(tool_name)
            if tool_definition is not None:
                tool_kind = tool_definition.kind
            else:
                # Fallback для незарегистрированных tools
                logger.warning(
                    "tool not found in registry, using 'other' kind",
                    session_id=session_id,
                    tool_name=tool_name,
                )

            # Создать tool call в сессии с правильным kind и сохранить данные для execution
            tool_call_id = self.tool_call_handler.create_tool_call(
                session=session,
                title=tool_name,
                kind=tool_kind,
                tool_name=tool_name,
                tool_arguments=tool_arguments,
            )

            # Отправить notification о создании tool_call
            notifications.append(
                self.tool_call_handler.build_tool_call_notification(
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    kind=tool_kind,
                )
            )

            # Получить текущий tool call из сессии
            tool_call_state = session.tool_calls.get(tool_call_id)
            if tool_call_state is None:
                logger.warning(
                    "tool_call_state not found",
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                )
                continue

            # Проверить requires_permission из tool_definition
            # Если tool не требует permission (например update_plan), сразу разрешить
            if tool_definition is not None and not tool_definition.requires_permission:
                logger.debug(
                    "tool does not require permission, auto-allowing",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                )
                decision = "allow"
            else:
                # Применить decision logic через fallback chain
                decision = await self._decide_tool_execution(
                    session=session,
                    tool_kind=tool_kind,
                )

            if decision == "allow":
                # Выполнить tool - переходим к execution ниже
                logger.debug(
                    "tool execution allowed by decision logic",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                )
                pass  # Continue to execution below
            elif decision == "reject":
                # Отклонить tool
                logger.debug(
                    "tool execution rejected by decision logic",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                )
                self.tool_call_handler.update_tool_call_status(
                    session,
                    tool_call_id,
                    "failed",
                )
                rejection_msg = f"Tool execution rejected by policy for {tool_kind}"
                notifications.append(
                    ACPMessage.notification(
                        "session/update",
                        {
                            "sessionId": session_id,
                            "update": {
                                "sessionUpdate": "tool_call_update",
                                "toolCallId": tool_call_id,
                                "status": "failed",
                                "content": [
                                    {
                                        "type": "content",
                                        "content": {
                                            "type": "text",
                                            "text": rejection_msg,
                                        },
                                    }
                                ],
                            },
                        },
                    )
                )
                continue
            elif decision == "ask":
                # Запросить разрешение у пользователя
                logger.debug(
                    "permission request created for tool",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                )
                permission_msg = self.permission_manager.build_permission_request(
                    session,
                    session_id,
                    tool_call_state.tool_call_id,
                    tool_call_state.title,
                    tool_kind,
                )
                notifications.append(permission_msg)
                
                # Перейти в фазу awaiting_permission
                if session.active_turn:
                    session.active_turn.phase = "awaiting_permission"
                    session.active_turn.permission_tool_call_id = tool_call_id
                
                logger.debug(
                    "permission request sent to client",
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    permission_request_id=permission_msg.id,
                )
                continue

            # Выполнить tool (decision == "allow")
            try:
                # Отправить notification о начале выполнения
                self.tool_call_handler.update_tool_call_status(
                    session,
                    tool_call_id,
                    "in_progress",
                )
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="in_progress",
                    )
                )

                # Выполнить tool с передачей session для executors
                result = await self.tool_registry.execute_tool(
                    session_id,
                    tool_name,
                    tool_arguments,
                    session=session,
                )

                # Извлечь content из result
                extracted_content = await self.content_extractor.extract_from_result(
                    tool_call_id, result
                )

                # Валидировать content
                is_valid, errors = self.content_validator.validate_content_list(
                    extracted_content.content_items
                )

                if not is_valid:
                    logger.warning(
                        "tool_result_content_validation_failed",
                        tool_call_id=tool_call_id,
                        errors=errors
                    )

                # Сохранить content в tool call state
                tool_call_state = session.tool_calls.get(tool_call_id)
                if tool_call_state:
                    tool_call_state.result_content = extracted_content.content_items

                # Форматировать content для LLM (Фаза 3)
                provider_raw = session.config_values.get("llm_provider", "openai")
                provider = cast(Literal["openai", "anthropic"], provider_raw)
                formatted_for_llm = self.content_formatter.format_for_llm(
                    extracted_content,
                    provider=provider
                )
                logger.debug(
                    "tool_result_formatted_for_llm",
                    tool_call_id=tool_call_id,
                    provider=provider,
                    formatted_keys=list(formatted_for_llm.keys())
                )

                # Обновить статус tool call
                if result.success:
                    self.tool_call_handler.update_tool_call_status(
                        session,
                        tool_call_id,
                        "completed",
                        content=[
                            {
                                "type": "content",
                                "content": {
                                    "type": "text",
                                    "text": result.output or "Tool executed successfully",
                                },
                            }
                        ],
                    )
                    status = "completed"
                else:
                    self.tool_call_handler.update_tool_call_status(
                        session,
                        tool_call_id,
                        "failed",
                    )
                    status = "failed"

                # Отправить notification об окончании выполнения
                notification_content: list[dict[str, Any]] | None = None
                if result.success and result.output:
                    notification_content = [
                        {
                            "type": "content",
                            "content": {
                                "type": "text",
                                "text": result.output,
                            },
                        }
                    ]

                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status=status,
                        content=notification_content,
                    )
                )

                logger.debug(
                    "tool executed successfully",
                    session_id=session_id,
                    tool_name=tool_name,
                    status=status,
                )

            except Exception as e:
                # Обработать ошибку выполнения
                logger.error(
                    "tool execution failed",
                    session_id=session_id,
                    tool_name=tool_name,
                    error=str(e),
                )

                self.tool_call_handler.update_tool_call_status(
                    session,
                    tool_call_id,
                    "failed",
                )
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="failed",
                    )
                )

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
        if session.active_turn is None or session.active_turn.permission_tool_call_id is None:
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

    async def _decide_tool_execution(
        self,
        session: SessionState,
        tool_kind: str,
    ) -> str:
        """Принимает решение о выполнении tool с fallback chain.
        
        Реализует fallback chain для проверки разрешений:
        1. session.permission_policy[tool_kind] - session-local политика
        2. global_policy[tool_kind] - глобальная политика (если доступна)
        3. ask (по умолчанию) - запросить разрешение у пользователя
        
        Args:
            session: Состояние сессии
            tool_kind: Тип инструмента (read, edit, execute, и т.д.)
        
        Returns:
            'allow' - выполнить инструмент
            'reject' - отклонить инструмент
            'ask' - запросить разрешение у пользователя
        """
        logger.debug(
            "checking tool execution decision",
            session_id=session.session_id,
            tool_kind=tool_kind,
        )
        
        # Шаг 1: Проверить session-local политику
        session_policy = session.permission_policy.get(tool_kind)
        logger.debug(
            "checking session policy for tool_kind",
            session_id=session.session_id,
            tool_kind=tool_kind,
            session_policy=session_policy,
        )
        
        if session_policy == "allow_always":
            logger.debug(
                "decision: allow (session policy)",
                tool_kind=tool_kind,
                session_id=session.session_id,
            )
            return "allow"
        if session_policy == "reject_always":
            logger.debug(
                "decision: reject (session policy)",
                tool_kind=tool_kind,
                session_id=session.session_id,
            )
            return "reject"
        
        logger.debug(
            "no session policy found",
            session_id=session.session_id,
            tool_kind=tool_kind,
        )
        
        # Шаг 2: Проверить глобальную политику (если менеджер доступен)
        if self._global_policy_manager is not None:
            global_policy = await self._global_policy_manager.get_global_policy(tool_kind)
            logger.debug(
                "checking global policy for tool_kind",
                session_id=session.session_id,
                tool_kind=tool_kind,
                global_policy=global_policy,
            )
            
            if global_policy == "allow_always":
                logger.debug(
                    "decision: allow (global policy)",
                    tool_kind=tool_kind,
                    session_id=session.session_id,
                )
                return "allow"
            if global_policy == "reject_always":
                logger.debug(
                    "decision: reject (global policy)",
                    tool_kind=tool_kind,
                    session_id=session.session_id,
                )
                return "reject"
        else:
            logger.debug(
                "global policy manager not available",
                session_id=session.session_id,
            )
        
        logger.debug(
            "no global policy found",
            session_id=session.session_id,
            tool_kind=tool_kind,
        )
        
        # Шаг 3: По умолчанию - запросить разрешение
        logger.debug(
            "decision: ask user for permission",
            tool_kind=tool_kind,
            session_id=session.session_id,
        )
        return "ask"

    async def _run_llm_loop(
        self,
        session: SessionState,
        session_id: str,
        agent_orchestrator: AgentOrchestrator,
        initial_prompt_text: str | None = None,
        tool_results: list[ToolResult] | None = None,
    ) -> LLMLoopResult:
        """Основной цикл LLM для обработки tool calls.
        
        Реализует цикл согласно ACP протоколу (05-Prompt Turn.md):
        "The Agent sends the tool results back to the language model as another request.
        The cycle returns to step 2, continuing until the language model completes
        its response without requesting additional tool calls or the turn gets stopped
        by the Agent or cancelled by the Client."
        
        Args:
            session: Состояние сессии
            session_id: ID сессии
            agent_orchestrator: Оркестратор агента для вызова LLM
            initial_prompt_text: Начальный промпт (None для продолжения)
            tool_results: Результаты tools для продолжения (None для начала)
            
        Returns:
            LLMLoopResult с notifications и статусом завершения
        """
        notifications: list[ACPMessage] = []
        max_iterations = 10
        iteration = 0
        final_text: str | None = None
        
        while iteration < max_iterations:
            iteration += 1
            
            # CHECK 1: cancel перед вызовом LLM
            if self._is_cancel_requested(session):
                logger.debug(
                    "llm_loop cancelled before LLM call",
                    session_id=session_id,
                    iteration=iteration,
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason="cancelled",
                )
            
            # Вызвать LLM
            try:
                if iteration == 1 and initial_prompt_text:
                    # Первая итерация с новым промптом (непустая строка)
                    agent_response = await agent_orchestrator.process_prompt(
                        session, initial_prompt_text
                    )
                else:
                    # Продолжение с tool results (пустой промпт или последующие итерации)
                    agent_response = await agent_orchestrator.continue_with_tool_results(
                        session, tool_results or []
                    )
            except Exception as e:
                error_message = f"Agent error: {str(e)}"
                notifications.append(_build_error_notification(session_id, error_message))
                logger.error(
                    "llm_loop agent processing failed",
                    session_id=session_id,
                    iteration=iteration,
                    error=str(e),
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason="end_turn",  # Завершаем turn при ошибке
                )
            
            # CHECK 2: cancel после вызова LLM
            if self._is_cancel_requested(session):
                logger.debug(
                    "llm_loop cancelled after LLM call",
                    session_id=session_id,
                    iteration=iteration,
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason="cancelled",
                )
            
            agent_response_text = agent_response.text if agent_response else ""
            has_tool_calls = agent_response and agent_response.tool_calls
            
            # Отправить текстовый ответ если есть
            if agent_response_text:
                final_text = agent_response_text
                
                # Добавить assistant message в историю ТОЛЬКО если нет tool_calls
                # Если есть tool_calls, assistant message добавится позже с tool_calls
                if not has_tool_calls:
                    self.state_manager.add_assistant_message(session, agent_response_text)
                
                # Сохранить в events_history
                self.state_manager.add_event(
                    session,
                    {
                        "type": "session_update",
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": agent_response_text},
                        },
                    },
                )
                
                # Notification для клиента
                notifications.append(
                    _build_agent_response_notification(session_id, agent_response_text)
                )
            
            # Обработка плана из agent_response (если есть)
            # Используем getattr для обратной совместимости с mock объектами
            agent_plan = getattr(agent_response, "plan", None) if agent_response else None
            if agent_plan:
                validated_plan = self.plan_builder.validate_plan_entries(agent_plan)
                if validated_plan:
                    # Обновить состояние сессии
                    session.latest_plan = list(validated_plan)
                    
                    # Построить и отправить notification
                    plan_notification = self.plan_builder.build_plan_notification(
                        session_id, validated_plan
                    )
                    notifications.append(plan_notification)
                    
                    # Сохранить в events_history для replay
                    self.replay_manager.save_plan(session, validated_plan)
                    
                    logger.debug(
                        "plan processed and published",
                        session_id=session_id,
                        num_entries=len(validated_plan),
                    )
            
            # Если нет tool_calls - выходим из цикла
            if not has_tool_calls:
                logger.debug(
                    "llm_loop completed - no tool calls",
                    session_id=session_id,
                    iteration=iteration,
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason="end_turn",
                    final_text=final_text,
                )
            
            # Обработать tool_calls и собрать результаты
            logger.info(
                "llm_loop processing tool calls",
                session_id=session_id,
                iteration=iteration,
                num_tool_calls=len(agent_response.tool_calls),
            )
            
            # ВАЖНО: Сохранить assistant message с tool_calls в историю сессии
            # Это необходимо для OpenAI API, который требует последовательность:
            # 1. assistant message с tool_calls
            # 2. tool messages с результатами
            # Без этого LLM не знает что инструмент уже запрашивался
            tool_calls_for_history = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in agent_response.tool_calls
            ]
            assistant_msg_with_tools = {
                "role": "assistant",
                "text": agent_response_text or "",
                "tool_calls": tool_calls_for_history,
            }
            session.history.append(assistant_msg_with_tools)
            logger.debug(
                "assistant_message_with_tool_calls_added_to_history",
                session_id=session_id,
                tool_calls_count=len(tool_calls_for_history),
            )
            
            loop_result = await self._process_tool_calls_for_llm_loop(
                session,
                session_id,
                agent_response.tool_calls,
                notifications,
            )
            
            # Если нужен permission - прерываем loop
            if loop_result.pending_permission:
                logger.debug(
                    "llm_loop deferred for permission",
                    session_id=session_id,
                    iteration=iteration,
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason=None,  # Turn не завершен
                    pending_permission=True,
                    tool_results=loop_result.tool_results,
                )
            
            # Если был cancel - прерываем
            if self._is_cancel_requested(session):
                logger.debug(
                    "llm_loop cancelled during tool processing",
                    session_id=session_id,
                    iteration=iteration,
                )
                return LLMLoopResult(
                    notifications=notifications,
                    stop_reason="cancelled",
                )
            
            # Подготовить tool_results для следующей итерации
            tool_results = loop_result.tool_results
        
        # Достигнут лимит итераций
        logger.warning(
            "llm_loop max iterations reached",
            session_id=session_id,
            max_iterations=max_iterations,
        )
        return LLMLoopResult(
            notifications=notifications,
            stop_reason="max_iterations",
            final_text=final_text,
        )

    def _is_cancel_requested(self, session: SessionState) -> bool:
        """Проверяет, был ли запрошен cancel для текущего turn.
        
        Args:
            session: Состояние сессии
            
        Returns:
            True если cancel был запрошен
        """
        return (
            session.active_turn is not None
            and session.active_turn.cancel_requested
        )

    async def _process_tool_calls_for_llm_loop(
        self,
        session: SessionState,
        session_id: str,
        tool_calls: list[Any],
        notifications: list[ACPMessage],
    ) -> LLMLoopResult:
        """Обработать tool_calls для LLM loop.
        
        Для каждого tool call:
        1. Создать tool call state
        2. Проверить decision (allow/reject/ask)
        3. Если allow - выполнить и собрать результат
        4. Если reject - добавить error result
        5. Если ask - прервать loop для permission request
        
        Args:
            session: Состояние сессии
            session_id: ID сессии
            tool_calls: Список tool_calls из AgentResponse
            notifications: Список для накопления notifications
            
        Returns:
            LLMLoopResult с tool_results и флагом pending_permission
        """
        tool_results: list[ToolResult] = []
        
        for tool_call in tool_calls:
            # CHECK: cancel перед каждым tool
            if self._is_cancel_requested(session):
                logger.debug(
                    "tool processing cancelled",
                    session_id=session_id,
                )
                return LLMLoopResult(
                    tool_results=tool_results,
                    stop_reason="cancelled",
                )
            
            tool_name = getattr(tool_call, "name", None)
            tool_arguments = getattr(tool_call, "arguments", {})
            tool_call_id_from_llm = getattr(tool_call, "id", None)
            
            if not tool_name:
                logger.warning("tool_call has no name", session_id=session_id)
                continue
            
            # Определить kind из ToolDefinition
            tool_kind = "other"
            tool_definition = self.tool_registry.get(tool_name)
            if tool_definition is not None:
                tool_kind = tool_definition.kind
            
            # Создать tool call в сессии
            tool_call_id = self.tool_call_handler.create_tool_call(
                session=session,
                title=tool_name,
                kind=tool_kind,
                tool_name=tool_name,
                tool_arguments=tool_arguments,
                tool_call_id_from_llm=tool_call_id_from_llm,
            )
            
            # Notification о создании tool_call
            notifications.append(
                self.tool_call_handler.build_tool_call_notification(
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    title=tool_name,
                    kind=tool_kind,
                )
            )
            
            # Сохранить tool_call в events_history для replay при session/load
            self.replay_manager.save_tool_call(
                session=session,
                tool_call_id=tool_call_id,
                title=tool_name,
                kind=tool_kind,
                status="pending",
            )
            
            # Проверить requires_permission из tool_definition
            # Если tool не требует permission (например update_plan), сразу разрешить
            if tool_definition is not None and not tool_definition.requires_permission:
                logger.debug(
                    "tool does not require permission, auto-allowing",
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_kind=tool_kind,
                )
                decision = "allow"
            else:
                # Применить decision logic
                decision = await self._decide_tool_execution(session, tool_kind)
            
            if decision == "ask":
                # Запросить разрешение - прервать loop
                tool_call_state = session.tool_calls.get(tool_call_id)
                if tool_call_state is not None:
                    permission_msg = self.permission_manager.build_permission_request(
                        session,
                        session_id,
                        tool_call_state.tool_call_id,
                        tool_call_state.title,
                        tool_kind,
                    )
                    notifications.append(permission_msg)
                    
                    # Перейти в фазу awaiting_permission
                    if session.active_turn:
                        session.active_turn.phase = "awaiting_permission"
                        session.active_turn.permission_tool_call_id = tool_call_id
                
                logger.debug(
                    "permission request sent, pausing llm loop",
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                )
                return LLMLoopResult(
                    tool_results=tool_results,
                    pending_permission=True,
                )
            
            if decision == "reject":
                # Отклонить tool
                self.tool_call_handler.update_tool_call_status(session, tool_call_id, "failed")
                rejection_msg = f"Tool execution rejected by policy for {tool_kind}"
                rejection_content = [
                    {"type": "content", "content": {"type": "text", "text": rejection_msg}}
                ]
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="failed",
                        content=rejection_content,
                    )
                )
                # Сохранить tool_call_update в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status="failed",
                    content=rejection_content,
                )
                # Добавить error result для LLM
                tool_results.append(ToolResult(
                    tool_call_id=tool_call_id_from_llm or tool_call_id,
                    tool_name=tool_name,
                    success=False,
                    error=rejection_msg,
                ))
                continue
            
            # decision == "allow" - выполнить tool
            try:
                # Notification о начале выполнения
                self.tool_call_handler.update_tool_call_status(session, tool_call_id, "in_progress")
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="in_progress",
                    )
                )
                # Сохранить in_progress в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status="in_progress",
                )
                
                # Выполнить tool
                result = await self.tool_registry.execute_tool(
                    session_id,
                    tool_name,
                    tool_arguments,
                    session=session,
                )
                
                # Извлечь content
                extracted_content = await self.content_extractor.extract_from_result(
                    tool_call_id, result
                )
                
                # Валидировать content
                is_valid, errors = self.content_validator.validate_content_list(
                    extracted_content.content_items
                )
                if not is_valid:
                    logger.warning(
                        "tool_result_content_validation_failed",
                        tool_call_id=tool_call_id,
                        errors=errors,
                    )
                
                # Сохранить content в tool call state
                tool_call_state = session.tool_calls.get(tool_call_id)
                if tool_call_state:
                    tool_call_state.result_content = extracted_content.content_items
                
                # Форматировать для LLM
                provider_raw = session.config_values.get("llm_provider", "openai")
                provider = cast(Literal["openai", "anthropic"], provider_raw)
                self.content_formatter.format_for_llm(extracted_content, provider=provider)
                
                # Обновить статус
                if result.success:
                    success_text = result.output or "Success"
                    success_content = [
                        {"type": "content", "content": {"type": "text", "text": success_text}}
                    ]
                    self.tool_call_handler.update_tool_call_status(
                        session, tool_call_id, "completed", content=success_content,
                    )
                    status = "completed"
                else:
                    self.tool_call_handler.update_tool_call_status(session, tool_call_id, "failed")
                    status = "failed"
                
                # Notification об окончании
                notification_content = None
                if result.success and result.output:
                    notification_content = [
                        {"type": "content", "content": {"type": "text", "text": result.output}}
                    ]
                
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status=status,
                        content=notification_content,
                    )
                )
                # Сохранить completed/failed в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status=status,
                    content=notification_content,
                )
                
                # Собрать ToolResult для LLM
                tool_results.append(ToolResult(
                    tool_call_id=tool_call_id_from_llm or tool_call_id,
                    tool_name=tool_name,
                    success=result.success,
                    output=result.output if result.success else None,
                    error=result.error if not result.success else None,
                ))
                
            except Exception as e:
                logger.error(
                    "tool execution failed",
                    session_id=session_id,
                    tool_name=tool_name,
                    error=str(e),
                )
                self.tool_call_handler.update_tool_call_status(session, tool_call_id, "failed")
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="failed",
                    )
                )
                # Сохранить failed в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status="failed",
                )
                # Добавить error result для LLM
                tool_results.append(ToolResult(
                    tool_call_id=tool_call_id_from_llm or tool_call_id,
                    tool_name=tool_name,
                    success=False,
                    error=str(e),
                ))
        
        return LLMLoopResult(tool_results=tool_results)

    async def execute_pending_tool(
        self,
        session: SessionState,
        session_id: str,
        tool_call_id: str,
        agent_orchestrator: AgentOrchestrator,
    ) -> LLMLoopResult:
        """Выполняет pending tool после permission approval и продолжает LLM loop.
        
        Этот метод вызывается из http_server.py когда permission был одобрен.
        Согласно ACP протоколу (05-Prompt Turn.md, Step 6 - Continue Conversation):
        1. Получает данные tool call из сессии
        2. Выполняет tool через tool_registry (который вызывает ClientRPC fs/*)
        3. Отправляет tool_call_update с completed/failed статусом
        4. Продолжает LLM loop с результатами инструмента
        
        Args:
            session: Состояние сессии
            session_id: ID сессии
            tool_call_id: ID tool call для выполнения
            agent_orchestrator: Оркестратор агента для LLM loop
            
        Returns:
            LLMLoopResult с notifications, stop_reason и pending_permission флагом
        """
        notifications: list[ACPMessage] = []
        tool_result: ToolResult | None = None
        
        # Получить tool call state
        tool_call_state = session.tool_calls.get(tool_call_id)
        if tool_call_state is None:
            logger.error(
                "tool_call_state not found for pending execution",
                session_id=session_id,
                tool_call_id=tool_call_id,
            )
            return LLMLoopResult(
                notifications=notifications,
                stop_reason="end_turn",
            )
        
        tool_name = tool_call_state.tool_name
        tool_arguments = tool_call_state.tool_arguments
        # Получить tool_call_id из LLM (если есть) для правильной связки в истории
        tool_call_id_from_llm = tool_call_state.tool_call_id_from_llm
        
        if tool_name is None:
            logger.error(
                "tool_name not found in tool_call_state",
                session_id=session_id,
                tool_call_id=tool_call_id,
            )
            return LLMLoopResult(
                notifications=notifications,
                stop_reason="end_turn",
            )
        
        logger.info(
            "executing pending tool after permission approval",
            session_id=session_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        
        try:
            # Выполнить tool через tool_registry (вызывает ClientRPC fs/* методы)
            result = await self.tool_registry.execute_tool(
                session_id,
                tool_name,
                tool_arguments,
                session=session,
            )
            
            # Извлечь и отформатировать content из result
            extracted_content = await self.content_extractor.extract_from_result(
                tool_call_id, result
            )
            tool_call_state.result_content = extracted_content.content_items
            
            # Форматировать для LLM
            provider_raw = session.config_values.get("llm_provider", "openai")
            provider = cast(Literal["openai", "anthropic"], provider_raw)
            self.content_formatter.format_for_llm(extracted_content, provider=provider)
            
            # Сформировать content для notification и ToolResult
            if result.success:
                completed_content = [
                    {
                        "type": "content",
                        "content": {
                            "type": "text",
                            "text": result.output or "Tool executed successfully",
                        },
                    }
                ]
                self.tool_call_handler.update_tool_call_status(
                    session, tool_call_id, "completed", content=completed_content
                )
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="completed",
                        content=completed_content,
                    )
                )
                # Сохранить completed в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status="completed",
                    content=completed_content,
                )
                # Создать ToolResult для LLM loop
                tool_result = ToolResult(
                    tool_call_id=tool_call_id_from_llm or tool_call_id,
                    tool_name=tool_name,
                    success=True,
                    output=result.output,
                )
            else:
                error_content = [
                    {
                        "type": "content",
                        "content": {
                            "type": "text",
                            "text": result.error or "Tool execution failed",
                        },
                    }
                ]
                self.tool_call_handler.update_tool_call_status(
                    session, tool_call_id, "failed", content=error_content
                )
                notifications.append(
                    self.tool_call_handler.build_tool_update_notification(
                        session_id=session_id,
                        tool_call_id=tool_call_id,
                        status="failed",
                        content=error_content,
                    )
                )
                # Сохранить failed в events_history для replay
                self.replay_manager.save_tool_call_update(
                    session=session,
                    tool_call_id=tool_call_id,
                    status="failed",
                    content=error_content,
                )
                # Создать ToolResult с ошибкой для LLM loop
                tool_result = ToolResult(
                    tool_call_id=tool_call_id_from_llm or tool_call_id,
                    tool_name=tool_name,
                    success=False,
                    error=result.error,
                )
                
        except Exception as exc:
            logger.error(
                "tool execution failed with exception",
                session_id=session_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                error=str(exc),
                exc_info=True,
            )
            error_content = [
                {
                    "type": "content",
                    "content": {
                        "type": "text",
                        "text": f"Tool execution error: {exc}",
                    },
                }
            ]
            self.tool_call_handler.update_tool_call_status(
                session, tool_call_id, "failed", content=error_content
            )
            notifications.append(
                self.tool_call_handler.build_tool_update_notification(
                    session_id=session_id,
                    tool_call_id=tool_call_id,
                    status="failed",
                    content=error_content,
                )
            )
            # Сохранить failed в events_history для replay
            self.replay_manager.save_tool_call_update(
                session=session,
                tool_call_id=tool_call_id,
                status="failed",
                content=error_content,
            )
            # Создать ToolResult с exception для LLM loop
            tool_result = ToolResult(
                tool_call_id=tool_call_id_from_llm or tool_call_id,
                tool_name=tool_name,
                success=False,
                error=str(exc),
            )
        
        # Продолжить LLM loop с результатом выполненного tool
        # (согласно ACP протоколу 05-Prompt Turn.md, Step 6 - Continue Conversation)
        if tool_result is not None:
            logger.info(
                "continuing LLM loop after pending tool execution",
                session_id=session_id,
                tool_call_id=tool_call_id,
                tool_success=tool_result.success,
            )
            
            # Запустить LLM loop с результатом инструмента
            llm_loop_result = await self._run_llm_loop(
                session=session,
                session_id=session_id,
                agent_orchestrator=agent_orchestrator,
                initial_prompt_text="",  # Не нужен текст - используем tool_results
                tool_results=[tool_result],
            )
            
            # Объединить notifications
            all_notifications = notifications + llm_loop_result.notifications
            
            return LLMLoopResult(
                notifications=all_notifications,
                stop_reason=llm_loop_result.stop_reason,
                final_text=llm_loop_result.final_text,
                pending_permission=llm_loop_result.pending_permission,
                pending_tool_calls=llm_loop_result.pending_tool_calls,
                tool_results=llm_loop_result.tool_results,
            )
        
        # Если tool_result не создан (не должно происходить), завершить turn
        return LLMLoopResult(
            notifications=notifications,
            stop_reason="end_turn",
        )


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
