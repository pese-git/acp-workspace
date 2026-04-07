"""CLI-точка входа ACP-сервера.

Модуль читает аргументы запуска и поднимает WS транспорт.

Пример использования:
    acp-server --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import argparse
import asyncio
import os

from .http_server import ACPHttpServer


def run_server() -> None:
    """Запускает ACP WS-сервер из аргументов командной строки.

    Пример использования:
        run_server()
    """

    parser = argparse.ArgumentParser(prog="acp-server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument(
        "--require-auth",
        action="store_true",
        help="Требовать authenticate перед session/new и session/load",
    )
    parser.add_argument(
        "--auth-api-key",
        default=None,
        help=(
            "Локальный API key для authenticate (передается клиентом в params.apiKey); "
            "можно также задать через переменную среды ACP_SERVER_API_KEY"
        ),
    )
    args = parser.parse_args()

    auth_api_key = args.auth_api_key
    if not isinstance(auth_api_key, str) or not auth_api_key:
        env_api_key = os.getenv("ACP_SERVER_API_KEY")
        auth_api_key = env_api_key if isinstance(env_api_key, str) and env_api_key else None

    server = ACPHttpServer(
        host=args.host,
        port=args.port,
        require_auth=args.require_auth,
        auth_api_key=auth_api_key,
    )

    asyncio.run(server.run())
