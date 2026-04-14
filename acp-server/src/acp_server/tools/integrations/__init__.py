"""Интеграционные адаптеры для executors инструментов.

Включает адаптеры для ClientRPCService и PermissionManager.
"""

from acp_server.tools.integrations.client_rpc_bridge import ClientRPCBridge
from acp_server.tools.integrations.permission_checker import PermissionChecker

__all__ = [
    "ClientRPCBridge",
    "PermissionChecker",
]
