"""ClientRPCService для вызова методов на клиенте.

Предоставляет асинхронный сервис для инициирования RPC вызовов на клиентской стороне.
Агент использует этот сервис для доступа к локальной среде клиента:
- Чтение/запись файлов
- Выполнение терминальных команд
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from pydantic import BaseModel

from .exceptions import (
    ClientCapabilityMissingError,
    ClientRPCError,
    ClientRPCResponseError,
    ClientRPCTimeoutError,
)
from .models import (
    ReadTextFileRequest,
    ReadTextFileResponse,
    TerminalCreateRequest,
    TerminalCreateResponse,
    TerminalKillRequest,
    TerminalKillResponse,
    TerminalOutputRequest,
    TerminalOutputResponse,
    TerminalReleaseRequest,
    TerminalReleaseResponse,
    TerminalWaitForExitRequest,
    TerminalWaitForExitResponse,
    WriteTextFileRequest,
    WriteTextFileResponse,
)

logger = structlog.get_logger()


class ClientRPCService:
    """Сервис для вызова методов на клиенте (Agent → Client RPC).

    Агент использует этот сервис для доступа к локальной среде клиента:
    - Чтение/запись файлов
    - Выполнение терминальных команд

    Attributes:
        _send_request: Функция для отправки JSON-RPC request
        _capabilities: Capabilities из initialize response
        _timeout: Timeout для ожидания ответа (секунды)
        _pending_requests: Словарь активных requests (request_id -> Future)
    """

    def __init__(
        self,
        send_request_callback: Callable,
        client_capabilities: dict,
        timeout: float = 30.0,
    ) -> None:
        """Инициализировать ClientRPCService.

        Args:
            send_request_callback: Функция для отправки JSON-RPC request.
                Ожидается сигнатура: async def send(request: dict) -> None
            client_capabilities: Capabilities из initialize response.
                Словарь вида {"fs": {"readTextFile": True}, "terminal": True}
            timeout: Timeout для ожидания ответа (секунды). По умолчанию 30 сек.
        """
        self._send_request = send_request_callback
        self._capabilities = client_capabilities
        self._timeout = timeout
        self._pending_requests: dict[str, asyncio.Future] = {}

    def _check_capability(self, capability_path: str) -> None:
        """Проверить наличие capability у клиента.

        Args:
            capability_path: Путь к capability (например, "fs.readTextFile").

        Raises:
            ClientCapabilityMissingError: Если capability отсутствует.
        """
        parts = capability_path.split(".")
        current: Any = self._capabilities

        for part in parts:
            if not isinstance(current, dict) or part not in current:
                raise ClientCapabilityMissingError(
                    f"Клиент не поддерживает capability: {capability_path}"
                )
            current = current[part]

        if not current:
            raise ClientCapabilityMissingError(
                f"Capability {capability_path} отключена"
            )

    async def _call_method(
        self,
        method: str,
        params: dict,
        response_model: type[BaseModel],
    ) -> Any:
        """Вызвать метод на клиенте и дождаться ответа.

        Args:
            method: Имя метода (например, "fs/read_text_file").
            params: Параметры запроса в виде словаря.
            response_model: Pydantic модель для парсинга ответа.

        Returns:
            Распарсенный response согласно response_model.

        Raises:
            ClientRPCTimeoutError: Timeout при ожидании ответа.
            ClientRPCResponseError: Ошибка от клиента.
            ClientRPCError: Некорректный ответ от клиента.
        """
        request_id = str(uuid.uuid4())
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # Отправить JSON-RPC request
            await self._send_request(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": params,
                }
            )

            logger.debug(
                "Отправлен RPC запрос на клиент",
                extra={"method": method, "request_id": request_id},
            )

            # Ждать ответ с timeout
            result = await asyncio.wait_for(future, timeout=self._timeout)

            # Парсить ответ
            return response_model.model_validate(result)

        except TimeoutError as err:
            raise ClientRPCTimeoutError(
                f"Timeout при вызове {method} (>{self._timeout}s)"
            ) from err
        finally:
            self._pending_requests.pop(request_id, None)

    def handle_response(self, response: dict) -> None:
        """Обработать ответ от клиента.

        Вызывается transport layer при получении JSON-RPC response.

        Args:
            response: JSON-RPC response от клиента вида:
                {"jsonrpc": "2.0", "id": "...", "result": {...}} или
                {"jsonrpc": "2.0", "id": "...", "error": {"code": -32001, ...}}
        """
        request_id = response.get("id")
        if not request_id or request_id not in self._pending_requests:
            logger.warning(
                "Получен ответ для неизвестного request_id",
                extra={"request_id": request_id},
            )
            return

        future = self._pending_requests[request_id]

        if "error" in response:
            error = response["error"]
            future.set_exception(
                ClientRPCResponseError(
                    code=error.get("code", -1),
                    message=error.get("message", "Unknown error"),
                    data=error.get("data"),
                )
            )
        elif "result" in response:
            future.set_result(response["result"])
        else:
            future.set_exception(
                ClientRPCError("Invalid response: missing 'result' or 'error'")
            )

    # ===== File System методы =====

    async def read_text_file(
        self,
        session_id: str,
        path: str,
        line: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Прочитать текстовый файл в окружении клиента.

        Args:
            session_id: ID сессии.
            path: Путь к файлу.
            line: Начальная строка (0-based, опционально).
            limit: Максимум строк (опционально).

        Returns:
            Содержимое файла.

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает fs.readTextFile.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("fs.readTextFile")

        request = ReadTextFileRequest(  # type: ignore[call-arg]
            session_id=session_id, path=path, line=line, limit=limit
        )

        response = await self._call_method(
            method="fs/read_text_file",
            params=request.model_dump(by_alias=True, exclude_none=True),
            response_model=ReadTextFileResponse,
        )

        return response.content

    async def write_text_file(
        self,
        session_id: str,
        path: str,
        content: str,
    ) -> bool:
        """Записать текстовый файл в окружении клиента.

        Args:
            session_id: ID сессии.
            path: Путь к файлу.
            content: Содержимое для записи.

        Returns:
            True при успехе.

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает fs.writeTextFile.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента (включая отказ в разрешении).
        """
        self._check_capability("fs.writeTextFile")

        request = WriteTextFileRequest(  # type: ignore[call-arg]
            session_id=session_id, path=path, content=content
        )

        response = await self._call_method(
            method="fs/write_text_file",
            params=request.model_dump(by_alias=True),
            response_model=WriteTextFileResponse,
        )

        return response.success

    # ===== Terminal методы =====

    async def create_terminal(
        self,
        session_id: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        output_byte_limit: int | None = None,
    ) -> str:
        """Создать терминал и запустить команду в окружении клиента.

        Args:
            session_id: ID сессии.
            command: Команда для выполнения.
            args: Аргументы команды (опционально).
            env: Переменные окружения (опционально).
            cwd: Рабочая директория (опционально).
            output_byte_limit: Лимит байт output (опционально).

        Returns:
            Terminal ID для дальнейшего использования.

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает terminal.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("terminal")

        request = TerminalCreateRequest(  # type: ignore[call-arg]
            session_id=session_id,
            command=command,
            args=args,
            env=env,
            cwd=cwd,
            output_byte_limit=output_byte_limit,
        )

        response = await self._call_method(
            method="terminal/create",
            params=request.model_dump(by_alias=True, exclude_none=True),
            response_model=TerminalCreateResponse,
        )

        return response.terminal_id

    async def terminal_output(
        self,
        session_id: str,
        terminal_id: str,
    ) -> tuple[str, bool, int | None]:
        """Получить текущий output терминала.

        Args:
            session_id: ID сессии.
            terminal_id: ID терминального сеанса.

        Returns:
            Кортеж (output, is_complete, exit_code).
            is_complete True если команда завершена.
            exit_code содержит код завершения (если завершена).

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает terminal.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("terminal")

        request = TerminalOutputRequest(  # type: ignore[call-arg]
            session_id=session_id, terminal_id=terminal_id
        )

        response = await self._call_method(
            method="terminal/output",
            params=request.model_dump(by_alias=True),
            response_model=TerminalOutputResponse,
        )

        return response.output, response.is_complete, response.exit_code

    async def wait_for_exit(
        self,
        session_id: str,
        terminal_id: str,
        timeout: float | None = None,
    ) -> tuple[str, int]:
        """Блокирующее ожидание завершения команды в терминале.

        Args:
            session_id: ID сессии.
            terminal_id: ID терминального сеанса.
            timeout: Timeout ожидания в секундах (опционально).

        Returns:
            Кортеж (output, exit_code).

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает terminal.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("terminal")

        request = TerminalWaitForExitRequest(  # type: ignore[call-arg]
            session_id=session_id, terminal_id=terminal_id, timeout=timeout
        )

        response = await self._call_method(
            method="terminal/wait_for_exit",
            params=request.model_dump(by_alias=True, exclude_none=True),
            response_model=TerminalWaitForExitResponse,
        )

        return response.output, response.exit_code

    async def kill_terminal(
        self,
        session_id: str,
        terminal_id: str,
        signal: str = "SIGTERM",
    ) -> bool:
        """Прервать команду в терминале.

        Args:
            session_id: ID сессии.
            terminal_id: ID терминального сеанса.
            signal: Сигнал для отправки (по умолчанию SIGTERM).

        Returns:
            True если сигнал успешно отправлен.

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает terminal.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("terminal")

        request = TerminalKillRequest(  # type: ignore[call-arg]
            session_id=session_id, terminal_id=terminal_id, signal=signal
        )

        response = await self._call_method(
            method="terminal/kill",
            params=request.model_dump(by_alias=True),
            response_model=TerminalKillResponse,
        )

        return response.success

    async def release_terminal(
        self,
        session_id: str,
        terminal_id: str,
    ) -> bool:
        """Освободить ресурсы терминала.

        Args:
            session_id: ID сессии.
            terminal_id: ID терминального сеанса.

        Returns:
            True если ресурсы успешно освобождены.

        Raises:
            ClientCapabilityMissingError: Клиент не поддерживает terminal.
            ClientRPCTimeoutError: Timeout.
            ClientRPCResponseError: Ошибка от клиента.
        """
        self._check_capability("terminal")

        request = TerminalReleaseRequest(  # type: ignore[call-arg]
            session_id=session_id, terminal_id=terminal_id
        )

        response = await self._call_method(
            method="terminal/release",
            params=request.model_dump(by_alias=True),
            response_model=TerminalReleaseResponse,
        )

        return response.success
