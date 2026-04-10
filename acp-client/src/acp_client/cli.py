"""CLI-обертка для запуска TUI приложения.

Команда:
    acp-client --tui [--host HOST] [--port PORT]

Для использования Clean Architecture API, используйте DIBootstrapper напрямую.

Пример использования с новым API:
    from acp_client.infrastructure.di_bootstrapper import DIBootstrapper
    from acp_client.application.use_cases import InitializeUseCase

    container = DIBootstrapper.build(host="localhost", port=8000)
    use_case = container.resolve(InitializeUseCase)
    result = await use_case.execute()
"""

from __future__ import annotations

import argparse

from .logging import setup_logging


def run_client() -> None:
    """Точка входа CLI-клиента.

    Запускает TUI приложение.
    """

    parser = argparse.ArgumentParser(prog="acp-client")
    parser.add_argument("--host", default=None, help="Хост сервера (default: localhost)")
    parser.add_argument("--port", default=None, type=int, help="Порт сервера (default: 8765)")
    parser.add_argument(
        "--tui",
        action="store_true",
        help="Запустить интерактивный Textual TUI клиент (default)",
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
    parser.add_argument(
        "--log-file",
        default=None,
        help="Путь к файлу логов. 'default' для ~/.acp-client/logs/acp-client.log",
    )
    args = parser.parse_args()

    # Настроить логирование с сохранением в ~/.acp-client/logs/acp-client.log по умолчанию
    setup_logging(
        level=args.log_level,
        json_format=args.log_json,
        log_file=args.log_file or "default",
    )

    # Запустить TUI по умолчанию
    run_tui_app(host=args.host, port=args.port)


def run_tui_app(*, host: str | None, port: int | None) -> None:
    """Ленивая загрузка TUI, чтобы не требовать Textual для обычного CLI."""

    from .tui import run_tui_app as _run_tui

    _run_tui(host=host, port=port)
