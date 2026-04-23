"""Общие фикстуры для тестов codelab."""

import pytest


@pytest.fixture
def sample_session_id() -> str:
    """Примерный ID сессии для тестов."""
    return "test-session-123"


@pytest.fixture
def sample_message_content() -> str:
    """Примерный текст сообщения для тестов."""
    return "Hello, ACP!"
