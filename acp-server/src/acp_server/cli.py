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

from dotenv import load_dotenv

from .config import AppConfig
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

    Загружает переменные окружения из .env файла в текущей директории.
    Приоритет: CLI аргументы > .env переменные > значения по умолчанию

    Пример .env файла:
        ACP_LLM_PROVIDER=openai
        ACP_LLM_MODEL=gpt-4-turbo
        ACP_LLM_API_KEY=sk-...
        ACP_LLM_TEMPERATURE=0.9
        ACP_SYSTEM_PROMPT=Your custom prompt

    Пример использования:
        # Загружает .env из текущей директории
        run_server()
    """
    # Загружаем переменные окружения из .env файла если он существует
    load_dotenv()

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
    parser.add_argument(
        "--llm-provider",
        default=None,
        help="LLM провайдер (openai, mock). Переопределяет ACP_LLM_PROVIDER",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Модель LLM. Переопределяет ACP_LLM_MODEL",
    )
    parser.add_argument(
        "--llm-api-key",
        default=None,
        help="API ключ для LLM. Переопределяет ACP_LLM_API_KEY",
    )
    parser.add_argument(
        "--llm-base-url",
        default=None,
        help="Base URL для LLM провайдера. Переопределяет ACP_LLM_BASE_URL",
    )
    parser.add_argument(
        "--llm-temperature",
        type=float,
        default=None,
        help="Temperature для LLM (0.0-1.0). Переопределяет ACP_LLM_TEMPERATURE",
    )
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=None,
        help="Максимум токенов для LLM. Переопределяет ACP_LLM_MAX_TOKENS",
    )
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="Системный промпт для агента. Переопределяет ACP_SYSTEM_PROMPT",
    )
    args = parser.parse_args()

    # Инициализируем логирование перед запуском сервера
    setup_logging(level=args.log_level, json_format=args.log_json)

    # Загружаем конфигурацию из переменных окружения
    config = AppConfig.from_env()

    # Переопределяем конфиг из аргументов командной строки если указаны
    if args.llm_provider:
        config.llm.provider = args.llm_provider
    if args.llm_model:
        config.llm.model = args.llm_model
    if args.llm_api_key:
        config.llm.api_key = args.llm_api_key
    if args.llm_base_url:
        config.llm.base_url = args.llm_base_url
    if args.llm_temperature is not None:
        config.llm.temperature = args.llm_temperature
    if args.llm_max_tokens is not None:
        config.llm.max_tokens = args.llm_max_tokens
    if args.system_prompt:
        config.agent.system_prompt = args.system_prompt

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
        config=config,
    )

    asyncio.run(server.run())
