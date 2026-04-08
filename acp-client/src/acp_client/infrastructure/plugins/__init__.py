"""Plugins infrastructure - система плагинов для расширяемости.

Содержит базовые классы для плагинов, контекст выполнения и менеджер плагинов.
"""

from acp_client.infrastructure.plugins.base import (
    ConfigurablePlugin,
    EventPlugin,
    HandlerPlugin,
    Plugin,
    PluginError,
    PluginInitializationError,
    PluginLoadError,
    PluginNotFoundError,
)
from acp_client.infrastructure.plugins.context import PluginContext
from acp_client.infrastructure.plugins.manager import PluginManager

__all__ = [
    "Plugin",
    "HandlerPlugin",
    "EventPlugin",
    "ConfigurablePlugin",
    "PluginContext",
    "PluginManager",
    "PluginError",
    "PluginLoadError",
    "PluginInitializationError",
    "PluginNotFoundError",
]
