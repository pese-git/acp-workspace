"""Менеджер сессий для TUI приложения."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

from acp_client.messages import SessionListItem, SessionSetupResult, SessionUpdateNotification


class SessionConnection(Protocol):
    """Минимальный контракт connection manager для SessionManager."""

    async def list_sessions(self) -> list[SessionListItem]:
        """Возвращает список сессий."""

        ...

    async def create_session(self, cwd: str) -> Any:
        """Создает сессию и возвращает объект с sessionId."""

        ...

    async def load_session(
        self,
        session_id: str,
        cwd: str,
    ) -> tuple[SessionSetupResult, list[SessionUpdateNotification]]:
        """Загружает существующую сессию."""

        ...

    async def send_prompt(
        self,
        *,
        session_id: str,
        text: str,
        on_update: Callable[[dict[str, Any]], None] | None,
        on_permission: Callable[[dict[str, Any]], str | None | Awaitable[str | None]] | None,
    ) -> Any:
        """Отправляет prompt в активную сессию."""

        ...

    async def cancel_prompt(self, session_id: str) -> None:
        """Отправляет отмену выполнения."""

        ...


class SessionManager:
    """Хранит активную сессию и упрощает вызовы ACP для UI."""

    def __init__(self, connection: SessionConnection) -> None:
        """Принимает connection manager и инициализирует локальное состояние."""

        self._connection = connection
        self._sessions: list[SessionListItem] = []
        self._active_session_id: str | None = None
        self._active_cwd: str = str(Path.cwd())
        self._last_replay_updates: list[SessionUpdateNotification] = []

    @property
    def active_session_id(self) -> str | None:
        """Возвращает ID текущей активной сессии."""

        return self._active_session_id

    @property
    def sessions(self) -> list[SessionListItem]:
        """Возвращает кэшированный список сессий."""

        return self._sessions

    @property
    def active_cwd(self) -> str:
        """Возвращает cwd активной сессии или последнее известное значение."""

        return self._active_cwd

    @property
    def last_replay_updates(self) -> list[SessionUpdateNotification]:
        """Возвращает replay updates последней операции load session."""

        return self._last_replay_updates

    async def refresh_sessions(self) -> list[SessionListItem]:
        """Перезагружает список сессий с сервера и обновляет кэш."""

        self._sessions = await self._connection.list_sessions()
        return self._sessions

    async def ensure_active_session(self) -> str:
        """Гарантирует наличие активной сессии, создавая ее при необходимости."""

        if self._active_session_id is not None:
            return self._active_session_id

        if self._sessions:
            return await self.activate_session(self._sessions[0].sessionId)

        created = await self._connection.create_session(cwd=self._active_cwd)
        if created.sessionId is None:
            msg = "Server returned session/new without sessionId"
            raise RuntimeError(msg)
        self._active_session_id = created.sessionId
        await self.refresh_sessions()
        self._last_replay_updates = []
        return created.sessionId

    async def create_and_activate_session(self, cwd: str | None = None) -> str:
        """Создает новую сессию и делает ее активной независимо от текущей."""

        target_cwd = cwd if isinstance(cwd, str) and cwd else self._active_cwd
        created = await self._connection.create_session(cwd=target_cwd)
        if created.sessionId is None:
            msg = "Server returned session/new without sessionId"
            raise RuntimeError(msg)
        self._active_session_id = created.sessionId
        self._active_cwd = target_cwd
        await self.refresh_sessions()
        self._last_replay_updates = []
        return created.sessionId

    async def activate_session(self, session_id: str) -> str:
        """Активирует существующую сессию и загружает ее состояние с сервера."""

        session_item = self._find_session(session_id)
        if session_item is None:
            msg = f"Session not found: {session_id}"
            raise ValueError(msg)
        _state, replay_updates = await self._connection.load_session(
            session_id=session_id,
            cwd=session_item.cwd,
        )
        self._active_session_id = session_id
        self._active_cwd = session_item.cwd
        self._last_replay_updates = replay_updates
        return session_id

    async def activate_next_session(self) -> str | None:
        """Переключает фокус на следующую сессию в списке."""

        if not self._sessions:
            return None
        next_index = self._active_index() + 1
        if next_index >= len(self._sessions):
            next_index = 0
        target = self._sessions[next_index]
        return await self.activate_session(target.sessionId)

    async def activate_previous_session(self) -> str | None:
        """Переключает фокус на предыдущую сессию в списке."""

        if not self._sessions:
            return None
        prev_index = self._active_index() - 1
        if prev_index < 0:
            prev_index = len(self._sessions) - 1
        target = self._sessions[prev_index]
        return await self.activate_session(target.sessionId)

    async def send_prompt(
        self,
        text: str,
        on_update: Callable[[dict[str, Any]], None],
        on_permission: Callable[[dict[str, Any]], str | None | Awaitable[str | None]] | None,
    ) -> None:
        """Отправляет prompt в активную сессию и прокидывает update callback."""

        session_id = await self.ensure_active_session()
        await self._connection.send_prompt(
            session_id=session_id,
            text=text,
            on_update=on_update,
            on_permission=on_permission,
        )

    async def cancel(self) -> None:
        """Отменяет текущее выполнение в активной сессии."""

        session_id = self._active_session_id
        if session_id is None:
            return
        await self._connection.cancel_prompt(session_id)

    def _active_index(self) -> int:
        """Возвращает индекс активной сессии или 0, если активная не найдена."""

        if self._active_session_id is None:
            return 0
        for index, item in enumerate(self._sessions):
            if item.sessionId == self._active_session_id:
                return index
        return 0

    def _find_session(self, session_id: str) -> SessionListItem | None:
        """Возвращает элемент списка сессий по его идентификатору."""

        for item in self._sessions:
            if item.sessionId == session_id:
                return item
        return None
