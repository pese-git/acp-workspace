"""Точка входа для запуска TUI клиента как модуля."""

from __future__ import annotations

import argparse

from .app import run_tui_app


def main() -> None:
    """Запускает TUI приложение с параметрами хоста, порта и логирования."""

    parser = argparse.ArgumentParser(prog="acp-client-tui")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", default=None, type=int)
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
    run_tui_app(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        log_json=args.log_json,
        log_file=args.log_file,
    )


if __name__ == "__main__":
    main()
