"""HTTP/WS транспорт ACP-сервера.

Модуль поднимает два endpoint:
- `POST /acp` для одиночных request/response,
- `GET /acp/ws` для двустороннего потока с `session/update`.

Пример использования:
    server = ACPHttpServer(host="127.0.0.1", port=8080)
    await server.run()
"""

from __future__ import annotations

import asyncio

from aiohttp import WSMsgType, web
from pydantic import ValidationError

from .messages import ACPMessage
from .protocol import ACPProtocol, ProtocolOutcome


class ACPHttpServer:
    """Транспортный слой ACP поверх aiohttp (HTTP + WebSocket).

    Класс принимает wire-сообщения, передает их в `ACPProtocol` и отправляет
    обратно response/notifications в правильном порядке.

    Пример использования:
        server = ACPHttpServer(port=8080)
        await server.run()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Создает транспортный сервер с адресом прослушивания.

        Пример использования:
            ACPHttpServer(host="0.0.0.0", port=8080)
        """

        self.host = host
        self.port = port
        self.protocol = ACPProtocol()

    async def run(self) -> None:
        """Запускает HTTP и WS endpoints и держит процесс живым.

        Пример использования:
            await ACPHttpServer().run()
        """

        app = web.Application()
        app.router.add_post("/acp", self.handle_http_request)
        app.router.add_get("/acp/ws", self.handle_ws_request)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()
        print(f"ACP HTTP/WS server listening on http://{self.host}:{self.port}")

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await runner.cleanup()

    async def handle_http_request(self, request: web.Request) -> web.Response:
        """Обрабатывает единичный JSON-RPC запрос через HTTP.

        Пример использования:
            # вызывается aiohttp автоматически на POST /acp
        """

        try:
            payload = await request.json()
            acp_request = ACPMessage.from_dict(payload)
            outcome = self.protocol.handle(acp_request)
            if (
                outcome.response is None
                and acp_request.method == "session/prompt"
                and isinstance(acp_request.params, dict)
            ):
                # Для HTTP финализируем deferred prompt сразу, чтобы не терять response.
                session_id = acp_request.params.get("sessionId")
                if isinstance(session_id, str):
                    completed = self.protocol.complete_active_turn(
                        session_id, stop_reason="end_turn"
                    )
                    if completed is not None:
                        return web.json_response(completed.to_dict(), status=200)
            if outcome.response is None:
                return web.Response(status=204)
            return web.json_response(outcome.response.to_dict(), status=200)
        except ValidationError as exc:
            error = ACPMessage.error_response(
                None,
                code=-32600,
                message="Invalid Request",
                data=str(exc),
            )
            return web.json_response(error.to_dict(), status=400)
        except Exception as exc:
            error = ACPMessage.error_response(
                None,
                code=-32700,
                message="Parse error",
                data=str(exc),
            )
            return web.json_response(error.to_dict(), status=400)

    async def handle_ws_request(self, request: web.Request) -> web.WebSocketResponse:
        """Обрабатывает WebSocket-сессию с поддержкой update-потока.

        Пример использования:
            # вызывается aiohttp автоматически на GET /acp/ws
        """

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        # Храним отложенные завершения prompt-turn по sessionId в рамках WS-соединения.
        deferred_prompt_tasks: dict[str, asyncio.Task[None]] = {}

        try:
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    method_name: str | None = None
                    session_id: str | None = None
                    try:
                        acp_request = ACPMessage.from_json(message.data)
                        method_name = acp_request.method
                        if method_name is None:
                            outcome = self.protocol.handle_client_response(acp_request)
                        else:
                            if isinstance(acp_request.params, dict):
                                raw_session_id = acp_request.params.get("sessionId")
                                if isinstance(raw_session_id, str):
                                    session_id = raw_session_id
                            outcome = self.protocol.handle(acp_request)
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
                        and self.protocol.should_auto_complete_active_turn(session_id)
                    ):
                        task = deferred_prompt_tasks.pop(session_id, None)
                        if task is not None:
                            task.cancel()
                        deferred_prompt_tasks[session_id] = asyncio.create_task(
                            self._complete_deferred_prompt(
                                ws=ws,
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
            response = self.protocol.complete_active_turn(session_id, stop_reason="end_turn")
            if response is not None and not ws.closed:
                await ws.send_str(response.to_json())
        except asyncio.CancelledError:
            # Нормальная ветка: отмена задачи при `session/cancel`.
            return
        finally:
            deferred_prompt_tasks.pop(session_id, None)
