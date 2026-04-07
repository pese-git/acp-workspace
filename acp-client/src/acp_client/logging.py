"""Модуль структурированного логирования для ACP клиента.

Предоставляет настройку логирования с поддержкой JSON и консольного формата.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def setup_logging(level: str = "INFO", json_format: bool = False) -> structlog.BoundLogger:
    """Настраивает структурированное логирование для клиента.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        json_format: Использовать JSON формат (True) или консольный (False)

    Returns:
        Настроенный logger

    Пример использования:
        logger = setup_logging(level="DEBUG", json_format=False)
        logger.info("client_request", method="session/prompt", session_id="sess_123")
    """
    # Настройка уровня логирования
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Процессоры для structlog
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Выбор рендерера
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # Конфигурация structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("acp_client")
