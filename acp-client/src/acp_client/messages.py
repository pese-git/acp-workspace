from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator

type JsonRpcId = str | int


class JsonRpcError(BaseModel):
    # Код и текст ошибки соответствуют JSON-RPC 2.0.
    code: int
    message: str
    # Произвольные детали ошибки от сервера.
    data: Any | None = None


class ACPMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: JsonRpcId | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any | None = None
    error: JsonRpcError | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> ACPMessage:
        # Отличаем явно переданные поля от отсутствующих для корректной проверки контракта.
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

    @classmethod
    def request(
        cls,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        request_id: JsonRpcId | None = None,
    ) -> ACPMessage:
        generated_id = request_id if request_id is not None else uuid4().hex[:8]
        return cls(id=generated_id, method=method, params=params or {})

    @classmethod
    def notification(cls, method: str, params: dict[str, Any] | None = None) -> ACPMessage:
        return cls(id=None, method=method, params=params or {})

    @classmethod
    def from_json(cls, raw: str) -> ACPMessage:
        return cls.model_validate_json(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ACPMessage:
        # В клиенте игнорируем legacy `type`, чтобы принимать старые ответы без падения.
        normalized = dict(data)
        normalized.pop("type", None)
        return cls.model_validate(normalized)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": self.jsonrpc}

        if self.method is not None:
            if self.id is not None:
                payload["id"] = self.id
            payload["method"] = self.method
            if "params" in self.model_fields_set:
                payload["params"] = self.params
            return payload

        payload["id"] = self.id
        if "result" in self.model_fields_set:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error.model_dump(exclude_none=True)
        return payload


class SessionUpdatePayload(BaseModel):
    # Дискриминатор типа события в `session/update`.
    sessionUpdate: str
    # Дальнейшие поля зависят от конкретного типа update.
    model_config = ConfigDict(extra="allow")


class SessionUpdateParams(BaseModel):
    # Идентификатор сессии, к которой относится update.
    sessionId: str
    # Полезная нагрузка update-события.
    update: SessionUpdatePayload
    model_config = ConfigDict(extra="forbid")


class SessionUpdateNotification(BaseModel):
    # Notification всегда в формате JSON-RPC 2.0.
    jsonrpc: Literal["2.0"] = "2.0"
    # Для данного помощника принимаем только `session/update`.
    method: Literal["session/update"]
    params: SessionUpdateParams
    model_config = ConfigDict(extra="forbid")


def parse_session_update_notification(payload: dict[str, Any]) -> SessionUpdateNotification | None:
    # Если это не `session/update`, возвращаем None для удобной фильтрации.
    if payload.get("method") != "session/update":
        return None
    return SessionUpdateNotification.model_validate(payload)


def parse_json_params(value: str | None) -> dict[str, Any]:
    # CLI принимает params строкой; здесь приводим к JSON-объекту для ACP запроса.
    if value is None:
        return {}

    try:
        data = json.loads(value)
    except JSONDecodeError as exc:
        msg = f"Invalid JSON in --params: {exc.msg}"
        raise ValueError(msg) from exc

    if not isinstance(data, dict):
        raise ValueError("--params must be a JSON object")

    return data
