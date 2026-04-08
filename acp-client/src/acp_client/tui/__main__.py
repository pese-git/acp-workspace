"""Точка входа для запуска TUI клиента как модуля."""

from __future__ import annotations

import argparse

from .app import run_tui_app


def main() -> None:
    """Запускает TUI приложение с параметрами хоста и порта."""

    parser = argparse.ArgumentParser(prog="acp-client-tui")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", default=None, type=int)
    args = parser.parse_args()
    run_tui_app(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
