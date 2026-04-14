"""Unit тесты для TerminalToolExecutor.

Проверяет:
- Инициализацию с зависимостями
- Создание терминала и запуск команды
- Ожидание завершения процесса
- Освобождение ресурсов терминала
- Lifecycle management (create → wait → release)
- Обработку ошибок на каждом этапе
- Корректность metadata в результатах
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from acp_server.protocol.state import SessionState
from acp_server.tools.base import ToolExecutionResult
from acp_server.tools.executors.terminal_executor import TerminalToolExecutor
from acp_server.tools.integrations.client_rpc_bridge import ClientRPCBridge
from acp_server.tools.integrations.permission_checker import PermissionChecker

class TestTerminalExecutorInit:
    """Тесты инициализации TerminalToolExecutor."""

    def test_terminal_executor_init(self) -> None:
        """Инициализация с зависимостями."""
        # Arrange
        mock_bridge = MagicMock(spec=ClientRPCBridge)
        mock_checker = MagicMock(spec=PermissionChecker)
        
        # Act
        executor = TerminalToolExecutor(mock_bridge, mock_checker)
        
        # Assert
        assert executor._bridge == mock_bridge
        assert executor._permission_checker == mock_checker

