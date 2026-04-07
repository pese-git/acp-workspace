"""CLI-точка входа ACP-сервера.

Модуль читает аргументы запуска и поднимает WS транспорт.

Пример использования:
    acp-server --host 127.0.0.1 --port 8080
    acp-server --log-level DEBUG
    acp-server --log-level INFO --log-json
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .http_server import ACPHttpServer
from .logging import setup_logging
from .storage import InMemoryStorage, JsonFileStorage, SessionStorage


def parse_storage_arg(storage_arg: str) -> SessionStorage:
    """Парсит аргумент --storage и создаёт соответствующий backend.

    Поддерживаемые форматы:
    - 'memory' — In-memory хранилище (default)
    - 'json:/path/to/dir' — JSON файловое хранилище

    Args:
        storage_arg: Строка с аргументом хранилища.

    Returns:
        Объект SessionStorage соответствующей реализации.

    Raises:
        ValueError: При неизвестном формате аргумента.

    Пример:
        storage = parse_storage_arg("json:~/.acp/sessions")
    """
    if storage_arg == "memory":
        return InMemoryStorage()
    elif storage_arg.startswith("json:"):
        path_str = storage_arg[5:]  # Убрать префикс "json:"
        path = Path(path_str).expanduser()
        return JsonFileStorage(path)
    else:
        raise ValueError(f"Unknown storage backend: {storage_arg}")


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
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования (DEBUG, INFO, WARNING, ERROR). По умолчанию INFO.",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Использовать JSON формат для логов (для production). По умолчанию консольный формат.",
    )
    parser.add_argument(
        "--storage",
        default="memory",
        help="Storage backend: 'memory' (default) или 'json:/path/to/dir' для persistence",
    )
    args = parser.parse_args()

    # Инициализируем логирование перед запуском сервера
    setup_logging(level=args.log_level, json_format=args.log_json)

    auth_api_key = args.auth_api_key
    if not isinstance(auth_api_key, str) or not auth_api_key:
        env_api_key = os.getenv("ACP_SERVER_API_KEY")
        auth_api_key = env_api_key if isinstance(env_api_key, str) and env_api_key else None

    # Парсим и создаём storage backend
    storage = parse_storage_arg(args.storage)

    server = ACPHttpServer(
        host=args.host,
        port=args.port,
        require_auth=args.require_auth,
        auth_api_key=auth_api_key,
        storage=storage,
    )

    asyncio.run(server.run())
