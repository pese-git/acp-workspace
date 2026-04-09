"""WebSocket транспортный слой для ACP-клиента.

Содержит классы и функции для работы с WebSocket соединениями:
- Управление persistent WS-сессиями
- Отправка/получение сообщений
- Обработка асинхронных ответов и RPC запросов от сервера
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiohttp import ClientSession, WSMsgType

from ..handlers import (
    build_permission_result,
    handle_server_fs_request,
    handle_server_terminal_request,
)
from ..messages import (
    ACPMessage,
    AuthenticateResult,
    InitializeResult,
    parse_authenticate_result,
    parse_initialize_result,
    parse_request_permission_request,
)

type PermissionHandler = Callable[[dict[str, Any]], str | None | Awaitable[str | None]]
type FsReadHandler = Callable[[str], str]
type FsWriteHandler = Callable[[str, str], str | None]
type TerminalCreateHandler = Callable[[str], str]
type TerminalOutputHandler = Callable[[str], str]
type TerminalWaitHandler = Callable[[str], int | tuple[int | None, str | None]]
type TerminalReleaseHandler = Callable[[str], None]
type TerminalKillHandler = Callable[[str], bool]


async def await_ws_response(
    *,
    ws: Any,
    request_id: Any,
    on_update: Callable[[dict], None] | None,
    on_permission: PermissionHandler | None,
    on_fs_read: FsReadHandler | None,
    on_fs_write: FsWriteHandler | None,
    on_terminal_create: TerminalCreateHandler | None,
    on_terminal_output: TerminalOutputHandler | None,
    on_terminal_wait_for_exit: TerminalWaitHandler | None,
    on_terminal_release: TerminalReleaseHandler | None,
    on_terminal_kill: TerminalKillHandler | None,
) -> ACPMessage:
    """Ждет финальный response для request ID и обрабатывает server RPC.

    Функция в цикле читает сообщения из WebSocket, обрабатывает:
    - session/update события (передает в on_update callback)
    - session/request_permission запросы (отправляет ответ)
    - session/fs_* и session/terminal_* запросы от сервера
    - Финальный JSON-RPC response с matching request_id

    Пример использования:
        response = await await_ws_response(
            ws=ws,
            request_id="req_1",
            on_update=updates.append,
            on_permission=handle_permission,
            ...
        )
    """

    logger = structlog.get_logger("acp_client.ws_response")
    
    while True:
        # Получаем сообщение из WebSocket
        message = await ws.receive()
        if message.type != WSMsgType.TEXT:
            # Логируем неожиданный тип сообщения для отладки disconnect проблем
            logger.error("unexpected_ws_message_type", type=str(message.type), expected="TEXT")
            msg = f"Unexpected WebSocket response type: {message.type}"
            raise RuntimeError(msg)

        # Парсим JSON payload
        payload = json.loads(message.data)
        logger.debug("ws_recv_payload", payload=payload)
        raw_method = payload.get("method") if isinstance(payload, dict) else None

        # Обрабатываем session/update события (промежуточные уведомления)
        if raw_method == "session/update":
            if on_update is not None:
                on_update(payload)
            continue

        # Обрабатываем session/request_permission запросы
        permission_request = None
        if isinstance(payload, dict):
            permission_request = parse_request_permission_request(payload)
        if permission_request is not None:
            permission_result = await build_permission_result(
                payload=payload,
                on_permission=on_permission,
            )
            await ws.send_str(
                ACPMessage.response(permission_request.id, permission_result).to_json()
            )
            continue

        # Обрабатываем session/fs_* запросы от сервера
        handled_fs_request = handle_server_fs_request(
            payload=payload,
            on_fs_read=on_fs_read,
            on_fs_write=on_fs_write,
        )
        if handled_fs_request is not None:
            await ws.send_str(handled_fs_request.to_json())
            continue

        # Обрабатываем session/terminal_* запросы от сервера
        handled_terminal_request = handle_server_terminal_request(
            payload=payload,
            on_terminal_create=on_terminal_create,
            on_terminal_output=on_terminal_output,
            on_terminal_wait_for_exit=on_terminal_wait_for_exit,
            on_terminal_release=on_terminal_release,
            on_terminal_kill=on_terminal_kill,
        )
        if handled_terminal_request is not None:
            await ws.send_str(handled_terminal_request.to_json())
            continue

        # Если это финальный response для нашего request - возвращаем
        response = ACPMessage.from_dict(payload)
        if response.id != request_id:
            continue
        return response


async def perform_ws_initialize(
    ws: Any,
    client_capabilities: dict[str, Any],
) -> InitializeResult:
    """Выполняет ACP initialize в открытом WS-соединении.

    Функция нужна для соблюдения handshake-фазы протокола перед вызовом
    `session/*` методов в рамках того же WS-канала.

    Пример использования:
        init_result = await perform_ws_initialize(ws, client_caps)
    """

    init_request = ACPMessage.request(
        method="initialize",
        params={
            "protocolVersion": 1,
            "clientCapabilities": client_capabilities,
        },
    )
    await ws.send_str(init_request.to_json())

    while True:
        message = await ws.receive()
        if message.type != WSMsgType.TEXT:
            # Логируем неожиданный тип сообщения при инициализации
            logger = structlog.get_logger("acp_client.ws_initialize")
            logger.error(
                "unexpected_ws_message_type_in_initialize",
                type=str(message.type),
                expected="TEXT",
            )
            msg = f"Unexpected WebSocket response type during initialize: {message.type}"
            raise RuntimeError(msg)

        payload = json.loads(message.data)
        raw_method = payload.get("method") if isinstance(payload, dict) else None

        # Инициализация не должна блокироваться на update-событиях
        if raw_method == "session/update":
            continue

        response = ACPMessage.from_dict(payload)
        if response.id != init_request.id:
            continue
        if response.error is not None:
            msg = f"WebSocket initialize failed: {response.error.code} {response.error.message}"
            raise RuntimeError(msg)
        return parse_initialize_result(response)


async def perform_ws_authenticate(
    ws: Any,
    *,
    method_id: str,
    api_key: str | None = None,
) -> AuthenticateResult:
    """Выполняет ACP `authenticate` в открытом WS-соединении.

    Пример использования:
        auth_result = await perform_ws_authenticate(
            ws,
            method_id="local",
            api_key="secret_key"
        )
    """

    auth_params: dict[str, Any] = {"methodId": method_id}
    if isinstance(api_key, str) and api_key:
        auth_params["apiKey"] = api_key

    auth_request = ACPMessage.request(
        method="authenticate",
        params=auth_params,
    )
    await ws.send_str(auth_request.to_json())

    while True:
        message = await ws.receive()
        if message.type != WSMsgType.TEXT:
            # Логируем неожиданный тип сообщения при аутентификации
            logger = structlog.get_logger("acp_client.ws_authenticate")
            logger.error(
                "unexpected_ws_message_type_in_authenticate",
                type=str(message.type),
                expected="TEXT",
            )
            msg = f"Unexpected WebSocket response type during authenticate: {message.type}"
            raise RuntimeError(msg)

        payload = json.loads(message.data)
        raw_method = payload.get("method") if isinstance(payload, dict) else None

        # Пропускаем update-события во время аутентификации
        if raw_method == "session/update":
            continue

        response = ACPMessage.from_dict(payload)
        if response.id != auth_request.id:
            continue
        if response.error is not None:
            msg = f"WebSocket authenticate failed: {response.error.code} {response.error.message}"
            raise RuntimeError(msg)
        return parse_authenticate_result(response)


class ACPClientWSSession:
    """Persistent WebSocket-сессия для последовательных ACP-запросов.

    Класс управляет жизненным циклом WebSocket соединения и предоставляет
    методы для отправки ACP-запросов в рамках одной сессии.

    Пример использования:
        async with ACPClientWSSession(client) as ws_session:
            await ws_session.request("session/list", params={})
    """

    def __init__(self, client: Any) -> None:
        """Создает объект persistent-сессии поверх переданного ACPClient.

        Пример использования:
            ws_session = ACPClientWSSession(client)
        """

        self._client = client
        self._http_session: ClientSession | None = None
        self._ws: Any | None = None
        self._initialized = False
        self.logger = structlog.get_logger("acp_client.ws_session")

    async def __aenter__(self) -> ACPClientWSSession:
        """Открывает WS-соединение и возвращает текущий session-object.

        Пример использования:
            async with client.open_ws_session() as ws_session:
                ...
        """

        url = f"ws://{self._client.host}:{self._client.port}/acp/ws"
        self._http_session = ClientSession()
        self._ws = await self._http_session.ws_connect(url)
        self.logger.debug("ws_connection_opened", url=url)
        return self

    async def __aexit__(self, *_: object) -> None:
        """Закрывает WS и HTTP-сессию независимо от результата операций.

        Пример использования:
            await ws_session.__aexit__(None, None, None)
        """

        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._http_session is not None:
            await self._http_session.close()
            self._http_session = None
        self._initialized = False
        self.logger.debug("ws_connection_closed")

    async def request(
        self,
        method: str,
        params: dict | None = None,
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> ACPMessage:
        """Отправляет ACP-запрос в рамках открытой persistent WS-сессии.

        Метод автоматически выполняет handshake (initialize + authenticate)
        для session/* методов перед первым запросом.

        Пример использования:
            response = await ws_session.request("session/list", params={})
        """

        if self._ws is None:
            # Логируем попытку отправки запроса при закрытой сессии
            self.logger.error("websocket_session_not_opened", method=method)
            raise RuntimeError("WebSocket session is not opened")

        # Для session/* методов требуется handshake (инициализация и аутентификация)
        should_initialize = method.startswith("session/") and method != "initialize"
        if should_initialize and not self._initialized:
            # Выполняем initialize handshake
            init_result = await perform_ws_initialize(
                self._ws,
                self._client._default_client_capabilities(),
            )

            # Выполняем auto-authenticate если включен
            if self._client.auto_authenticate:
                from ..helpers import pick_auth_method_id

                selected_auth_method = pick_auth_method_id(
                    init_result,
                    self._client.preferred_auth_method_id,
                )
                if selected_auth_method is not None:
                    await perform_ws_authenticate(
                        self._ws,
                        method_id=selected_auth_method,
                        api_key=self._client.auth_api_key,
                    )
            self._initialized = True

        # Отправляем запрос
        request = ACPMessage.request(method=method, params=params)
        request_json = request.to_json()
        self.logger.debug("ws_send_payload", payload=json.loads(request_json), method=method)
        await self._ws.send_str(request_json)

        # Ждем ответ (обрабатывая промежуточные события)
        response = await await_ws_response(
            ws=self._ws,
            request_id=request.id,
            on_update=on_update,
            on_permission=on_permission,
            on_fs_read=on_fs_read,
            on_fs_write=on_fs_write,
            on_terminal_create=on_terminal_create,
            on_terminal_output=on_terminal_output,
            on_terminal_wait_for_exit=on_terminal_wait_for_exit,
            on_terminal_release=on_terminal_release,
            on_terminal_kill=on_terminal_kill,
        )

        # Если это initialize - отмечаем инициализацию
        if method == "initialize" and response.error is None:
            self._initialized = True

        return response

    async def authenticate(
        self, *, method_id: str, api_key: str | None = None
    ) -> AuthenticateResult:
        """Выполняет `authenticate` в рамках persistent WS-сессии.

        Пример использования:
            await ws_session.authenticate(method_id="local")
        """

        from ..messages import parse_authenticate_result

        response = await self.request(
            method="authenticate",
            params={
                "methodId": method_id,
                **(
                    {"apiKey": api_key}
                    if isinstance(api_key, str) and api_key
                    else (
                        {"apiKey": self._client.auth_api_key}
                        if isinstance(self._client.auth_api_key, str) and self._client.auth_api_key
                        else {}
                    )
                ),
            },
        )
        return parse_authenticate_result(response)

    async def prompt(
        self,
        *,
        session_id: str,
        prompt: list[dict[str, Any]],
        prompt_directives: dict[str, Any] | None = None,
        on_update: Callable[[dict], None] | None = None,
        on_permission: PermissionHandler | None = None,
        on_fs_read: FsReadHandler | None = None,
        on_fs_write: FsWriteHandler | None = None,
        on_terminal_create: TerminalCreateHandler | None = None,
        on_terminal_output: TerminalOutputHandler | None = None,
        on_terminal_wait_for_exit: TerminalWaitHandler | None = None,
        on_terminal_release: TerminalReleaseHandler | None = None,
        on_terminal_kill: TerminalKillHandler | None = None,
    ) -> Any:
        """Выполняет `session/prompt` в persistent WS и парсит stop reason.

        Пример использования:
            result = await ws_session.prompt(
                session_id="sess_1",
                prompt=[{"type": "text", "text": "build plan"}],
                prompt_directives={"publishPlan": True},
            )
        """

        from ..messages import parse_prompt_result

        params: dict[str, Any] = {
            "sessionId": session_id,
            "prompt": prompt,
        }
        if isinstance(prompt_directives, dict) and prompt_directives:
            params["_meta"] = {
                "promptDirectives": prompt_directives,
            }

        response = await self.request(
            method="session/prompt",
            params=params,
            on_update=on_update,
            on_permission=on_permission,
            on_fs_read=on_fs_read,
            on_fs_write=on_fs_write,
            on_terminal_create=on_terminal_create,
            on_terminal_output=on_terminal_output,
            on_terminal_wait_for_exit=on_terminal_wait_for_exit,
            on_terminal_release=on_terminal_release,
            on_terminal_kill=on_terminal_kill,
        )
        return parse_prompt_result(response)
