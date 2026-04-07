from __future__ import annotations

import argparse
import asyncio

from .http_server import ACPHttpServer
from .server import ACPServer


def run_server() -> None:
    parser = argparse.ArgumentParser(prog="acp-server")
    parser.add_argument("--transport", choices=["tcp", "http"], default="tcp")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    if args.transport == "tcp":
        server = ACPServer(host=args.host, port=args.port)
    else:
        server = ACPHttpServer(host=args.host, port=args.port)

    asyncio.run(server.run())
