"""Модуль хранилища сессий ACP.

Предоставляет абстракцию для различных backend'ов хранения сессий.
"""

from .base import SessionStorage, StorageError
from .json_file import JsonFileStorage
from .memory import InMemoryStorage

__all__ = ["SessionStorage", "StorageError", "InMemoryStorage", "JsonFileStorage"]
