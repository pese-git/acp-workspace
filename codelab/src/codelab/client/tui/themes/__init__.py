"""Система тем для CodeLab TUI.

Предоставляет:
- ThemeManager: управление темами
- Theme: базовый класс темы
- DarkTheme, LightTheme: предустановленные темы
"""

from .manager import Theme, ThemeManager, ThemeType

__all__ = [
    "Theme",
    "ThemeManager",
    "ThemeType",
]
