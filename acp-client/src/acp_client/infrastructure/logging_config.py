"""Конфигурация structured logging для ACP-клиента.

Модуль предоставляет:
- Инициализацию structlog с форматированием
- Логирование операций с контекстом
- Отслеживание времени выполнения

Пример использования:
    from acp_client.infrastructure.logging_config import setup_logging
    setup_logging(level="INFO")
    logger = structlog.get_logger(__name__)
    logger.info("operation_started", operation_id="op_123")
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Literal, Protocol

import structlog


class Logger(Protocol):
    """Интерфейс структурированного логгера."""

    def info(self, event: str, **kw: Any) -> None:
        """Логирует info сообщение."""
        ...

    def debug(self, event: str, **kw: Any) -> None:
        """Логирует debug сообщение."""
        ...

    def warning(self, event: str, **kw: Any) -> None:
        """Логирует warning сообщение."""
        ...

    def error(self, event: str, **kw: Any) -> None:
        """Логирует error сообщение."""
        ...


def setup_logging(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
) -> None:
    """Инициализирует структурированное логирование для клиента.

    Настраивает:
    - Structlog для JSON-подобного логирования
    - Форматирование времени в ISO 8601
    - Вывод в stdout/stderr
    - Стандартное логирование Python (fallback)

    Args:
        level: Уровень логирования (по умолчанию INFO)

    Пример:
        setup_logging(level="DEBUG")
        logger = structlog.get_logger(__name__)
        logger.debug("test_message", key="value")
    """
    # Стандартное логирование Python как fallback
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level),
    )

    # Structlog конфигурация
    structlog.configure(
        processors=[
            # Добавляем текущее время
            structlog.processors.TimeStamper(fmt="iso"),
            # Добавляем информацию об логгере
            structlog.processors.add_log_level,
            # Выделение exception traceback-а
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Сортировка ключей для читаемости
            structlog.processors.KeyValueRenderer(
                key_order=["timestamp", "level", "event"],
            ),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class OperationTimer:
    """Контекстный менеджер для отслеживания времени операций.

    Логирует время начала, окончания и продолжительность операции.

    Пример использования:
        logger = structlog.get_logger(__name__)
        with OperationTimer(logger, "fetch_data", datasource="api"):
            # выполнение операции
            data = fetch_from_api()
    """

    def __init__(
        self,
        logger: Any,
        operation_name: str,
        **context: Any,
    ) -> None:
        """Инициализирует таймер операции.

        Args:
            logger: Structlog логгер
            operation_name: Имя операции для логирования
            **context: Дополнительный контекст для логирования

        Пример:
            with OperationTimer(logger, "api_call", endpoint="/users"):
                ...
        """
        self.logger = logger
        self.operation_name = operation_name
        self.context: dict[str, Any] = context
        self.start_time: float | None = None

    def __enter__(self) -> OperationTimer:
        """Логирует начало операции."""
        import time

        self.start_time = time.time()
        self.logger.info(
            f"{self.operation_name}_started",
            **self.context,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Логирует окончание операции и время выполнения."""
        import time

        if self.start_time is None:
            return

        duration = time.time() - self.start_time

        if exc_type is not None:
            # Ошибка при выполнении
            self.logger.error(
                f"{self.operation_name}_failed",
                duration_ms=round(duration * 1000, 2),
                error_type=exc_type.__name__,
                **self.context,
            )
        else:
            # Успешное завершение
            self.logger.info(
                f"{self.operation_name}_completed",
                duration_ms=round(duration * 1000, 2),
                **self.context,
            )


def get_logger(name: str) -> structlog.PrintLogger:
    """Возвращает настроенный структурированный логгер.

    Args:
        name: Имя логгера (обычно __name__)

    Returns:
        Готовый к использованию structlog логгер

    Пример:
        logger = get_logger(__name__)
        logger.info("operation_started")
    """
    return structlog.get_logger(name)
