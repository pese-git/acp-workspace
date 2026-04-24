"""Модуль структурированного логирования для CodeLab.

Предоставляет настройку логирования с поддержкой JSON и консольного формата.
Поддерживает сохранение логов в файл в директорию ~/.codelab/logs/

Использует structlog для структурированного логирования с timestamps,
уровнями логов и поддержкой контекстных переменных.

Пример использования:
    # Базовая настройка
    logger = setup_logging(level="DEBUG")
    logger.info("app_started", version="1.0.0")

    # С сохранением в файл
    logger = setup_logging(level="INFO", log_file="default")
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Any

import structlog


def get_codelab_dir() -> Path:
    """Получить директорию ~/.codelab с автоматическим созданием.

    Директория используется для хранения конфигурации,
    логов и других данных приложения.

    Returns:
        Путь к директории ~/.codelab
    """
    codelab_dir = Path.home() / ".codelab"
    codelab_dir.mkdir(parents=True, exist_ok=True)
    return codelab_dir


def get_logs_dir(log_dir: Path | None = None) -> Path:
    """Получить директорию для логов с автоматическим созданием.

    Args:
        log_dir: Кастомная директория для логов. Если None,
                 используется ~/.codelab/logs/

    Returns:
        Путь к директории логов
    """
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    logs_dir = get_codelab_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str | None = None,
    log_dir: Path | None = None,
    console_output: bool = False,
) -> structlog.BoundLogger:
    """Настраивает структурированное логирование для CodeLab.

    По умолчанию логи выводятся только в файл (если указан), вывод в stdout/stderr
    отключен, чтобы не мешать работе TUI. Для серверного режима (serve) можно
    включить console_output для вывода логов в терминал.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR).
        json_format: Использовать JSON формат (True) или консольный (False).
        log_file: Путь к файлу логов. Поддерживает спецпути:
                  - None - логи не сохраняются в файл
                  - "default" - использует ~/.codelab/logs/codelab.log
                  - абсолютный или относительный путь
        log_dir: Кастомная директория для логов (опционально).
                 Используется вместо ~/.codelab/logs/ если указана.
        console_output: Выводить логи в консоль (stdout). По умолчанию False.
                        Включите для режима serve, где TUI не используется.

    Returns:
        Настроенный структурированный logger.

    Пример использования:
        # Только DEBUG логирование без файла
        logger = setup_logging(level="DEBUG")
        logger.info("request_received", method="session/prompt")

        # С сохранением в файл по умолчанию
        logger = setup_logging(
            level="INFO",
            json_format=True,
            log_file="default"
        )

        # Серверный режим с выводом в консоль и файл
        logger = setup_logging(
            level="INFO",
            log_file="default",
            console_output=True
        )
    """
    # Настройка уровня логирования
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Определение пути для файла логов
    file_path: Path | None = None
    if log_file:
        if log_file == "default":
            # Используем стандартный путь ~/.codelab/logs/codelab.log
            logs_directory = get_logs_dir(log_dir)
            file_path = logs_directory / "codelab.log"
        else:
            # Используем указанный путь
            file_path = Path(log_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)

    # Настройка обработчиков логирования
    handlers: list[logging.Handler] = []

    # Добавляем консольный обработчик для режима serve (где нет TUI)
    if console_output:
        stream_handler = logging.StreamHandler()
        handlers.append(stream_handler)

    # Добавляем файловый обработчик, если указан путь
    if file_path:
        # Используем RotatingFileHandler для ротации файлов
        file_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB максимальный размер файла
            backupCount=5,  # Храним 5 резервных копий
            encoding="utf-8",
        )
        handlers.append(file_handler)

    # Базовая конфигурация logging
    logging.basicConfig(
        format="%(message)s",
        handlers=handlers,
        level=log_level,
    )

    # Процессоры для structlog — определяют обработку сообщений
    processors: list[Any] = [
        # Объединяем контекстные переменные в сообщение
        structlog.contextvars.merge_contextvars,
        # Добавляем уровень логирования
        structlog.processors.add_log_level,
        # Добавляем timestamp в ISO формате (UTC)
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Добавляем информацию о стеке вызовов
        structlog.processors.StackInfoRenderer(),
        # Форматируем информацию об исключениях
        structlog.processors.format_exc_info,
        # Декодируем Unicode
        structlog.processors.UnicodeDecoder(),
    ]

    # Выбор рендерера в зависимости от формата
    if json_format:
        # JSON формат для машинной обработки
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Консольный формат для человеко-читаемых логов
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
        # Используем StandardLibLoggerFactory чтобы логи писались в файл
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("codelab")
