"""Stdio транспорт для MCP (Model Context Protocol).

Реализует асинхронную коммуникацию с MCP сервером через stdin/stdout subprocess.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from .models import MCPNotification, MCPRequest, MCPResponse

logger = logging.getLogger(__name__)


class StdioTransportError(Exception):
    """Базовое исключение для ошибок транспорта."""
    pass


class ProcessNotStartedError(StdioTransportError):
    """Процесс MCP сервера не запущен."""
    pass


class ProcessExitedError(StdioTransportError):
    """Процесс MCP сервера неожиданно завершился."""
    
    def __init__(self, message: str, return_code: int | None = None):
        super().__init__(message)
        self.return_code = return_code


class StdioTransport:
    """Асинхронный stdio транспорт для коммуникации с MCP сервером.
    
    Запускает MCP сервер как subprocess и обеспечивает асинхронный обмен
    JSON-RPC 2.0 сообщениями через stdin/stdout. Stderr используется для логов.
    
    Attributes:
        command: Команда для запуска MCP сервера.
        args: Аргументы командной строки.
        env: Переменные окружения для процесса.
    
    Example:
        >>> transport = StdioTransport()
        >>> await transport.start("mcp-server", ["--stdio"])
        >>> response = await transport.send_request("initialize", {...})
        >>> await transport.close()
    """
    
    def __init__(self) -> None:
        """Инициализация транспорта."""
        self._process: asyncio.subprocess.Process | None = None
        self._request_id: int = 0
        self._pending_requests: dict[int | str, asyncio.Future[MCPResponse]] = {}
        self._read_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._closed: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
    
    @property
    def is_running(self) -> bool:
        """Проверить, запущен ли процесс MCP сервера."""
        return (
            self._process is not None 
            and self._process.returncode is None
            and not self._closed
        )
    
    async def start(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        """Запустить MCP сервер как subprocess.
        
        Args:
            command: Команда для запуска (путь к исполняемому файлу).
            args: Аргументы командной строки.
            env: Дополнительные переменные окружения.
            cwd: Рабочая директория для процесса.
        
        Raises:
            StdioTransportError: Если не удалось запустить процесс.
        """
        if self._process is not None:
            raise StdioTransportError("Transport already started")
        
        args = args or []
        
        # Формируем окружение: берём текущее и добавляем пользовательское
        import os
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        logger.debug(
            "Starting MCP server: %s %s (cwd=%s)",
            command, " ".join(args), cwd
        )
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=cwd,
            )
        except FileNotFoundError as e:
            raise StdioTransportError(f"MCP server not found: {command}") from e
        except OSError as e:
            raise StdioTransportError(f"Failed to start MCP server: {e}") from e
        
        # Запускаем фоновые задачи чтения
        self._read_task = asyncio.create_task(
            self._read_stdout_loop(),
            name="mcp_stdout_reader"
        )
        self._stderr_task = asyncio.create_task(
            self._read_stderr_loop(),
            name="mcp_stderr_reader"
        )
        
        logger.info("MCP server started (pid=%d)", self._process.pid)
    
    async def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Отправить JSON-RPC запрос и дождаться ответа.
        
        Args:
            method: Имя вызываемого метода.
            params: Параметры запроса.
            timeout: Таймаут ожидания ответа в секундах.
        
        Returns:
            Результат из ответа (поле result).
        
        Raises:
            ProcessNotStartedError: Если процесс не запущен.
            ProcessExitedError: Если процесс завершился.
            asyncio.TimeoutError: Если истёк таймаут.
            StdioTransportError: При ошибке в ответе.
        """
        if not self.is_running:
            raise ProcessNotStartedError("MCP server process not running")
        
        # Генерируем уникальный ID запроса
        async with self._lock:
            self._request_id += 1
            request_id = self._request_id
        
        # Создаём запрос
        request = MCPRequest(
            id=request_id,
            method=method,
            params=params
        )
        
        # Создаём Future для ожидания ответа
        loop = asyncio.get_running_loop()
        future: asyncio.Future[MCPResponse] = loop.create_future()
        self._pending_requests[request_id] = future
        
        try:
            # Отправляем запрос
            await self._write_message(request.model_dump(by_alias=True, exclude_none=True))
            
            logger.debug("Sent MCP request: method=%s id=%d", method, request_id)
            
            # Ожидаем ответ с таймаутом
            response = await asyncio.wait_for(future, timeout=timeout)
            
            # Проверяем на ошибку
            if response.error:
                raise StdioTransportError(
                    f"MCP error {response.error.code}: {response.error.message}"
                )
            
            return response.result or {}
            
        finally:
            # Удаляем из ожидающих
            self._pending_requests.pop(request_id, None)
    
    async def send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Отправить JSON-RPC нотификацию без ожидания ответа.
        
        Args:
            method: Имя метода нотификации.
            params: Параметры нотификации.
        
        Raises:
            ProcessNotStartedError: Если процесс не запущен.
        """
        if not self.is_running:
            raise ProcessNotStartedError("MCP server process not running")
        
        notification = MCPNotification(method=method, params=params)
        await self._write_message(
            notification.model_dump(by_alias=True, exclude_none=True)
        )
        
        logger.debug("Sent MCP notification: method=%s", method)
    
    async def close(self) -> None:
        """Закрыть соединение и завершить процесс MCP сервера.
        
        Выполняет graceful shutdown: сначала закрывает stdin,
        ждёт завершения процесса, при необходимости принудительно завершает.
        """
        if self._closed:
            return
        
        self._closed = True
        
        logger.debug("Closing MCP transport")
        
        # Отменяем все ожидающие запросы
        for _request_id, future in self._pending_requests.items():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()
        
        # Останавливаем задачи чтения
        if self._read_task:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._read_task
        
        if self._stderr_task:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
        
        # Закрываем процесс
        if self._process:
            # Закрываем stdin для сигнала о завершении
            if self._process.stdin:
                self._process.stdin.close()
                with contextlib.suppress(Exception):
                    await self._process.stdin.wait_closed()
            
            # Ждём завершения процесса (с таймаутом)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
                logger.info(
                    "MCP server exited (code=%s)",
                    self._process.returncode
                )
            except TimeoutError:
                # Принудительное завершение
                logger.warning("MCP server did not exit, terminating")
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except TimeoutError:
                    logger.warning("MCP server did not terminate, killing")
                    self._process.kill()
                    await self._process.wait()
        
        self._process = None
        logger.debug("MCP transport closed")
    
    async def _write_message(self, message: dict[str, Any]) -> None:
        """Записать JSON-RPC сообщение в stdin процесса.
        
        Args:
            message: Сообщение для отправки.
        
        Raises:
            ProcessExitedError: Если процесс завершился.
        """
        if not self._process or not self._process.stdin:
            raise ProcessNotStartedError("No stdin available")
        
        # Сериализуем в JSON + newline
        data = json.dumps(message) + "\n"
        
        try:
            self._process.stdin.write(data.encode("utf-8"))
            await self._process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as e:
            raise ProcessExitedError(
                f"MCP server pipe broken: {e}",
                self._process.returncode
            ) from e
    
    async def _read_stdout_loop(self) -> None:
        """Фоновая задача чтения ответов из stdout.
        
        Читает JSON-RPC сообщения построчно и диспетчеризирует их
        к соответствующим ожидающим Future.
        """
        if not self._process or not self._process.stdout:
            return
        
        try:
            while not self._closed:
                # Читаем строку (JSON-RPC сообщение)
                line = await self._process.stdout.readline()
                
                if not line:
                    # EOF - процесс завершился
                    logger.debug("MCP stdout EOF")
                    break
                
                # Декодируем и парсим JSON
                try:
                    data = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError as e:
                    logger.warning("Invalid JSON from MCP server: %s", e)
                    continue
                
                # Обрабатываем сообщение
                await self._handle_message(data)
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Error reading MCP stdout: %s", e)
            # Отменяем все ожидающие запросы при ошибке
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(
                        ProcessExitedError(f"Read error: {e}")
                    )
    
    async def _read_stderr_loop(self) -> None:
        """Фоновая задача чтения логов из stderr.
        
        Выводит stderr MCP сервера в лог для отладки.
        """
        if not self._process or not self._process.stderr:
            return
        
        try:
            while not self._closed:
                line = await self._process.stderr.readline()
                
                if not line:
                    break
                
                # Логируем stderr как отладочную информацию
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.debug("MCP stderr: %s", text)
                    
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Error reading MCP stderr: %s", e)
    
    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Обработать входящее JSON-RPC сообщение.
        
        Args:
            data: Распарсенное JSON сообщение.
        """
        # Проверяем, есть ли id (это ответ на запрос)
        message_id = data.get("id")
        
        if message_id is not None:
            # Это ответ - ищем ожидающий Future
            future = self._pending_requests.get(message_id)
            
            if future and not future.done():
                # Парсим как MCPResponse
                try:
                    response = MCPResponse.model_validate(data)
                    future.set_result(response)
                except Exception as e:
                    future.set_exception(
                        StdioTransportError(f"Invalid response: {e}")
                    )
            else:
                logger.warning(
                    "Received response for unknown request id=%s",
                    message_id
                )
        else:
            # Это нотификация от сервера
            method = data.get("method", "unknown")
            logger.debug(
                "Received MCP notification: method=%s",
                method
            )
            # Нотификации пока игнорируем, но можно добавить обработку
