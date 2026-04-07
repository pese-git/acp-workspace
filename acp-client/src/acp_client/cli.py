from __future__ import annotations

import argparse
import asyncio
import json

from .client import ACPClient
from .messages import parse_json_params


def run_client() -> None:
    parser = argparse.ArgumentParser(prog="acp-client")
    parser.add_argument("--transport", choices=["http", "ws"], default="http")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--method", required=True)
    parser.add_argument("--params", default=None)
    args = parser.parse_args()

    params = parse_json_params(args.params)
    client = ACPClient(host=args.host, port=args.port)
    response = asyncio.run(
        client.request(
            method=args.method,
            params=params,
            transport=args.transport,
        )
    )
    print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
