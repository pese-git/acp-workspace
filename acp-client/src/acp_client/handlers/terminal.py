"""Обработчик запросов терминала от сервера.

Модуль содержит функцию для обработки server-originated terminal/* RPC-запросов
и построения соответствующих ответов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..messages import ACPMessage, JsonRpcError

if TYPE_CHECKING:
    from . import (
        TerminalCreateHandler,
        TerminalKillHandler,
        TerminalOutputHandler,
        TerminalReleaseHandler,
        TerminalWaitHandler,
    )


def handle_server_terminal_request(
    *,
    payload: dict[str, Any],
    on_terminal_create: TerminalCreateHandler | None,
    on_terminal_output: TerminalOutputHandler | None,
    on_terminal_wait_for_exit: TerminalWaitHandler | None,
    on_terminal_release: TerminalReleaseHandler | None,
    on_terminal_kill: TerminalKillHandler | None,
) -> ACPMessage | None:
    """Обрабатывает server-originated `terminal/*` запрос и строит response.

    Функция поддерживает пять типов запросов:
    - terminal/create: создание нового терминального сеанса
    - terminal/output: получение вывода из терминала
    - terminal/wait_for_exit: ожидание выхода из процесса
    - terminal/release: освобождение ресурсов терминала
    - terminal/kill: завершение процесса в терминале

    Если соответствующий handler не передан, возвращается ошибка -32601
    (Method not found). Если параметры невалидны, возвращается ошибка -32602
    (Invalid params).

    Args:
        payload: Словарь с полями method, id и params из JSON-RPC запроса
        on_terminal_create: Callback для обработки terminal/create запросов
        on_terminal_output: Callback для обработки terminal/output запросов
        on_terminal_wait_for_exit: Callback для обработки terminal/wait_for_exit запросов
        on_terminal_release: Callback для обработки terminal/release запросов
        on_terminal_kill: Callback для обработки terminal/kill запросов

    Returns:
        ACPMessage с ответом, если это был terminal/* запрос, иначе None
    """

    # Извлекаем поля из payload JSON-RPC запроса
    method = payload.get("method")
    request_id = payload.get("id")
    raw_params = payload.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}

    # Обработка запроса создания терминала
    if method == "terminal/create":
        # Проверяем, что client поддерживает создание терминала
        if on_terminal_create is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support terminal/create",
                ),
            )
        # Валидируем параметры запроса
        command = params.get("command")
        if not isinstance(command, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: command must be a string",
                ),
            )
        # Выполняем callback и возвращаем ID созданного терминала
        return ACPMessage.response(request_id, {"terminalId": on_terminal_create(command)})

    # Обработка запроса получения вывода терминала
    if method == "terminal/output":
        # Проверяем, что client поддерживает получение вывода
        if on_terminal_output is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support terminal/output",
                ),
            )
        # Валидируем параметры запроса
        terminal_id = params.get("terminalId")
        if not isinstance(terminal_id, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: terminalId must be a string",
                ),
            )
        # Выполняем callback и возвращаем вывод терминала
        return ACPMessage.response(
            request_id,
            {
                "output": on_terminal_output(terminal_id),
                "truncated": False,
                "exitStatus": None,
            },
        )

    # Обработка запроса ожидания выхода из процесса
    if method == "terminal/wait_for_exit":
        # Проверяем, что client поддерживает ожидание выхода
        if on_terminal_wait_for_exit is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support terminal/wait_for_exit",
                ),
            )
        # Валидируем параметры запроса
        terminal_id = params.get("terminalId")
        if not isinstance(terminal_id, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: terminalId must be a string",
                ),
            )
        # Выполняем callback и парсим результат
        wait_result = on_terminal_wait_for_exit(terminal_id)
        exit_code: int | None
        signal: str | None
        if isinstance(wait_result, tuple):
            tuple_exit_code, tuple_signal = wait_result
            exit_code = tuple_exit_code if isinstance(tuple_exit_code, int) else None
            signal = tuple_signal if isinstance(tuple_signal, str) else None
        else:
            exit_code = wait_result if isinstance(wait_result, int) else None
            signal = None
        # Возвращаем код выхода и сигнал
        return ACPMessage.response(
            request_id,
            {
                "exitCode": exit_code,
                "signal": signal,
            },
        )

    # Обработка запроса освобождения ресурсов терминала
    if method == "terminal/release":
        # Проверяем, что client поддерживает освобождение терминала
        if on_terminal_release is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support terminal/release",
                ),
            )
        # Валидируем параметры запроса
        terminal_id = params.get("terminalId")
        if not isinstance(terminal_id, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: terminalId must be a string",
                ),
            )
        # Выполняем callback и возвращаем пустой результат
        on_terminal_release(terminal_id)
        return ACPMessage.response(request_id, {})

    # Обработка запроса завершения процесса в терминале
    if method == "terminal/kill":
        # Проверяем, что client поддерживает завершение процесса
        if on_terminal_kill is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support terminal/kill",
                ),
            )
        # Валидируем параметры запроса
        terminal_id = params.get("terminalId")
        if not isinstance(terminal_id, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: terminalId must be a string",
                ),
            )
        # Выполняем callback и возвращаем пустой результат
        _ = on_terminal_kill(terminal_id)
        return ACPMessage.response(request_id, {})

    # Не terminal/* запрос — возвращаем None для обработки другими handlers
    return None
