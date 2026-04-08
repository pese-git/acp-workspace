from __future__ import annotations

from pathlib import Path

import pytest

from acp_client.tui.managers.filesystem import LocalFileSystemManager


def test_read_file_requires_absolute_path(tmp_path: Path) -> None:
    manager = LocalFileSystemManager()
    target = tmp_path / "example.txt"
    target.write_text("content", encoding="utf-8")

    with pytest.raises(ValueError, match="Path must be absolute"):
        manager.read_file("example.txt")


def test_read_file_supports_line_and_limit(tmp_path: Path) -> None:
    manager = LocalFileSystemManager()
    target = tmp_path / "example.txt"
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")

    content = manager.read_file(str(target), line=2, limit=1)

    assert content == "line2\n"


def test_write_file_creates_parent_dirs_and_notifies_callback(tmp_path: Path) -> None:
    written: list[Path] = []
    manager = LocalFileSystemManager(on_file_written=written.append)
    target = tmp_path / "nested" / "file.txt"

    manager.write_file(str(target), "hello")

    assert target.read_text(encoding="utf-8") == "hello"
    assert written == [target]


def test_write_file_requires_absolute_path() -> None:
    manager = LocalFileSystemManager()

    with pytest.raises(ValueError, match="Path must be absolute"):
        manager.write_file("relative.txt", "data")
