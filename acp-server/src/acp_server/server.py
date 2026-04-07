from __future__ import annotations

import asyncio
import json

from .messages import ACPMessage
from .protocol import process_request


class ACPServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port

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
                    response = process_request(request)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    response = ACPMessage(
                        id="unknown",
                        type="response",
                        error={"code": -32700, "message": f"Parse error: {exc}"},
                    )

                writer.write((response.to_json() + "\n").encode())
                await writer.drain()

                if method_name == "shutdown":
                    break
        finally:
            writer.close()
            await writer.wait_closed()
            print(f"Client disconnected: {peer}")
