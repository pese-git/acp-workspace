"""Структурированное логирование с использованием structlog.

Модуль предоставляет настройку логирования для development и production.
Поддерживает JSON формат для production и цветной консольный формат для development.
Позволяет сохранять логи в файл с автоматической ротацией.

Пример использования:
    logger = setup_logging(level="INFO", json_format=False)
    logger.info("server started", port=8080)
    
    # С сохранением логов в файл
    logger = setup_logging(level="DEBUG", json_format=False, log_file="default")
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

import structlog


def get_acp_server_dir() -> Path:
    """Получить директорию ~/.acp-server с автоматическим созданием.
    
    Returns:
        Path: Путь к директории ~/.acp-server
    """
    acp_dir = Path.home() / ".acp-server"
    acp_dir.mkdir(parents=True, exist_ok=True)
    return acp_dir


def get_logs_dir() -> Path:
    """Получить директорию ~/.acp-server/logs с автоматическим созданием.
    
    Returns:
        Path: Путь к директории ~/.acp-server/logs
    """
    logs_dir = get_acp_server_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str | None = None,
) -> structlog.BoundLogger:
    """Настраивает структурированное логирование.

    Аргументы:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR). По умолчанию INFO.
        json_format: Использовать JSON формат вместо цветной консоли. По умолчанию False.
        log_file: Путь к файлу логов. Если не указан, логи не сохраняются в файл.
                 Поддерживает спецпути:
                 - "default" - использует ~/.acp-server/logs/acp-server.log
                 - абсолютный или относительный путь

    Возвращает:
        Настроенный BoundLogger для использования в приложении.

    Пример использования:
        logger = setup_logging(level="DEBUG", json_format=False)
        logger.info("application started")
        
        # С сохранением логов в файл
        logger = setup_logging(level="DEBUG", json_format=True, log_file="default")
    """

    # Преобразуем строковый уровень в константу logging
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Определение пути для файла логов
    file_path: Path | None = None
    if log_file:
        if log_file == "default":
            # Используем стандартный путь ~/.acp-server/logs/acp-server.log
            log_dir = get_logs_dir()
            file_path = log_dir / "acp-server.log"
        else:
            # Используем указанный путь
            file_path = Path(log_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)

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

    # Конфигурируем обработчики логирования
    handlers: list[logging.Handler] = []
    
    # Всегда добавляем обработчик для вывода в консоль
    handlers.append(logging.StreamHandler(sys.stdout))
    
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

    # Конфигурируем стандартный logging
    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=log_level,
    )

    # Конфигурируем structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Получаем и возвращаем конфигурированный logger
    logger = structlog.get_logger()
    return logger
