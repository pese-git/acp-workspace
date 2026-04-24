"""Тесты для модуля логирования."""

from pathlib import Path
from tempfile import TemporaryDirectory

from codelab.shared.logging import setup_logging


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


def test_setup_logging_with_file() -> None:
    """Тест настройки логирования с сохранением в файл."""
    with TemporaryDirectory() as tmpdir:
        log_file = str(Path(tmpdir) / "test.log")
        logger = setup_logging(log_file=log_file)
        assert logger is not None
        # Проверяем что файл создан
        assert Path(log_file).exists()


def test_setup_logging_with_default_file_path() -> None:
    """Тест настройки логирования с путем по умолчанию 'default'."""
    logger = setup_logging(log_file="default")
    assert logger is not None
    # Проверяем что директория создана
    home = Path.home()
    log_dir = home / ".acp-client" / "logs"
    assert log_dir.exists()
    # Проверяем что файл создан
    log_file = log_dir / "acp-client.log"
    assert log_file.exists()
