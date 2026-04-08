"""CLI-обертка над ACPClient.

Команда читает параметры из аргументов, выполняет ACP-запрос и печатает JSON.
Для `session/load` поддержан режим показа replay/update-событий.

Пример использования:
    acp-client --method session/load --show-updates --params '{...}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from .client import ACPClient
from .logging import setup_logging
from .messages import parse_json_params


def run_client() -> None:
    """Точка входа CLI-клиента.

    Метод:
    - парсит аргументы,
    - валидирует JSON-параметры,
    - вызывает ACP-клиент,
    - печатает результат в человеко-читаемом JSON.

    Пример использования:
        run_client()
    """

    parser = argparse.ArgumentParser(prog="acp-client")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", default=None, type=int)
    parser.add_argument("--method", default=None)
    parser.add_argument("--params", default=None)
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Запустить интерактивный Textual TUI клиент",
    )
    parser.add_argument(
        "--show-updates",
        action="store_true",
        help="Показать replay/update события для session/load (полезно для WS)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Уровень логирования (default: INFO)",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Использовать JSON формат для логов",
    )
    args = parser.parse_args()

    # Настроить логирование только если явно указаны флаги
    if args.log_level != "INFO" or args.log_json:
        setup_logging(level=args.log_level, json_format=args.log_json)

    if args.tui:
        run_tui_app(host=args.host, port=args.port)
        return

    resolved_host = args.host if isinstance(args.host, str) and args.host else "127.0.0.1"
    resolved_port = args.port if isinstance(args.port, int) and args.port > 0 else 8765

    if not isinstance(args.method, str) or not args.method:
        parser.error("--method обязателен, если не используется --tui")

    params = parse_json_params(args.params)
    client = ACPClient(host=resolved_host, port=resolved_port)

    # Для `session/load` можно вывести replay обновления вместе с финальным ответом.
    if args.method == "session/load" and args.show_updates:
        session_id = params.get("sessionId")
        cwd = params.get("cwd")
        mcp_servers = params.get("mcpServers", [])

        if not isinstance(session_id, str):
            parser.error("--params для session/load должен содержать строковое поле sessionId")
        if not isinstance(cwd, str):
            parser.error("--params для session/load должен содержать строковое поле cwd")
        if not isinstance(mcp_servers, list):
            parser.error("--params для session/load должен содержать массив mcpServers")

        response, updates = asyncio.run(
            client.load_session_parsed(
                session_id=session_id,
                cwd=cwd,
                mcp_servers=[item for item in mcp_servers if isinstance(item, dict)],
            )
        )
        payload: dict[str, Any] = {
            "response": response.to_dict(),
            # Для CLI выводим типизированные updates в JSON-совместимом формате.
            "updates": [update.model_dump() for update in updates],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    response = asyncio.run(
        client.request(
            method=args.method,
            params=params,
        )
    )
    print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))


def run_tui_app(*, host: str | None, port: int | None) -> None:
    """Ленивая загрузка TUI, чтобы не требовать Textual для обычного CLI."""

    from .tui import run_tui_app as _run_tui

    _run_tui(host=host, port=port)
