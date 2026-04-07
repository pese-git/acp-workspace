"""Помощники для аутентификации в ACP-клиенте."""

from __future__ import annotations

from ..messages import InitializeResult


def pick_auth_method_id(
    init_result: InitializeResult,
    preferred_auth_method_id: str | None = None,
) -> str | None:
    """Выбирает auth method id из согласованного списка `authMethods`.

    Функция реализует логику выбора метода аутентификации:
    1. Если предпочитаемый метод указан и доступен — возвращает его id
    2. Если предпочитаемый метод не найден — выбрасывает ошибку
    3. Если нет методов — возвращает None
    4. Иначе — возвращает первый доступный метод

    Аргументы:
        init_result: результат initialize с доступными методами
        preferred_auth_method_id: предпочитаемый id метода аутентификации (опционально)

    Возвращает:
        id выбранного метода или None, если методы недоступны

    Исключения:
        RuntimeError: если предпочитаемый метод не найден в списке доступных

    Пример использования:
        method_id = pick_auth_method_id(init_result, preferred="local")
    """

    auth_methods = init_result.authMethods
    # Если список методов пуст, аутентификация не требуется
    if not auth_methods:
        return None

    # Если указан предпочитаемый метод, проверяем его наличие
    if preferred_auth_method_id is not None:
        for auth_method in auth_methods:
            if auth_method.id == preferred_auth_method_id:
                return auth_method.id
        # Предпочитаемый метод не найден — ошибка
        msg = f"Preferred auth method not advertised: {preferred_auth_method_id}"
        raise RuntimeError(msg)

    # Используем первый доступный метод по умолчанию
    return auth_methods[0].id
