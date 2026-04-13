"""JSON файловое хранилище для сессий ACP."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles

from ..exceptions import StorageError
from ..models import AvailableCommand, HistoryMessage, PlanStep
from ..protocol.state import (
    ActiveTurnState,
    ClientRuntimeCapabilities,
    PendingClientRequestState,
    SessionState,
    ToolCallState,
)
from .base import SessionStorage


class JsonFileStorage(SessionStorage):
    """Хранилище сессий в JSON файлах.

    Каждая сессия сохраняется в отдельный файл:
    {base_path}/{session_id}.json

    Пример использования:
        storage = JsonFileStorage(Path.home() / ".acp" / "sessions")
        await storage.save_session(session)
        loaded = await storage.load_session(session_id)
    """

    def __init__(self, base_path: Path | str) -> None:
        """Инициализирует хранилище.

        Args:
            base_path: Директория для хранения JSON файлов
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Кэш для быстрого доступа
        self._cache: dict[str, SessionState] = {}

    def _session_file_path(self, session_id: str) -> Path:
        """Возвращает путь к файлу сессии."""
        # Экранировать session_id для безопасности
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self.base_path / f"{safe_id}.json"

    def _serialize_active_turn(self, active_turn: ActiveTurnState) -> dict[str, Any]:
        """Сериализует ActiveTurnState в dict для JSON."""
        return {
            "prompt_request_id": active_turn.prompt_request_id,
            "session_id": active_turn.session_id,
            "cancel_requested": active_turn.cancel_requested,
            "permission_request_id": active_turn.permission_request_id,
            "permission_tool_call_id": active_turn.permission_tool_call_id,
            "phase": active_turn.phase,
            "pending_client_request": (
                self._serialize_pending_client_request(active_turn.pending_client_request)
                if active_turn.pending_client_request
                else None
            ),
        }

    def _deserialize_active_turn(self, data: dict[str, Any]) -> ActiveTurnState:
        """Десериализует dict в ActiveTurnState."""
        return ActiveTurnState(
            prompt_request_id=data.get("prompt_request_id"),
            session_id=data["session_id"],
            cancel_requested=data.get("cancel_requested", False),
            permission_request_id=data.get("permission_request_id"),
            permission_tool_call_id=data.get("permission_tool_call_id"),
            phase=data.get("phase", "running"),
            pending_client_request=(
                self._deserialize_pending_client_request(data["pending_client_request"])
                if data.get("pending_client_request")
                else None
            ),
        )

    def _serialize_tool_call(self, tool_call: ToolCallState) -> dict[str, Any]:
        """Сериализует ToolCallState в dict для JSON."""
        return {
            "tool_call_id": tool_call.tool_call_id,
            "title": tool_call.title,
            "kind": tool_call.kind,
            "status": tool_call.status,
            "content": tool_call.content,
        }

    def _deserialize_tool_call(self, data: dict[str, Any]) -> ToolCallState:
        """Десериализует dict в ToolCallState."""
        return ToolCallState(
            tool_call_id=data["tool_call_id"],
            title=data["title"],
            kind=data["kind"],
            status=data["status"],
            content=data.get("content", []),
        )

    def _serialize_pending_client_request(
        self, pending: PendingClientRequestState,
    ) -> dict[str, Any]:
        """Сериализует PendingClientRequestState в dict для JSON."""
        return {
            "request_id": pending.request_id,
            "kind": pending.kind,
            "tool_call_id": pending.tool_call_id,
            "path": pending.path,
            "expected_new_text": pending.expected_new_text,
            "terminal_id": pending.terminal_id,
            "terminal_output": pending.terminal_output,
            "terminal_exit_code": pending.terminal_exit_code,
            "terminal_signal": pending.terminal_signal,
            "terminal_truncated": pending.terminal_truncated,
        }

    def _deserialize_pending_client_request(
        self, data: dict[str, Any],
    ) -> PendingClientRequestState:
        """Десериализует dict в PendingClientRequestState."""
        return PendingClientRequestState(
            request_id=data["request_id"],
            kind=data["kind"],
            tool_call_id=data["tool_call_id"],
            path=data["path"],
            expected_new_text=data.get("expected_new_text"),
            terminal_id=data.get("terminal_id"),
            terminal_output=data.get("terminal_output"),
            terminal_exit_code=data.get("terminal_exit_code"),
            terminal_signal=data.get("terminal_signal"),
            terminal_truncated=data.get("terminal_truncated"),
        )

    def _serialize_capabilities(
        self, caps: ClientRuntimeCapabilities,
    ) -> dict[str, Any]:
        """Сериализует ClientRuntimeCapabilities в dict для JSON."""
        return {
            "fs_read": caps.fs_read,
            "fs_write": caps.fs_write,
            "terminal": caps.terminal,
        }

    def _deserialize_capabilities(self, data: dict[str, Any]) -> ClientRuntimeCapabilities:
        """Десериализует dict в ClientRuntimeCapabilities."""
        return ClientRuntimeCapabilities(
            fs_read=data.get("fs_read", False),
            fs_write=data.get("fs_write", False),
            terminal=data.get("terminal", False),
        )

    def _serialize_session(self, session: SessionState) -> dict[str, Any]:
        """Сериализует SessionState в dict для JSON."""
        # Сериализовать историю, преобразуя Pydantic модели в dict
        history_serialized: list[dict[str, Any]] = []
        for entry in session.history:
            if isinstance(entry, HistoryMessage):
                # Использовать model_dump() для Pydantic моделей
                history_serialized.append(entry.model_dump(exclude_none=False))
            else:
                # Оставить dict как есть
                history_serialized.append(entry)

        # Сериализовать доступные команды
        available_commands_serialized: list[dict[str, Any]] = []
        for cmd in session.available_commands:
            if isinstance(cmd, AvailableCommand):
                available_commands_serialized.append(cmd.model_dump(exclude_none=False))
            else:
                available_commands_serialized.append(cmd)

        # Сериализовать план
        latest_plan_serialized: list[dict[str, Any]] = []
        for step in session.latest_plan:
            if isinstance(step, PlanStep):
                latest_plan_serialized.append(step.model_dump(exclude_none=False))
            else:
                latest_plan_serialized.append(step)

        return {
            "session_id": session.session_id,
            "cwd": session.cwd,
            "mcp_servers": session.mcp_servers,
            "title": session.title,
            "updated_at": session.updated_at,
            "config_values": session.config_values,
            "history": history_serialized,
            "events_history": session.events_history,
            "active_turn": (
                self._serialize_active_turn(session.active_turn)
                if session.active_turn
                else None
            ),
            "tool_call_counter": session.tool_call_counter,
            "tool_calls": {
                k: self._serialize_tool_call(v) for k, v in session.tool_calls.items()
            },
            "available_commands": available_commands_serialized,
            "latest_plan": latest_plan_serialized,
            "permission_policy": session.permission_policy,
            "cancelled_permission_requests": list(session.cancelled_permission_requests),
            "cancelled_client_rpc_requests": list(session.cancelled_client_rpc_requests),
            "runtime_capabilities": (
                self._serialize_capabilities(session.runtime_capabilities)
                if session.runtime_capabilities
                else None
            ),
        }

    def _deserialize_session(self, data: dict[str, Any]) -> SessionState:
        """Десериализует dict в SessionState."""
        # Десериализовать историю, преобразуя dict в Pydantic модели
        history_deserialized: list[HistoryMessage | dict[str, Any]] = []
        for entry in data.get("history", []):
            if isinstance(entry, dict):
                try:
                    # Попытаться создать HistoryMessage из dict
                    history_deserialized.append(HistoryMessage.model_validate(entry))
                except Exception:
                    # Если не получается, оставить как dict
                    history_deserialized.append(entry)
            else:
                history_deserialized.append(entry)

        # Десериализовать доступные команды
        available_commands_deserialized: list[AvailableCommand | dict[str, Any]] = []
        for cmd in data.get("available_commands", []):
            if isinstance(cmd, dict):
                try:
                    available_commands_deserialized.append(AvailableCommand.model_validate(cmd))
                except Exception:
                    available_commands_deserialized.append(cmd)
            else:
                available_commands_deserialized.append(cmd)

        # Десериализовать план
        latest_plan_deserialized: list[PlanStep | dict[str, Any]] = []
        for step in data.get("latest_plan", []):
            if isinstance(step, dict):
                try:
                    latest_plan_deserialized.append(PlanStep.model_validate(step))
                except Exception:
                    latest_plan_deserialized.append(step)
            else:
                latest_plan_deserialized.append(step)

        return SessionState(
            session_id=data["session_id"],
            cwd=data["cwd"],
            mcp_servers=data["mcp_servers"],
            title=data.get("title"),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            config_values=data.get("config_values", {}),
            history=history_deserialized,
            events_history=data.get("events_history", []),
            active_turn=(
                self._deserialize_active_turn(data["active_turn"])
                if data.get("active_turn")
                else None
            ),
            tool_call_counter=data.get("tool_call_counter", 0),
            tool_calls={
                k: self._deserialize_tool_call(v)
                for k, v in data.get("tool_calls", {}).items()
            },
            available_commands=available_commands_deserialized,
            latest_plan=latest_plan_deserialized,
            permission_policy=data.get("permission_policy", {}),
            cancelled_permission_requests=set(
                data.get("cancelled_permission_requests", [])
            ),
            cancelled_client_rpc_requests=set(
                data.get("cancelled_client_rpc_requests", [])
            ),
            runtime_capabilities=(
                self._deserialize_capabilities(data["runtime_capabilities"])
                if data.get("runtime_capabilities")
                else None
            ),
        )

    async def save_session(self, session: SessionState) -> None:
        """Сохраняет сессию в JSON файл.

        Args:
            session: Состояние сессии для сохранения.

        Raises:
            StorageError: При ошибке сохранения.
        """
        try:
            # Обновить временную метку
            session.updated_at = datetime.now(UTC).isoformat()
            file_path = self._session_file_path(session.session_id)
            data = self._serialize_session(session)

            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))

            # Обновить кэш
            self._cache[session.session_id] = session

        except Exception as e:
            raise StorageError(f"Failed to save session {session.session_id}: {e}") from e

    async def load_session(self, session_id: str) -> SessionState | None:
        """Загружает сессию из JSON файла.

        Args:
            session_id: Идентификатор сессии.

        Returns:
            SessionState если найдена, None если не существует.

        Raises:
            StorageError: При ошибке загрузки.
        """
        # Проверить кэш
        if session_id in self._cache:
            return self._cache[session_id]

        try:
            file_path = self._session_file_path(session_id)
            if not file_path.exists():
                return None

            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            session = self._deserialize_session(data)
            self._cache[session_id] = session
            return session

        except json.JSONDecodeError as e:
            raise StorageError(
                f"Failed to parse session file {session_id}: invalid JSON"
            ) from e
        except Exception as e:
            raise StorageError(f"Failed to load session {session_id}: {e}") from e

    async def delete_session(self, session_id: str) -> bool:
        """Удаляет JSON файл сессии.

        Args:
            session_id: Идентификатор сессии.

        Returns:
            True если сессия была удалена, False если не существовала.

        Raises:
            StorageError: При ошибке удаления.
        """
        try:
            file_path = self._session_file_path(session_id)
            if file_path.exists():
                file_path.unlink()
                self._cache.pop(session_id, None)
                return True
            return False
        except Exception as e:
            raise StorageError(f"Failed to delete session {session_id}: {e}") from e

    async def list_sessions(
        self,
        cwd: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[SessionState], str | None]:
        """Возвращает список сессий из файлов.

        Args:
            cwd: Фильтр по рабочей директории (опционально).
            cursor: Курсор для пагинации (session_id последней сессии предыдущей страницы).
            limit: Максимальное количество сессий на странице.

        Returns:
            Кортеж (список сессий, следующий курсор или None).

        Raises:
            StorageError: При ошибке получения списка.
        """
        try:
            # Загрузить все сессии
            sessions: list[SessionState] = []
            for file_path in self.base_path.glob("*.json"):
                session_id = file_path.stem
                session = await self.load_session(session_id)
                if session:
                    sessions.append(session)

            # Фильтрация по cwd
            if cwd:
                sessions = [s for s in sessions if s.cwd == cwd]

            # Сортировка по updated_at (новые первыми)
            sessions.sort(key=lambda s: s.updated_at, reverse=True)

            # Пагинация с курсором
            start_index = 0
            if cursor:
                for i, s in enumerate(sessions):
                    if s.session_id == cursor:
                        start_index = i + 1
                        break

            page = sessions[start_index : start_index + limit]
            next_cursor = (
                page[-1].session_id
                if len(sessions) > start_index + limit and page
                else None
            )

            return page, next_cursor

        except Exception as e:
            raise StorageError(f"Failed to list sessions: {e}") from e

    async def session_exists(self, session_id: str) -> bool:
        """Проверяет существование файла сессии.

        Args:
            session_id: Идентификатор сессии.

        Returns:
            True если сессия существует, False иначе.
        """
        return self._session_file_path(session_id).exists()
