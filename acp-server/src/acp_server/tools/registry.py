"""Простая реализация реестра инструментов для системы tools."""

from collections.abc import Callable
from typing import Any

from acp_server.tools.base import ToolDefinition, ToolExecutionResult


class SimpleToolRegistry:
    """Простой реестр инструментов с хранением в памяти.
    
    Хранит определения инструментов и их обработчики (handlers).
    Позволяет регистрировать, получать и выполнять инструменты.
    """

    def __init__(self) -> None:
        """Инициализация реестра."""
        # Словарь для хранения определений инструментов
        self._tools: dict[str, ToolDefinition] = {}
        # Словарь для хранения обработчиков инструментов
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        tool: ToolDefinition,
        handler: Callable,
    ) -> None:
        """Регистрация инструмента и его обработчика.
        
        Args:
            tool: Определение инструмента (ToolDefinition)
            handler: Callable обработчик инструмента
            
        Raises:
            ValueError: Если имя инструмента пустое
        """
        # Проверка, что имя инструмента не пустое
        if not tool.name or not tool.name.strip():
            raise ValueError("Имя инструмента не может быть пустым")
        
        # Регистрация инструмента и его обработчика
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def get(self, name: str) -> ToolDefinition | None:
        """Получение определения инструмента по имени.
        
        Args:
            name: Имя инструмента
            
        Returns:
            Определение инструмента или None, если не найден
        """
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        """Получение списка всех зарегистрированных инструментов.
        
        Returns:
            Список определений инструментов
        """
        return list(self._tools.values())

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Выполнение инструмента по имени с переданными аргументами.
        
        Args:
            name: Имя инструмента
            arguments: Словарь аргументов для обработчика
            
        Returns:
            Результат выполнения (ToolExecutionResult)
            
        Raises:
            ValueError: Если инструмент не найден
        """
        # Проверка существования инструмента
        if name not in self._tools:
            return ToolExecutionResult(
                success=False,
                error=f"Инструмент '{name}' не найден в реестре",
            )
        
        # Получение обработчика
        handler = self._handlers[name]
        
        try:
            # Выполнение обработчика с аргументами
            output = handler(**arguments)
            
            # Преобразование вывода в строку если необходимо
            output_str = str(output) if output is not None else None
            
            return ToolExecutionResult(
                success=True,
                output=output_str,
            )
        except Exception as exc:
            # Обработка исключений при выполнении
            error_msg = f"Ошибка при выполнении инструмента '{name}': {str(exc)}"
            return ToolExecutionResult(
                success=False,
                error=error_msg,
            )
