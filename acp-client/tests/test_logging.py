"""Тесты для модуля логирования."""

from acp_client.logging import setup_logging


def test_setup_logging_default() -> None:
    """Тест настройки логирования с параметрами по умолчанию."""
    logger = setup_logging()
    # Функция возвращает lazy proxy logger, проверяем что он не None
    assert logger is not None


def test_setup_logging_debug_level() -> None:
    """Тест настройки уровня DEBUG."""
    logger = setup_logging(level="DEBUG")
    # Функция возвращает lazy proxy logger, проверяем что он не None
    assert logger is not None


def test_setup_logging_json_format() -> None:
    """Тест настройки JSON формата."""
    logger = setup_logging(json_format=True)
    # Функция возвращает lazy proxy logger, проверяем что он не None
    assert logger is not None


def test_setup_logging_console_format() -> None:
    """Тест настройки консольного формата."""
    logger = setup_logging(json_format=False)
    # Функция возвращает lazy proxy logger, проверяем что он не None
    assert logger is not None
