"""Модуль хранилища сессий ACP.

Предоставляет абстракцию для различных backend'ов хранения сессий.
"""

from .base import SessionStorage, StorageError
from .memory import InMemoryStorage

__all__ = ["SessionStorage", "StorageError", "InMemoryStorage"]
