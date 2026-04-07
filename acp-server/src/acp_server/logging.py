"""Структурированное логирование с использованием structlog.

Модуль предоставляет настройку логирования для development и production.
Поддерживает JSON формат для production и цветной консольный формат для development.

Пример использования:
    logger = setup_logging(level="INFO", json_format=False)
    logger.info("server started", port=8080)
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> structlog.BoundLogger:
    """Настраивает структурированное логирование.

    Аргументы:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR). По умолчанию INFO.
        json_format: Использовать JSON формат вместо цветной консоли. По умолчанию False.

    Возвращает:
        Настроенный BoundLogger для использования в приложении.

    Пример использования:
        logger = setup_logging(level="DEBUG", json_format=False)
        logger.info("application started")
    """

    # Преобразуем строковый уровень в константу logging
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Задаем обработчики в зависимости от формата
    if json_format:
        # Production: JSON формат для парсинга в системах логирования
        processors = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: цветной консольный формат для удобства
        processors = [
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ]

    # Конфигурируем structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Конфигурируем стандартный logging для совместимости
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Получаем и возвращаем конфигурированный logger
    logger = structlog.get_logger()
    return logger
