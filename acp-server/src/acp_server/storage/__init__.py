"""Модуль хранилища сессий ACP.

Предоставляет абстракцию для различных backend'ов хранения сессий.
"""

from ..exceptions import StorageError
from .base import SessionStorage
from .json_file import JsonFileStorage
from .memory import InMemoryStorage

__all__ = ["SessionStorage", "StorageError", "InMemoryStorage", "JsonFileStorage"]
