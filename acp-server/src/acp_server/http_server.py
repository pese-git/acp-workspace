"""WebSocket транспорт ACP-сервера.

Модуль поднимает endpoint `GET /acp/ws` для двустороннего потока с
`session/update` и server->client RPC.

Пример использования:
    server = ACPHttpServer(host="127.0.0.1", port=8080)
    await server.run()
"""

from __future__ import annotations

import asyncio

from aiohttp import WSMsgType, web

from .messages import ACPMessage
from .protocol import ACPProtocol, ProtocolOutcome


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
    ) -> None:
        """Создает транспортный сервер с адресом прослушивания.

        Пример использования:
            ACPHttpServer(host="0.0.0.0", port=8080)
        """

        self.host = host
        self.port = port
        self.require_auth = require_auth
        self.auth_api_key = auth_api_key

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
        print(f"ACP WS server listening on ws://{self.host}:{self.port}/acp/ws")

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await runner.cleanup()

    async def handle_ws_request(self, request: web.Request) -> web.WebSocketResponse:
        """Обрабатывает WebSocket-сессию с поддержкой update-потока.

        Пример использования:
            # вызывается aiohttp автоматически на GET /acp/ws
        """

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        protocol = ACPProtocol(require_auth=self.require_auth, auth_api_key=self.auth_api_key)
        # Храним отложенные завершения prompt-turn по sessionId в рамках WS-соединения.
        deferred_prompt_tasks: dict[str, asyncio.Task[None]] = {}
        # По ACP любые session-методы в WS доступны только после initialize.
        initialized = False

        try:
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    method_name: str | None = None
                    session_id: str | None = None
                    try:
                        acp_request = ACPMessage.from_json(message.data)
                        method_name = acp_request.method
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
                            outcome = protocol.handle(acp_request)
                    except Exception as exc:
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

        return ws

    async def _complete_deferred_prompt(
        self,
        *,
        ws: web.WebSocketResponse,
        protocol: ACPProtocol,
        session_id: str,
        deferred_prompt_tasks: dict[str, asyncio.Task[None]],
    ) -> None:
        """Завершает отложенный `session/prompt` и отправляет финальный response.

        Метод нужен для demo-эмуляции in-flight turn, который можно отменить через
        `session/cancel` до отправки финального `stopReason`.

        Пример использования:
            task = asyncio.create_task(server._complete_deferred_prompt(...))
        """

        try:
            # Небольшая задержка оставляет окно для входящего `session/cancel`.
            await asyncio.sleep(0.05)
            response = protocol.complete_active_turn(session_id, stop_reason="end_turn")
            if response is not None and not ws.closed:
                await ws.send_str(response.to_json())
        except asyncio.CancelledError:
            # Нормальная ветка: отмена задачи при `session/cancel`.
            return
        finally:
            deferred_prompt_tasks.pop(session_id, None)
