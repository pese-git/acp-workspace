"""Единый CLI для CodeLab.

Режимы работы:
- local (по умолчанию): запускает сервер на localhost и TUI
- serve: запускает только сервер с WebSocket API
- connect: запускает только TUI клиент

Примеры использования:
    codelab                                      # Локальный режим (сервер + TUI)
    codelab serve --port 4096 --host 0.0.0.0     # Режим сервера (WebSocket API)
    codelab connect --host 127.0.0.1 --port 4096 # Режим клиента (TUI)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from codelab.server.http_server import ACPHttpServer

# Настройка логирования для CLI
logger = structlog.get_logger("codelab.cli")

# Порт по умолчанию для WebSocket сервера
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"


def _configure_logging(verbose: bool = False) -> None:
    """Настраивает structlog для CLI.

    Args:
        verbose: Включить подробное логирование (DEBUG уровень)
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Базовая конфигурация logging
    logging.basicConfig(
        format="%(message)s",
        level=level,
        stream=sys.stderr,
    )

    # Настройка structlog для красивого вывода в консоль
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def main() -> None:
    """Главная точка входа CLI.

    Парсит аргументы командной строки и запускает соответствующий режим.
    """
    parser = argparse.ArgumentParser(
        prog="codelab",
        description="CodeLab - AI-powered coding assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  codelab                           Локальный режим (сервер + TUI)
  codelab serve --port 4096         Запустить только сервер
  codelab connect --host server.local --port 4096  Подключиться к серверу
        """,
    )

    # Глобальные опции
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Включить подробное логирование",
    )

    # Подкоманды
    subparsers = parser.add_subparsers(dest="command", help="Режим работы")

    # codelab serve - режим сервера
    serve_parser = subparsers.add_parser(
        "serve",
        help="Запустить только WebSocket сервер",
        description="Запускает ACP WebSocket сервер для удалённых клиентов",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=f"Адрес для прослушивания (по умолчанию: {DEFAULT_HOST})",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Порт для прослушивания (по умолчанию: {DEFAULT_PORT})",
    )
    serve_parser.add_argument(
        "--no-web",
        action="store_true",
        help="Отключить Web UI на корневом пути /",
    )

    # codelab connect - режим клиента
    connect_parser = subparsers.add_parser(
        "connect",
        help="Подключиться к удалённому серверу",
        description="Запускает TUI клиент и подключается к удалённому ACP серверу",
    )
    connect_parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Адрес сервера (по умолчанию: {DEFAULT_HOST})",
    )
    connect_parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Порт сервера (по умолчанию: {DEFAULT_PORT})",
    )
    connect_parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Рабочая директория проекта (по умолчанию: текущая)",
    )

    args = parser.parse_args()

    # Настраиваем логирование
    _configure_logging(verbose=getattr(args, "verbose", False))

    try:
        if args.command == "serve":
            run_serve(args)
        elif args.command == "connect":
            run_connect(args)
        else:
            # Локальный режим по умолчанию (без подкоманды)
            run_local(args)
    except KeyboardInterrupt:
        # Graceful shutdown при Ctrl+C
        logger.info("shutdown_requested", reason="KeyboardInterrupt")
        sys.exit(0)


def run_local(args: argparse.Namespace) -> None:
    """Локальный режим: запускает сервер в фоне и TUI.

    Сервер запускается в отдельном потоке на localhost,
    затем запускается TUI клиент с подключением к этому серверу.
    При завершении TUI сервер автоматически останавливается.

    Args:
        args: Аргументы командной строки
    """
    from codelab.server.http_server import ACPHttpServer

    host = DEFAULT_HOST
    port = DEFAULT_PORT

    logger.info("starting_local_mode", host=host, port=port)

    # Событие для сигнализации остановки сервера
    stop_event = threading.Event()
    server_ready_event = threading.Event()
    server_instance: ACPHttpServer | None = None

    def run_server_in_thread() -> None:
        """Запускает сервер в отдельном event loop."""
        nonlocal server_instance

        # Создаём новый event loop для потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            server_instance = ACPHttpServer(host=host, port=port)

            async def server_task() -> None:
                """Асинхронная задача сервера с проверкой остановки."""
                # Сигнализируем что сервер готов
                server_ready_event.set()

                # Запускаем сервер (assert для type checker)
                assert server_instance is not None
                await server_instance.run()

            loop.run_until_complete(server_task())
        except Exception as exc:
            logger.error("server_error", error=str(exc))
        finally:
            loop.close()

    # Запускаем сервер в отдельном потоке
    server_thread = threading.Thread(target=run_server_in_thread, daemon=True)
    server_thread.start()

    # Ждём готовности сервера (максимум 5 секунд)
    if not server_ready_event.wait(timeout=5.0):
        logger.error("server_start_timeout")
        sys.exit(1)

    # Небольшая задержка чтобы сервер полностью инициализировался
    import time

    time.sleep(0.5)

    logger.info("server_started", host=host, port=port)

    try:
        # Запускаем TUI клиент
        _run_tui_app(host=host, port=port, cwd=getattr(args, "cwd", None))
    finally:
        # Останавливаем сервер
        logger.info("stopping_server")
        stop_event.set()


def run_serve(args: argparse.Namespace) -> None:
    """Режим сервера: запускает только WebSocket API.

    Args:
        args: Аргументы командной строки с host, port и no_web
    """
    from codelab.server.http_server import ACPHttpServer

    host = args.host
    port = args.port
    enable_web = not getattr(args, "no_web", False)

    logger.info("starting_server_mode", host=host, port=port, enable_web=enable_web)

    # Логируем доступные endpoints
    logger.info(
        "endpoints_available",
        ws_api=f"ws://{host}:{port}/acp/ws",
        web_ui=f"http://{host}:{port}/" if enable_web else "disabled",
    )

    # Создаём и запускаем сервер
    server = ACPHttpServer(host=host, port=port, enable_web=enable_web)

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("server_shutdown", reason="KeyboardInterrupt")


def run_connect(args: argparse.Namespace) -> None:
    """Режим клиента: подключается к удалённому серверу.

    Args:
        args: Аргументы командной строки с host, port и cwd
    """
    host = args.host
    port = args.port
    cwd = getattr(args, "cwd", None)

    logger.info("starting_connect_mode", host=host, port=port)

    _run_tui_app(host=host, port=port, cwd=cwd)


def _run_tui_app(*, host: str, port: int, cwd: str | None = None) -> None:
    """Запускает TUI приложение.

    Args:
        host: Адрес сервера
        port: Порт сервера
        cwd: Рабочая директория (опционально)
    """
    from codelab.client.tui.app import ACPClientApp

    logger.info("starting_tui", host=host, port=port, cwd=cwd or "(current)")

    # Создаём и запускаем TUI приложение
    app = ACPClientApp(host=host, port=port, cwd=cwd)
    app.run()

    logger.info("tui_exited")


if __name__ == "__main__":
    main()
