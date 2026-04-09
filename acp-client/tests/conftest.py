"""Общие pytest fixtures для всех тестов acp-client."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

if TYPE_CHECKING:
    from acp_client.presentation.chat_view_model import ChatViewModel
    from acp_client.presentation.session_view_model import SessionViewModel


@pytest.fixture
def mock_session_view_model() -> SessionViewModel:
    """Создать mock SessionViewModel для тестов компонентов."""
    mock_vm: SessionViewModel = Mock()
    # Инициализируем Observable свойства
    mock_vm.sessions = Mock()
    mock_vm.sessions.subscribe = Mock()
    mock_vm.selected_session_id = Mock()
    mock_vm.selected_session_id.subscribe = Mock()
    mock_vm.is_loading_sessions = Mock()
    mock_vm.is_loading_sessions.subscribe = Mock()
    return mock_vm


@pytest.fixture
def mock_chat_view_model() -> ChatViewModel:
    """Создать mock ChatViewModel для тестов компонентов."""
    mock_vm: ChatViewModel = Mock()
    # Инициализируем Observable свойства
    mock_vm.messages = Mock()
    mock_vm.messages.subscribe = Mock()
    mock_vm.tool_calls = Mock()
    mock_vm.tool_calls.subscribe = Mock()
    mock_vm.is_streaming = Mock()
    mock_vm.is_streaming.subscribe = Mock()
    mock_vm.streaming_text = Mock()
    mock_vm.streaming_text.subscribe = Mock()
    return mock_vm
