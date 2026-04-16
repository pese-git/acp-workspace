"""Основной класс протокола ACP.

Содержит реализацию класса ACPProtocol с основной логикой обработки
запросов клиента и управления сессиями.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from ..messages import ACPMessage, JsonRpcId
from ..storage import SessionStorage
from .handlers import (
    auth,
    config,
    legacy,
    permissions,
    prompt,
    session,
)
from .session_factory import SessionFactory
from .state import (
    ClientRuntimeCapabilities,
    ProtocolOutcome,
    SessionState,
)

if TYPE_CHECKING:
    from ..agent.orchestrator import AgentOrchestrator
    from ..client_rpc.service import ClientRPCService
    from ..tools.base import ToolRegistry
    from .handlers.global_policy_manager import GlobalPolicyManager


logger = structlog.get_logger()


class ACPProtocol:
    """Диспетчер ACP-методов и in-memory реализация сессионного протокола.

    Класс принимает валидированные JSON-RPC сообщения и возвращает
    `ProtocolOutcome` для транспортного слоя.

    Пример использования:
        protocol = ACPProtocol()
        outcome = protocol.handle(ACPMessage.request("initialize", {}))
    """

    def __init__(
        self,
        *,
        require_auth: bool = False,
        auth_api_key: str | None = None,
        storage: SessionStorage | None = None,
        agent_orchestrator: AgentOrchestrator | None = None,
        client_rpc_service: ClientRPCService | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        """Инициализирует протокол и хранилище сессий.

        Args:
            require_auth: Требовать аутентификацию перед session setup.
            auth_api_key: API ключ для аутентификации.
            storage: Хранилище сессий (по умолчанию InMemoryStorage).
            agent_orchestrator: Оркестратор LLM-агента для обработки prompts (опционально).
            client_rpc_service: Сервис ClientRPC для выполнения инструментов (опционально).
            tool_registry: Реестр инструментов для регистрации и выполнения tools (опционально).

        Пример использования:
            protocol = ACPProtocol()
            # или с кастомным хранилищем и агентом:
            from acp_server.storage import InMemoryStorage
            from acp_server.agent.orchestrator import AgentOrchestrator
            storage = InMemoryStorage()
            agent = AgentOrchestrator(...)
            protocol = ACPProtocol(storage=storage, agent_orchestrator=agent)
        """

        # Инициализировать хранилище (по умолчанию InMemoryStorage)
        if storage is None:
            from ..storage import InMemoryStorage

            storage = InMemoryStorage()
        self._storage = storage
        # Внутренний кэш сессий для совместимости с handlers
        self._sessions: dict[str, SessionState] = {}

        # Оркестратор LLM-агента для обработки prompt-turns через агента
        self._agent_orchestrator = agent_orchestrator

        # Сервис ClientRPC для выполнения встроенных инструментов
        self._client_rpc_service = client_rpc_service

        # Реестр инструментов для регистрации и выполнения tools
        self._tool_registry = tool_registry

        # GlobalPolicyManager для fallback chain в permission checks
        self._global_policy_manager: GlobalPolicyManager | None = None

        # Последние capabilities, согласованные через initialize.
        # Для in-memory demo-сервера это достаточно; по мере роста можно
        # расширить до connection-scoped хранилища.
        self._runtime_capabilities: ClientRuntimeCapabilities | None = None
        # Флаг для сценариев, где агент требует authenticate до session setup.
        self._require_auth = require_auth
        # Локальный API key для production-профиля authenticate (если задан).
        self._auth_api_key = auth_api_key
        # Состояние аутентификации текущего протокольного инстанса.
        self._authenticated = False
        self._auth_methods: list[dict[str, Any]] = [
            {
                "id": "local",
                "name": "Local authentication",
                "description": "Local authentication flow",
                "type": "api_key",
            }
        ]

    _config_specs: dict[str, dict[str, Any]] = {
        "mode": {
            "name": "Session Mode",
            "category": "mode",
            "default": "ask",
            "options": [
                {
                    "value": "ask",
                    "name": "Ask",
                    "description": "Request permission before sensitive actions",
                },
                {
                    "value": "code",
                    "name": "Code",
                    "description": "Execute actions without per-step approval",
                },
            ],
        },
        "model": {
            "name": "Model",
            "category": "model",
            "default": "baseline",
            "options": [
                {
                    "value": "baseline",
                    "name": "Baseline",
                    "description": "Balanced speed and quality",
                }
            ],
        },
    }
    _supported_protocol_versions = (1,)
    _supported_stop_reasons = {
        "end_turn",
        "max_tokens",
        "max_turn_requests",
        "refusal",
        "cancelled",
    }
    _supported_tool_kinds = {
        "read",
        "edit",
        "delete",
        "move",
        "search",
        "execute",
        "think",
        "fetch",
        "switch_mode",
        "other",
    }
    # Размер страницы для `session/list`; cursor указывает смещение в этом срезе.
    _session_list_page_size = 50

    async def handle(self, message: ACPMessage) -> ProtocolOutcome:
        """Обрабатывает входящее сообщение и маршрутизирует его по ACP-методу.

        Метод является основной точкой входа для HTTP/WS транспорта.

        Пример использования:
            outcome = protocol.handle(ACPMessage.request("session/list", {}))
        """

        # Сервер принимает только входящие requests/notifications.
        if message.method is None:
            return ProtocolOutcome(
                response=ACPMessage.error_response(
                    message.id,
                    code=-32600,
                    message="Invalid request: unexpected response payload",
                )
            )

        method = message.method
        params = message.params or {}

        # Явный диспетчер методов упрощает проверку протокольных веток.
        if method == "initialize":
            response = auth.initialize(
                message.id,
                params,
                self._supported_protocol_versions,
                self._require_auth,
                self._auth_methods,
            )
            # Сохраняем согласованные runtime-возможности клиента для feature-gate.
            client_capabilities = params.get("clientCapabilities")
            if isinstance(client_capabilities, dict):
                self._runtime_capabilities = auth.parse_client_runtime_capabilities(
                    client_capabilities
                )
            
            # Инициализируем GlobalPolicyManager для fallback chain
            if self._global_policy_manager is None:
                # Вопрос: как инициализировать асинхронный менеджер в синхронном контексте?
                # Решение: не инициализируем здесь, а передаем None (graceful degradation)
                # GlobalPolicyManager требует async инициализации и singleton pattern
                logger.debug("GlobalPolicyManager will be initialized on demand")
            
            return ProtocolOutcome(response=response)

        if method == "authenticate":
            response, authenticated = auth.authenticate(
                message.id,
                params,
                self._require_auth,
                self._auth_api_key,
                self._auth_methods,
            )
            self._authenticated = authenticated
            return ProtocolOutcome(response=response)

        if method == "session/new":
            # Используем обработчик из handlers для валидации и создания ответа
            response_msg = session.session_new(
                message.id,
                params,
                self._require_auth,
                self._authenticated,
                self._config_specs,
                self._auth_methods,
                self._runtime_capabilities,
            )

            # Если создание прошло успешно, сохраняем в storage и кэш
            if response_msg.result is not None:
                session_id = response_msg.result.get("sessionId")
                if isinstance(session_id, str):
                    # Создаем сессию через фабрику для сохранения
                    config_values = {
                        config_id: str(spec["default"])
                        for config_id, spec in self._config_specs.items()
                    }
                    session_state = SessionFactory.create_session(
                        cwd=params.get("cwd", ""),
                        mcp_servers=params.get("mcpServers", []),
                        config_values=config_values,
                        available_commands=session.build_default_commands(),
                        runtime_capabilities=self._runtime_capabilities,
                        session_id=session_id,
                    )
                    await self._storage.save_session(session_state)
                    # Обновляем внутренний кэш для синхронной работы handlers
                    self._sessions[session_id] = session_state

            return ProtocolOutcome(response=response_msg)

        if method == "session/load":
            # Обновляем runtime capabilities при загрузке сессии
            session_id = params.get("sessionId")
            if isinstance(session_id, str):
                session_obj = await self._get_session_for_runtime(session_id)
                if session_obj is not None:
                    session_obj.runtime_capabilities = self._runtime_capabilities
            return session.session_load(
                message.id,
                params,
                self._require_auth,
                self._authenticated,
                self._config_specs,
                self._auth_methods,
                self._sessions,
            )

        if method == "session/list":
            # Подтягиваем persisted-сессии в кэш, чтобы `session/list` после рестарта
            # не зависел только от in-memory словаря текущего процесса.
            await self._hydrate_session_cache_from_storage()
            return ProtocolOutcome(
                response=session.session_list(
                    message.id,
                    params,
                    self._sessions,
                    self._session_list_page_size,
                )
            )

        if method == "session/prompt":
            return await prompt.session_prompt(
                message.id,
                params,
                self._sessions,
                self._config_specs,
                agent_orchestrator=self._agent_orchestrator,
                storage=self._storage,
                tool_registry=self._tool_registry,
                client_rpc_service=self._client_rpc_service,
                global_manager=self._global_policy_manager,
            )

        if method == "session/cancel":
            return prompt.session_cancel(
                message.id,
                params,
                self._sessions,
            )

        if method == "session/set_config_option":
            return config.session_set_config_option(
                message.id,
                params,
                self._sessions,
                self._config_specs,
            )

        if method == "session/set_mode":
            return config.session_set_mode(
                message.id,
                params,
                self._sessions,
                self._config_specs,
            )

        if method == "ping":
            return ProtocolOutcome(response=legacy.ping(message.id))

        if method == "echo":
            return ProtocolOutcome(response=legacy.echo(message.id, params))

        if method == "shutdown":
            return ProtocolOutcome(response=legacy.shutdown(message.id))

        if message.is_notification:
            return ProtocolOutcome()

        return ProtocolOutcome(
            response=ACPMessage.error_response(
                message.id,
                code=-32601,
                message=f"Method not found: {method}",
            )
        )

    def complete_active_turn(
        self, session_id: str, *, stop_reason: str = "end_turn"
    ) -> ACPMessage | None:
        """Завершает активный prompt-turn и возвращает финальный response.

        Используется транспортом WS для отложенного ответа на `session/prompt`.

        Пример использования:
            response = protocol.complete_active_turn("sess_1", stop_reason="end_turn")
        """

        return prompt.complete_active_turn(
            session_id,
            self._sessions,
            stop_reason=stop_reason,
        )

    def should_auto_complete_active_turn(self, session_id: str) -> bool:
        """Возвращает `True`, если active turn можно безопасно автозавершить.

        Если turn ожидает permission-response, автозавершение запрещено.

        Пример использования:
            if protocol.should_auto_complete_active_turn("sess_1"):
                ...
        """

        return prompt.should_auto_complete_active_turn(session_id, self._sessions)

    def handle_client_response(self, message: ACPMessage) -> ProtocolOutcome:
        """Обрабатывает входящий response от клиента для server-originated requests.

        Сейчас используется для `session/request_permission`, отправленного ранее
        в рамках active prompt-turn.

        Пример использования:
            outcome = protocol.handle_client_response(client_response)
        """

        if message.id is None:
            return ProtocolOutcome()

        resolved_client_rpc = self._resolve_pending_client_rpc_response(
            request_id=message.id,
            result=message.result,
            error=message.error.model_dump(exclude_none=True)
            if message.error is not None
            else None,
        )
        if resolved_client_rpc is not None:
            return resolved_client_rpc

        if self._client_rpc_service is not None and self._client_rpc_service.has_pending_request(
            message.id
        ):
            # Пробрасываем response в ClientRPCService для async-ожиданий,
            # используемых tool executors (filesystem/terminal).
            logger.debug(
                "forwarding client response to client_rpc_service",
                request_id=message.id,
                has_error=message.error is not None,
            )
            self._client_rpc_service.handle_response(message.to_dict())
            return ProtocolOutcome()

        if permissions.consume_cancelled_client_rpc_response(message.id, self._sessions):
            # Late response на отмененный agent->client RPC считаем no-op.
            return ProtocolOutcome()

        if permissions.consume_cancelled_permission_response(message.id, self._sessions):
            # Late response на уже отмененный permission-request считаем
            # корректно обработанным no-op, чтобы избежать race-эффектов.
            return ProtocolOutcome()

        resolved = self._resolve_permission_response(message.id, message.result)
        if resolved is None:
            return ProtocolOutcome()
        return resolved

    def _resolve_pending_client_rpc_response(
        self,
        *,
        request_id: JsonRpcId,
        result: Any,
        error: dict[str, Any] | None,
    ) -> ProtocolOutcome | None:
        """Обрабатывает response на ожидаемый agent->client fs/* request.

        Пример использования:
            outcome = protocol._resolve_pending_client_rpc_response(
                request_id="req_1",
                result={"content": "ok"},
                error=None,
            )
        """

        session = prompt.find_session_by_pending_client_request_id(request_id, self._sessions)
        if session is None:
            return None

        return prompt.resolve_pending_client_rpc_response_impl(
            session=session,
            request_id=request_id,
            result=result,
            error=error,
            sessions=self._sessions,
        )

    def _resolve_permission_response(
        self,
        permission_request_id: JsonRpcId,
        result: Any,
    ) -> ProtocolOutcome | None:
        """Применяет решение по permission-request к активному prompt-turn.

        Пример использования:
            outcome = protocol._resolve_permission_response(
                "perm_1",
                {"outcome": {"outcome": "selected", "optionId": "allow_once"}},
            )
        """

        session = permissions.find_session_by_permission_request_id(
            permission_request_id, self._sessions
        )
        if session is None:
            return None

        return prompt.resolve_permission_response_impl(
            session=session,
            permission_request_id=permission_request_id,
            result=result,
            sessions=self._sessions,
        )

    async def _get_session_for_runtime(self, session_id: str) -> SessionState | None:
        """Возвращает сессию из кэша или подгружает её из storage по id.

        Пример использования:
            session = await protocol._get_session_for_runtime("sess_1")
        """

        cached_session = self._sessions.get(session_id)
        if cached_session is not None:
            return cached_session

        loaded_session = await self._storage.load_session(session_id)
        if loaded_session is not None:
            self._sessions[session_id] = loaded_session
        return loaded_session

    async def _hydrate_session_cache_from_storage(self) -> None:
        """Подгружает все страницы сессий из storage в in-memory кэш.

        Пример использования:
            await protocol._hydrate_session_cache_from_storage()
        """

        cursor: str | None = None
        while True:
            page, next_cursor = await self._storage.list_sessions(
                cursor=cursor,
                limit=self._session_list_page_size,
            )
            for session_state in page:
                self._sessions[session_state.session_id] = session_state
            if next_cursor is None:
                break
            cursor = next_cursor

    async def cancel_active_turns_on_disconnect(self) -> int:
        """Отменяет все активные turn в рамках текущего протокольного инстанса.

        Используется транспортом при разрыве соединения клиента. Метод
        обеспечивает ACP-инвариант остановки in-flight turn и освобождение
        внутренних ожиданий без отправки сетевых сообщений.

        Returns:
            Количество сессий, в которых активный turn был отменен.
        """

        cancelled_count = 0
        for session_id, session_state in list(self._sessions.items()):
            if session_state.active_turn is None:
                continue

            prompt.session_cancel(
                request_id=None,
                params={"sessionId": session_id},
                sessions=self._sessions,
            )
            cancelled_count += 1

            try:
                await self._storage.save_session(self._sessions[session_id])
            except Exception:
                # Ошибка персистентности не должна блокировать cleanup при disconnect.
                continue

        return cancelled_count

    async def initialize_global_policy_manager(self) -> None:
        """Инициализировать GlobalPolicyManager для fallback на global policies.

        Graceful degradation: если инициализация не удалась, продолжаем без global policies.

        Пример использования:
            await protocol.initialize_global_policy_manager()
        """
        try:
            from .handlers.global_policy_manager import GlobalPolicyManager

            self._global_policy_manager = await GlobalPolicyManager.get_instance()
            await self._global_policy_manager.initialize()

            logger.info("GlobalPolicyManager initialized successfully")
        except Exception as e:
            logger.warning(
                "Failed to initialize GlobalPolicyManager, continuing without global policies",
                error=str(e),
                exc_info=True,
            )
            self._global_policy_manager = None
