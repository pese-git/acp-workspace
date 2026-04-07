"""Обработчик для работы с запросами разрешений в ACP протоколе."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_permission_result(
    *,
    payload: dict[str, Any],
    on_permission: Callable[[dict[str, Any]], str | None] | None,
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
    selected_option_id = on_permission(payload) if on_permission is not None else None

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
