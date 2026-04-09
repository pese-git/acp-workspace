"""Модуль структурированного логирования для ACP клиента.

Предоставляет настройку логирования с поддержкой JSON и консольного формата.
Поддерживает сохранение логов в файл в директорию ~/.acp-client/logs/
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Any

import structlog


def get_acp_client_dir() -> Path:
    """Получить директорию ~/.acp-client с автоматическим созданием.
    
    Returns:
        Path: Путь к директории ~/.acp-client
    """
    acp_dir = Path.home() / ".acp-client"
    acp_dir.mkdir(parents=True, exist_ok=True)
    return acp_dir


def get_logs_dir() -> Path:
    """Получить директорию ~/.acp-client/logs с автоматическим созданием.
    
    Returns:
        Path: Путь к директории ~/.acp-client/logs
    """
    logs_dir = get_acp_client_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str | None = None,
) -> structlog.BoundLogger:
    """Настраивает структурированное логирование для клиента.

    Логи выводятся только в файл, вывод в stdout/stderr отключен.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        json_format: Использовать JSON формат (True) или консольный (False)
        log_file: Путь к файлу логов. Если не указан, логи не сохраняются.
                 Поддерживает спецпути:
                 - "default" - использует ~/.acp-client/logs/acp-client.log
                 - абсолютный или относительный путь

    Returns:
        Настроенный logger

    Пример использования:
        logger = setup_logging(level="DEBUG", json_format=False)
        logger.info("client_request", method="session/prompt", session_id="sess_123")
        
        # С сохранением логов в файл
        logger = setup_logging(
            level="DEBUG",
            json_format=True,
            log_file="default"
        )
    """
    # Настройка уровня логирования
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Определение пути для файла логов
    file_path: Path | None = None
    if log_file:
        if log_file == "default":
            # Используем стандартный путь ~/.acp-client/logs/acp-client.log
            log_dir = get_logs_dir()
            file_path = log_dir / "acp-client.log"
        else:
            # Используем указанный путь
            file_path = Path(log_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)

    # Настройка стандартного logging только для файлового вывода
    # StreamHandler удалён - логи выводятся только в файл, не в stdout
    handlers: list[logging.Handler] = []

    # Добавляем файловый обработчик, если указан путь
    if file_path:
        # Используем RotatingFileHandler для ротации файлов
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # Храним 5 резервных копий
            encoding="utf-8",
        )
        handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
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

    # Конфигурация structlog с использованием stdlib logging для файловых логов
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        # Используем StandardLibLoggerFactory чтобы структурированные логи писались в файл
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("acp_client")
