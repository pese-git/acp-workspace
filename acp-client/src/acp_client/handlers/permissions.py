"""Обработчик для работы с запросами разрешений в ACP протоколе."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


async def build_permission_result(
    *,
    payload: dict[str, Any],
    on_permission: Callable[[dict[str, Any]], Any] | None,
) -> dict[str, Any]:
    """Формирует результат `session/request_permission` для ответа агенту.

    Если callback не передан или вернул `None`, возвращается `cancelled`.
    Если callback вернул опцию, возвращается `selected` с этой опцией.

    Args:
        payload: Исходный payload запроса разрешения от сервера.
        on_permission: Опциональный callback для обработки запроса разрешения.
                      Функция принимает payload и возвращает ID выбранной опции
                      или None для отмены.

    Returns:
        Словарь с результатом: либо `{"outcome": {"outcome": "cancelled"}}`,
        либо `{"outcome": {"outcome": "selected", "optionId": <selected_id>}}`.

    Пример использования:
        result = build_permission_result(
            payload=data,
            on_permission=my_handler
        )
    """

    # Вызываем callback если он передан, иначе None
    selected_option_id: str | None = None
    if on_permission is not None:
        callback_result = on_permission(payload)
        if inspect.isawaitable(callback_result):
            awaited_result = await callback_result
            if isinstance(awaited_result, str) and awaited_result:
                selected_option_id = awaited_result
        elif isinstance(callback_result, str) and callback_result:
            selected_option_id = callback_result

    # Если опция не выбрана, возвращаем отмену
    if selected_option_id is None:
        return {
            "outcome": {
                "outcome": "cancelled",
            }
        }

    # Иначе возвращаем выбранную опцию
    return {
        "outcome": {
            "outcome": "selected",
            "optionId": selected_option_id,
        }
    }
