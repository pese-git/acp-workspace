"""CLI-точка входа ACP-сервера.

Модуль читает аргументы запуска и поднимает HTTP/WS транспорт.

Пример использования:
    acp-server --transport http --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import argparse
import asyncio

from .http_server import ACPHttpServer


def run_server() -> None:
    """Запускает ACP HTTP/WS сервер из аргументов командной строки.

    Пример использования:
        run_server()
    """

    parser = argparse.ArgumentParser(prog="acp-server")
    parser.add_argument("--transport", choices=["http", "ws"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()

    server = ACPHttpServer(host=args.host, port=args.port)

    asyncio.run(server.run())
