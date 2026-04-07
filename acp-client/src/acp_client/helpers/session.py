"""Вспомогательные функции для работы с сессиями.

Содержит утилиты для парсинга и фильтрации update-событий
при работе с session/load и другими session-методами.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from acp_client.messages import (
    PlanUpdate,
    SessionUpdateNotification,
    StructuredSessionUpdate,
    ToolCallUpdate,
    parse_plan_update,
    parse_structured_session_update,
    parse_tool_call_update,
)

# Тип параметра для generic функции парсера
ParserType = TypeVar("ParserType")


def filter_parsed_updates(  # noqa: UP047
    raw_updates: list[dict[str, Any]],
    parser: Callable[[SessionUpdateNotification], ParserType | None],
) -> list[ParserType]:
    """Фильтрует raw updates, парсит через notification и применяет парсер.

    Функция упрощает повторяющийся паттерн фильтрации update-событий:
    - Валидирует, что элемент - это dict
    - Парсит в SessionUpdateNotification
    - Применяет специализированный парсер
    - Пропускает None результаты

    Args:
        raw_updates: Список сырых update-событий из WS
        parser: Функция для преобразования SessionUpdateNotification в конкретный тип

    Returns:
        Список успешно распарсенных объектов нужного типа

    Пример использования:
        tool_updates = filter_parsed_updates(
            raw_updates,
            parse_tool_call_update
        )
    """

    from acp_client.messages import parse_session_update_notification

    result: list[ParserType] = []
    for raw_update in raw_updates:
        if not isinstance(raw_update, dict):
            continue
        parsed = parse_session_update_notification(raw_update)
        if parsed is None:
            continue
        parsed_item = parser(parsed)
        if parsed_item is None:
            continue
        result.append(parsed_item)
    return result


def extract_tool_call_updates(
    raw_updates: list[dict[str, Any]],
) -> list[ToolCallUpdate]:
    """Выделяет только tool-call update-события из списка raw updates.

    Удобна для UI/логики, которым важны только статусы инструментов.

    Args:
        raw_updates: Список сырых update-событий из WS

    Returns:
        Список распарсенных ToolCallUpdate объектов

    Пример использования:
        tool_updates = extract_tool_call_updates(raw_updates)
    """

    return filter_parsed_updates(raw_updates, parse_tool_call_update)


def extract_plan_updates(
    raw_updates: list[dict[str, Any]],
) -> list[PlanUpdate]:
    """Выделяет только plan update-события из списка raw updates.

    Полезна для клиентов, которые показывают пользователю только текущий
    план выполнения без остальных session/update событий.

    Args:
        raw_updates: Список сырых update-событий из WS

    Returns:
        Список распарсенных PlanUpdate объектов

    Пример использования:
        plans = extract_plan_updates(raw_updates)
    """

    return filter_parsed_updates(raw_updates, parse_plan_update)


def extract_structured_updates(
    raw_updates: list[dict[str, Any]],
) -> list[StructuredSessionUpdate]:
    """Выделяет только известные typed update payload из списка raw updates.

    Применяет парсер StructuredSessionUpdate для извлечения стандартных
    типов обновлений, пропуская неизвестные события.

    Args:
        raw_updates: Список сырых update-событий из WS

    Returns:
        Список распарсенных StructuredSessionUpdate объектов

    Пример использования:
        structured = extract_structured_updates(raw_updates)
    """

    return filter_parsed_updates(raw_updates, parse_structured_session_update)
