"""Обработчик запросов файловой системы от сервера.

Модуль содержит функцию для обработки server-originated fs/* RPC-запросов
и построения соответствующих ответов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..messages import ACPMessage, JsonRpcError

if TYPE_CHECKING:
    from . import FsReadHandler, FsWriteHandler


def handle_server_fs_request(
    *,
    payload: dict[str, Any],
    on_fs_read: FsReadHandler | None,
    on_fs_write: FsWriteHandler | None,
) -> ACPMessage | None:
    """Обрабатывает server-originated `fs/*` запрос и строит response.

    Функция поддерживает два типа запросов:
    - fs/read_text_file: чтение содержимого текстового файла
    - fs/write_text_file: запись содержимого в текстовый файл

    Если соответствующий handler не передан, возвращается ошибка -32601
    (Method not found). Если параметры невалидны, возвращается ошибка -32602
    (Invalid params).

    Args:
        payload: Словарь с полями method, id и params из JSON-RPC запроса
        on_fs_read: Callback для обработки fs/read_text_file запросов
        on_fs_write: Callback для обработки fs/write_text_file запросов

    Returns:
        ACPMessage с ответом, если это был fs/* запрос, иначе None
    """

    # Извлекаем поля из payload JSON-RPC запроса
    method = payload.get("method")
    request_id = payload.get("id")
    params = payload.get("params")

    # Обработка запроса чтения файла
    if method == "fs/read_text_file":
        # Проверяем, что client поддерживает операцию чтения
        if on_fs_read is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support fs/read_text_file",
                ),
            )
        # Валидируем параметры запроса
        path = params.get("path") if isinstance(params, dict) else None
        if not isinstance(path, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: path must be a string",
                ),
            )
        # Выполняем callback и возвращаем результат
        return ACPMessage.response(request_id, {"content": on_fs_read(path)})

    # Обработка запроса записи в файл
    if method == "fs/write_text_file":
        # Проверяем, что client поддерживает операцию записи
        if on_fs_write is None:
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32601,
                    message="Client does not support fs/write_text_file",
                ),
            )
        # Валидируем параметры запроса
        path = params.get("path") if isinstance(params, dict) else None
        content = params.get("content") if isinstance(params, dict) else None
        if not isinstance(path, str) or not isinstance(content, str):
            return ACPMessage(
                id=request_id,
                error=JsonRpcError(
                    code=-32602,
                    message="Invalid params: path and content must be strings",
                ),
            )
        # Выполняем callback и возвращаем пустой результат
        _ = on_fs_write(path, content)
        return ACPMessage.response(request_id, {})

    # Не fs/* запрос — возвращаем None для обработки другими handlers
    return None
