from __future__ import annotations

import argparse
import asyncio

from .http_server import ACPHttpServer


def run_server() -> None:
    parser = argparse.ArgumentParser(prog="acp-server")
    parser.add_argument("--transport", choices=["http", "ws"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    server = ACPHttpServer(host=args.host, port=args.port)

    asyncio.run(server.run())
