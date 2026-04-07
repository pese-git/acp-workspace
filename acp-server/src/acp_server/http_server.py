"""WebSocket транспорт ACP-сервера.

Модуль поднимает endpoint `GET /acp/ws` для двустороннего потока с
`session/update` и server->client RPC.

Пример использования:
    server = ACPHttpServer(host="127.0.0.1", port=8080)
    await server.run()
"""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog
from aiohttp import WSMsgType, web

from .messages import ACPMessage
from .protocol import ACPProtocol, ProtocolOutcome
from .storage import SessionStorage

# Получаем структурированный logger
logger = structlog.get_logger()


class ACPHttpServer:
    """Транспортный слой ACP поверх aiohttp (WebSocket-only).

    Класс принимает wire-сообщения, передает их в `ACPProtocol` и отправляет
    обратно response/notifications в правильном порядке.

    Пример использования:
        server = ACPHttpServer(port=8080)
        await server.run()
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        *,
        require_auth: bool = False,
        auth_api_key: str | None = None,
        storage: SessionStorage | None = None,
    ) -> None:
        """Создает транспортный сервер с адресом прослушивания.

        Args:
            host: IP адрес для прослушивания (по умолчанию 127.0.0.1).
            port: Порт для прослушивания (по умолчанию 8080).
            require_auth: Требовать аутентификацию перед session/new и session/load.
            auth_api_key: API ключ для аутентификации.
            storage: Backend для хранения сессий (по умолчанию InMemoryStorage).

        Пример использования:
            ACPHttpServer(host="0.0.0.0", port=8080)
        """

        self.host = host
        self.port = port
        self.require_auth = require_auth
        self.auth_api_key = auth_api_key
        self.storage = storage

    async def run(self) -> None:
        """Запускает WS endpoint и держит процесс живым.

        Пример использования:
            await ACPHttpServer().run()
        """

        app = web.Application()
        app.router.add_get("/acp/ws", self.handle_ws_request)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()
        
        # Логируем запуск сервера
        logger.info(
            "server started",
            host=self.host,
            port=self.port,
            endpoint="/acp/ws",
        )

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            # Логируем остановку сервера
            logger.info("server shutting down")
            await runner.cleanup()

    async def handle_ws_request(self, request: web.Request) -> web.WebSocketResponse:
        """Обрабатывает WebSocket-сессию с поддержкой update-потока.

        Пример использования:
            # вызывается aiohttp автоматически на GET /acp/ws
        """

        # Генерируем уникальный ID подключения для отслеживания
        connection_id = str(uuid.uuid4())[:8]
        remote_addr = request.remote or "unknown"
        start_time = time.time()
        
        # Логируем подключение клиента
        logger.info(
            "ws connection established",
            connection_id=connection_id,
            remote_addr=remote_addr,
        )

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        protocol = ACPProtocol(
            require_auth=self.require_auth,
            auth_api_key=self.auth_api_key,
            storage=self.storage,
        )
        # Храним отложенные завершения prompt-turn по sessionId в рамках WS-соединения.
        deferred_prompt_tasks: dict[str, asyncio.Task[None]] = {}
        # По ACP любые session-методы в WS доступны только после initialize.
        initialized = False
        
        # Создаем логгер с контекстом подключения
        conn_logger = logger.bind(connection_id=connection_id)

        try:
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    method_name: str | None = None
                    session_id: str | None = None
                    request_id: str | None = None
                    try:
                        acp_request = ACPMessage.from_json(message.data)
                        method_name = acp_request.method
                        request_id = str(acp_request.id) if acp_request.id is not None else None
                        
                        if method_name is None:
                            outcome = protocol.handle_client_response(acp_request)
                        else:
                            if method_name == "initialize":
                                initialized = True
                            elif not initialized:
                                if acp_request.is_notification:
                                    outcome = ProtocolOutcome()
                                else:
                                    outcome = ProtocolOutcome(
                                        response=ACPMessage.error_response(
                                            acp_request.id,
                                            code=-32000,
                                            message="Initialize required before session methods",
                                        )
                                    )
                                method_name = None
                                session_id = None
                                for notification in outcome.notifications:
                                    await ws.send_str(notification.to_json())
                                if outcome.response is not None:
                                    await ws.send_str(outcome.response.to_json())
                                for followup_response in outcome.followup_responses:
                                    await ws.send_str(followup_response.to_json())
                                continue
                            if isinstance(acp_request.params, dict):
                                raw_session_id = acp_request.params.get("sessionId")
                                if isinstance(raw_session_id, str):
                                    session_id = raw_session_id
                            outcome = await protocol.handle(acp_request)
                        
                        # Логируем входящий запрос с методом и сессией
                        conn_logger.info(
                            "request received",
                            method=method_name,
                            request_id=request_id,
                            session_id=session_id,
                        )
                    except Exception as exc:
                        # Логируем ошибку парсинга с полным traceback
                        conn_logger.error(
                            "request parse error",
                            request_id=request_id,
                            error=str(exc),
                            exc_info=True,
                        )
                        outcome = ProtocolOutcome(
                            response=ACPMessage.error_response(
                                None,
                                code=-32700,
                                message="Parse error",
                                data=str(exc),
                            )
                        )

                    if method_name == "session/cancel" and session_id is not None:
                        task = deferred_prompt_tasks.pop(session_id, None)
                        if task is not None:
                            task.cancel()

                    if (
                        method_name == "session/prompt"
                        and session_id is not None
                        and outcome.response is None
                        and protocol.should_auto_complete_active_turn(session_id)
                    ):
                        task = deferred_prompt_tasks.pop(session_id, None)
                        if task is not None:
                            task.cancel()
                        deferred_prompt_tasks[session_id] = asyncio.create_task(
                            self._complete_deferred_prompt(
                                ws=ws,
                                protocol=protocol,
                                session_id=session_id,
                                deferred_prompt_tasks=deferred_prompt_tasks,
                                connection_id=connection_id,
                            )
                        )

                    for notification in outcome.notifications:
                        await ws.send_str(notification.to_json())

                    if outcome.response is not None:
                        await ws.send_str(outcome.response.to_json())
                    for followup_response in outcome.followup_responses:
                        await ws.send_str(followup_response.to_json())

                    if method_name == "shutdown":
                        await ws.close()
                        break
                elif message.type in {WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING}:
                    break
        finally:
            for task in deferred_prompt_tasks.values():
                task.cancel()
            
            # Логируем закрытие соединения с продолжительностью
            duration = time.time() - start_time
            conn_logger.info(
                "ws connection closed",
                duration=round(duration, 3),
            )

        return ws

    async def _complete_deferred_prompt(
        self,
        *,
        ws: web.WebSocketResponse,
        protocol: ACPProtocol,
        session_id: str,
        deferred_prompt_tasks: dict[str, asyncio.Task[None]],
        connection_id: str,
    ) -> None:
        """Завершает отложенный `session/prompt` и отправляет финальный response.

        Метод нужен для demo-эмуляции in-flight turn, который можно отменить через
        `session/cancel` до отправки финального `stopReason`.

        Пример использования:
            task = asyncio.create_task(server._complete_deferred_prompt(...))
        """
        
        conn_logger = logger.bind(connection_id=connection_id, session_id=session_id)

        try:
            # Небольшая задержка оставляет окно для входящего `session/cancel`.
            await asyncio.sleep(0.05)
            response = protocol.complete_active_turn(session_id, stop_reason="end_turn")
            if response is not None and not ws.closed:
                await ws.send_str(response.to_json())
                conn_logger.info("deferred prompt completed")
        except asyncio.CancelledError:
            # Нормальная ветка: отмена задачи при `session/cancel`.
            conn_logger.info("deferred prompt cancelled")
            return
        finally:
            deferred_prompt_tasks.pop(session_id, None)
