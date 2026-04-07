from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from .client import ACPClient
from .messages import parse_json_params


def run_client() -> None:
    parser = argparse.ArgumentParser(prog="acp-client")
    parser.add_argument("--transport", choices=["http", "ws"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--method", required=True)
    parser.add_argument("--params", default=None)
    parser.add_argument(
        "--show-updates",
        action="store_true",
        help="Показать replay/update события для session/load (полезно для WS)",
    )
    args = parser.parse_args()

    params = parse_json_params(args.params)
    client = ACPClient(host=args.host, port=args.port)

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
            client.load_session(
                session_id=session_id,
                cwd=cwd,
                mcp_servers=[item for item in mcp_servers if isinstance(item, dict)],
                transport=args.transport,
            )
        )
        payload: dict[str, Any] = {
            "response": response.to_dict(),
            "updates": updates,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    response = asyncio.run(
        client.request(
            method=args.method,
            params=params,
            transport=args.transport,
        )
    )
    print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
