"""Серверные модели JSON-RPC/ACP сообщений.

Модуль описывает единый wire-формат, который используется обработчиками
транспортов и протоколом ACP.

Пример использования:
    msg = ACPMessage.request("initialize", {})
    raw = msg.to_json()
"""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

type JsonRpcId = str | int


class JsonRpcError(BaseModel):
    """Структура ошибки JSON-RPC в ответе сервера.

    Пример использования:
        JsonRpcError(code=-32601, message="Method not found")
    """

    # Код и текст ошибки соответствуют JSON-RPC 2.0.
    code: int
    message: str
    # Дополнительные детали ошибки для диагностики.
    data: Any | None = None


class ACPMessage(BaseModel):
    """Универсальная модель JSON-RPC сообщения для серверной части.

    Модель покрывает request/notification/response и используется как единая
    точка сериализации/валидации перед отправкой в транспорт.

    Пример использования:
        response = ACPMessage.response("req_1", {"ok": True})
    """

    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: JsonRpcId | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: JsonRpcError | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ACPMessage:
        """Проверяет целостность формы JSON-RPC payload.

        Пример использования:
            ACPMessage.model_validate({"jsonrpc": "2.0", "id": "1", "result": {}})
        """

        # Проверяем, какие поля реально были переданы во входном payload.
        has_result = "result" in self.model_fields_set
        has_error = "error" in self.model_fields_set and self.error is not None

        if self.method is not None:
            if has_result or has_error:
                msg = "Request/notification must not contain result or error"
                raise ValueError(msg)
            return self

        if not has_result and not has_error:
            msg = "Response must contain result or error"
            raise ValueError(msg)
        if has_result and has_error:
            msg = "Response must not contain both result and error"
            raise ValueError(msg)
        return self

    @property
    def is_notification(self) -> bool:
        """Возвращает `True`, если сообщение является notification.

        Пример использования:
            ACPMessage.notification("session/update", {}).is_notification
        """

        return self.method is not None and self.id is None

    @property
    def is_request(self) -> bool:
        """Возвращает `True`, если сообщение является request.

        Пример использования:
            ACPMessage.request("ping", {}).is_request
        """

        return self.method is not None and self.id is not None

    @classmethod
    def request(
        cls,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        request_id: JsonRpcId | None = None,
    ) -> ACPMessage:
        """Создает request-сообщение.

        Пример использования:
            ACPMessage.request("session/list", {})
        """

        generated_id = request_id if request_id is not None else uuid4().hex[:8]
        return cls(id=generated_id, method=method, params=params or {})

    @classmethod
    def notification(cls, method: str, params: dict[str, Any] | None = None) -> ACPMessage:
        """Создает notification-сообщение без поля `id`.

        Пример использования:
            ACPMessage.notification("session/cancel", {"sessionId": "sess_1"})
        """

        return cls(id=None, method=method, params=params or {})

    @classmethod
    def response(cls, request_id: JsonRpcId | None, result: Any) -> ACPMessage:
        """Создает успешный response.

        Пример использования:
            ACPMessage.response("req_1", {"stopReason": "end_turn"})
        """

        return cls(id=request_id, result=result)

    @classmethod
    def error_response(
        cls,
        request_id: JsonRpcId | None,
        *,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> ACPMessage:
        """Создает error response с кодом, сообщением и опциональными деталями.

        Пример использования:
            ACPMessage.error_response("req_1", code=-32602, message="Invalid params")
        """

        return cls(id=request_id, error=JsonRpcError(code=code, message=message, data=data))

    @classmethod
    def from_json(cls, raw: str) -> ACPMessage:
        """Десериализует JSON-строку в `ACPMessage`.

        Пример использования:
            ACPMessage.from_json(raw_message)
        """

        return cls.model_validate_json(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ACPMessage:
        """Десериализует словарь с поддержкой legacy-поля `type`.

        Пример использования:
            ACPMessage.from_dict({"jsonrpc": "2.0", "id": "1", "result": {}})
        """

        # Поддерживаем legacy-поле `type`, чтобы переход на новый wire-формат был плавным.
        normalized = dict(data)
        legacy_type = normalized.pop("type", None)
        if legacy_type == "request" and "id" not in normalized:
            normalized["id"] = uuid4().hex[:8]
        return cls.model_validate(normalized)

    def to_json(self) -> str:
        """Сериализует сообщение в компактную JSON-строку.

        Пример использования:
            wire = ACPMessage.request("ping", {}).to_json()
        """

        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        """Собирает словарь wire-формата JSON-RPC.

        Пример использования:
            payload = ACPMessage(id="req_1", result=None).to_dict()
        """

        payload: dict[str, Any] = {"jsonrpc": self.jsonrpc}

        if self.method is not None:
            if self.id is not None:
                payload["id"] = self.id
            payload["method"] = self.method
            if "params" in self.model_fields_set:
                payload["params"] = self.params
            return payload

        # Для ответов `id` передается всегда (включая null для parse errors).
        payload["id"] = self.id
        if "result" in self.model_fields_set:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error.model_dump(exclude_none=True)
        return payload


def is_parse_error(exc: Exception) -> bool:
    """Проверяет, является ли исключение ошибкой валидации/парсинга сообщения.

    Пример использования:
        if is_parse_error(exc): ...
    """

    return isinstance(exc, ValidationError)
