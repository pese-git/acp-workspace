"""Компоненты пользовательского интерфейса TUI.

Фаза 1 (Core Layout):
- MainLayout: главный контейнер с трехколоночной структурой
- StyledContainer, Card: универсальные контейнеры
- CollapsiblePanel, AccordionPanel: сворачиваемые панели
- HeaderBar, FooterBar: улучшенные header/footer
"""

from .chat_view import ChatView
from .chat_view_permission_manager import ChatViewPermissionManager
from .container import Card, ContainerVariant, StyledContainer
from .file_tree import FileTree
from .file_viewer import FileViewerModal
from .footer import AgentStatus, FooterBar
from .header import HeaderBar
from .help_modal import HelpModal
from .inline_permission_widget import InlinePermissionWidget
from .main_layout import MainLayout
from .panel import AccordionPanel, CollapsiblePanel
from .permission_modal import PermissionModal
from .plan_panel import PlanPanel
from .prompt_input import PromptInput
from .sidebar import Sidebar
from .terminal_log_modal import TerminalLogModal
from .terminal_output import TerminalOutputPanel
from .tool_panel import ToolPanel

__all__ = [
    # Layout компоненты (Фаза 1)
    "MainLayout",
    "StyledContainer",
    "ContainerVariant",
    "Card",
    "CollapsiblePanel",
    "AccordionPanel",
    # Header/Footer
    "HeaderBar",
    "FooterBar",
    "AgentStatus",
    # Sidebar
    "Sidebar",
    # Chat
    "ChatView",
    "ChatViewPermissionManager",
    # Files
    "FileTree",
    "FileViewerModal",
    # Input
    "PromptInput",
    # Modals
    "HelpModal",
    "PermissionModal",
    "InlinePermissionWidget",
    # Panels
    "PlanPanel",
    "TerminalLogModal",
    "TerminalOutputPanel",
    "ToolPanel",
]
