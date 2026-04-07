from __future__ import annotations

import asyncio

from aiohttp import WSMsgType, web

from .messages import ACPMessage
from .protocol import process_request


class ACPHttpServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        self.host = host
        self.port = port

    async def run(self) -> None:
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
        try:
            payload = await request.json()
            acp_request = ACPMessage.from_dict(payload)
            response = process_request(acp_request)
            status = 200
        except Exception as exc:
            response = ACPMessage(
                id="unknown",
                type="response",
                error={"code": -32700, "message": f"Parse error: {exc}"},
            )
            status = 400

        return web.json_response(response.to_dict(), status=status)

    async def handle_ws_request(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for message in ws:
            if message.type == WSMsgType.TEXT:
                method_name: str | None = None
                try:
                    acp_request = ACPMessage.from_json(message.data)
                    method_name = acp_request.method
                    response = process_request(acp_request)
                except Exception as exc:
                    response = ACPMessage(
                        id="unknown",
                        type="response",
                        error={"code": -32700, "message": f"Parse error: {exc}"},
                    )

                await ws.send_str(response.to_json())
                if method_name == "shutdown":
                    await ws.close()
                    break
            elif message.type in {WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSING}:
                break

        return ws
