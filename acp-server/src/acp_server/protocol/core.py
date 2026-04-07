"""Основной класс протокола ACP.

Содержит реализацию класса ACPProtocol с основной логикой обработки
запросов клиента и управления сессиями.
"""

from __future__ import annotations

from typing import Any

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
from .state import (
    ClientRuntimeCapabilities,
    ProtocolOutcome,
    SessionState,
)


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
    ) -> None:
        """Инициализирует протокол и хранилище сессий.

        Args:
            require_auth: Требовать аутентификацию перед session setup.
            auth_api_key: API ключ для аутентификации.
            storage: Хранилище сессий (по умолчанию InMemoryStorage).

        Пример использования:
            protocol = ACPProtocol()
            # или с кастомным хранилищем:
            from acp_server.storage import InMemoryStorage
            storage = InMemoryStorage()
            protocol = ACPProtocol(storage=storage)
        """

        # Инициализировать хранилище (по умолчанию InMemoryStorage)
        if storage is None:
            from ..storage import InMemoryStorage
            storage = InMemoryStorage()
        self._storage = storage
        # Внутренний кэш сессий для совместимости с handlers
        self._sessions: dict[str, SessionState] = {}
        
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
            # Проверяем требования auth
            if self._require_auth and not self._authenticated:
                from .handlers.auth import auth_required_error
                return ProtocolOutcome(
                    response=auth_required_error(message.id, self._auth_methods)
                )

            # Валидируем параметры и создаем сессию
            from pathlib import Path
            from uuid import uuid4

            cwd = params.get("cwd")
            if not isinstance(cwd, str) or not Path(cwd).is_absolute():
                return ProtocolOutcome(
                    response=ACPMessage.error_response(
                        message.id,
                        code=-32602,
                        message="Invalid params: cwd must be an absolute path",
                    )
                )

            mcp_servers = params.get("mcpServers", [])
            if not isinstance(mcp_servers, list):
                return ProtocolOutcome(
                    response=ACPMessage.error_response(
                        message.id,
                        code=-32602,
                        message="Invalid params: mcpServers must be an array",
                    )
                )

            # Создаем сессию
            session_id = f"sess_{uuid4().hex[:12]}"
            config_values = {
                config_id: str(spec["default"]) 
                for config_id, spec in self._config_specs.items()
            }

            session_state = SessionState(
                session_id=session_id,
                cwd=cwd,
                mcp_servers=[srv for srv in mcp_servers if isinstance(srv, dict)],
                config_values=config_values,
                available_commands=session.build_default_commands(),
                runtime_capabilities=self._runtime_capabilities,
            )
            await self._storage.save_session(session_state)
            # Обновляем внутренний кэш для синхронной работы handlers
            self._sessions[session_id] = session_state

            return ProtocolOutcome(
                response=ACPMessage.response(
                    message.id,
                    {
                        "sessionId": session_id,
                        "configOptions": session.build_config_options(
                            config_values, self._config_specs
                        ),
                        "modes": session.build_modes_state(
                            config_values, self._config_specs
                        ),
                    },
                )
            )

        if method == "session/load":
            # Обновляем runtime capabilities при загрузке сессии
            session_id = params.get("sessionId")
            if isinstance(session_id, str):
                session_obj = self._sessions.get(session_id)
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
            return ProtocolOutcome(
                response=session.session_list(
                    message.id,
                    params,
                    self._sessions,
                    self._session_list_page_size,
                )
            )

        if method == "session/prompt":
            return prompt.session_prompt(
                message.id,
                params,
                self._sessions,
                self._config_specs,
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
