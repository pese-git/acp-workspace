"""Тесты для FileSystemExecutor.

Проверяют:
- Чтение файлов
- Запись файлов
- Валидацию путей (защита от path traversal)
- Обработку ошибок
"""

from pathlib import Path

import pytest

from codelab.client.infrastructure.services.file_system_executor import FileSystemExecutor

# Маркируем все async тесты в модуле
pytestmark = pytest.mark.asyncio


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Временная директория для тестов."""
    return tmp_path


@pytest.fixture
def executor_with_sandbox(temp_dir: Path) -> FileSystemExecutor:
    """Executor с sandbox ограничением."""
    return FileSystemExecutor(base_path=temp_dir)


@pytest.fixture
def executor_without_sandbox() -> FileSystemExecutor:
    """Executor без sandbox ограничения."""
    return FileSystemExecutor()


class TestFileSystemExecutorReadFile:
    """Тесты для чтения файлов."""

    async def test_read_full_file(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест чтения полного файла."""
        # Подготовка
        test_file = temp_dir / "test.txt"
        test_content = "Hello, World!\nLine 2\nLine 3\n"
        test_file.write_text(test_content)

        # Действие
        result = await executor_with_sandbox.read_text_file("test.txt")

        # Проверка
        assert result == test_content

    async def test_read_file_with_line_and_limit(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест чтения диапазона строк."""
        # Подготовка
        test_file = temp_dir / "test.txt"
        lines = ["Line 1\n", "Line 2\n", "Line 3\n", "Line 4\n"]
        test_file.write_text("".join(lines))

        # Действие
        result = await executor_with_sandbox.read_text_file(
            "test.txt", line=2, limit=2
        )

        # Проверка
        assert result == "Line 2\nLine 3\n"

    async def test_read_file_not_found(
        self, executor_with_sandbox: FileSystemExecutor
    ) -> None:
        """Тест ошибки когда файл не найден."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            await executor_with_sandbox.read_text_file("nonexistent.txt")

    async def test_read_directory_as_file(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест ошибки при попытке читать директорию как файл."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        with pytest.raises(ValueError, match="Not a file"):
            await executor_with_sandbox.read_text_file("subdir")

    async def test_path_traversal_protection(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест защиты от path traversal атак."""
        with pytest.raises(ValueError, match="Path traversal"):
            await executor_with_sandbox.read_text_file("../../../etc/passwd")

    async def test_read_with_absolute_path(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест чтения с абсолютным путем (в пределах sandbox)."""
        test_file = temp_dir / "test.txt"
        test_content = "Hello\n"
        test_file.write_text(test_content)

        result = await executor_with_sandbox.read_text_file(str(test_file))
        assert result == test_content


class TestFileSystemExecutorWriteFile:
    """Тесты для записи файлов."""

    async def test_write_new_file(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест записи нового файла."""
        # Действие
        result = await executor_with_sandbox.write_text_file(
            "new_file.txt", "New content\n"
        )

        # Проверка
        assert result is True
        assert (temp_dir / "new_file.txt").read_text() == "New content\n"

    async def test_write_overwrites_existing(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест перезаписи существующего файла."""
        # Подготовка
        test_file = temp_dir / "test.txt"
        test_file.write_text("Old content\n")

        # Действие
        result = await executor_with_sandbox.write_text_file(
            "test.txt", "New content\n"
        )

        # Проверка
        assert result is True
        assert test_file.read_text() == "New content\n"

    async def test_write_creates_parent_dirs(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест создания родительских директорий."""
        # Действие
        result = await executor_with_sandbox.write_text_file(
            "subdir/nested/file.txt", "Content\n"
        )

        # Проверка
        assert result is True
        assert (temp_dir / "subdir" / "nested" / "file.txt").read_text() == "Content\n"

    async def test_write_path_traversal_protection(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест защиты от path traversal при записи."""
        with pytest.raises(ValueError, match="Path traversal"):
            await executor_with_sandbox.write_text_file(
                "../../etc/passwd", "hacked"
            )

    async def test_write_empty_file(
        self,
        temp_dir: Path,
        executor_with_sandbox: FileSystemExecutor,
    ) -> None:
        """Тест записи пустого файла."""
        result = await executor_with_sandbox.write_text_file("empty.txt", "")
        assert result is True
        assert (temp_dir / "empty.txt").read_text() == ""


class TestFileSystemExecutorWithoutSandbox:
    """Тесты для executor без sandbox ограничения."""

    async def test_read_file_anywhere(
        self, tmp_path: Path, executor_without_sandbox: FileSystemExecutor
    ) -> None:
        """Тест чтения файла без sandbox ограничения."""
        # Подготовка
        test_file = tmp_path / "test.txt"
        test_content = "Test content\n"
        test_file.write_text(test_content)

        # Действие (используем абсолютный путь)
        result = await executor_without_sandbox.read_text_file(str(test_file))

        # Проверка
        assert result == test_content

    async def test_write_file_anywhere(
        self, tmp_path: Path, executor_without_sandbox: FileSystemExecutor
    ) -> None:
        """Тест записи файла без sandbox ограничения."""
        test_file = tmp_path / "test.txt"

        result = await executor_without_sandbox.write_text_file(
            str(test_file), "Test content\n"
        )
        assert result is True
        assert test_file.read_text() == "Test content\n"
