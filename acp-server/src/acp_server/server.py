from __future__ import annotations

import asyncio
import json

from pydantic import ValidationError

from .messages import ACPMessage
from .protocol import ACPProtocol, ProtocolOutcome


class ACPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.protocol = ACPProtocol()

    async def run(self) -> None:
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        sockets = server.sockets or []
        bound = sockets[0].getsockname() if sockets else (self.host, self.port)
        print(f"ACP server listening on {bound[0]}:{bound[1]}")
        async with server:
            await server.serve_forever()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                method_name: str | None = None

                try:
                    request = ACPMessage.from_json(raw.decode().strip())
                    method_name = request.method
                    outcome = self.protocol.handle(request)
                except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
                    outcome = ProtocolOutcome(
                        response=ACPMessage.error_response(
                            None,
                            code=-32700,
                            message="Parse error",
                            data=str(exc),
                        )
                    )

                for notification in outcome.notifications:
                    writer.write((notification.to_json() + "\n").encode())
                    await writer.drain()

                if outcome.response is not None:
                    writer.write((outcome.response.to_json() + "\n").encode())
                    await writer.drain()

                if method_name == "shutdown":
                    break
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"Client disconnected: {peer}")
