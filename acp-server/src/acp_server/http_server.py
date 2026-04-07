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

        async for message in ws:
            if message.type == WSMsgType.TEXT:
                method_name: str | None = None
                try:
                    acp_request = ACPMessage.from_json(message.data)
                    method_name = acp_request.method
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

                for notification in outcome.notifications:
                    await ws.send_str(notification.to_json())

                if outcome.response is not None:
                    await ws.send_str(outcome.response.to_json())

                if method_name == "shutdown":
                    await ws.close()
                    break
            elif message.type in {WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING}:
                break

        return ws
