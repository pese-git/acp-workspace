from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

type JsonRpcId = str | int


class JsonRpcError(BaseModel):
    # Код и текст ошибки соответствуют JSON-RPC 2.0.
    code: int
    message: str
    # Дополнительные детали ошибки для диагностики.
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
        return self.method is not None and self.id is None

    @property
    def is_request(self) -> bool:
        return self.method is not None and self.id is not None

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
    def response(cls, request_id: JsonRpcId | None, result: Any) -> ACPMessage:
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
        return cls(id=request_id, error=JsonRpcError(code=code, message=message, data=data))

    @classmethod
    def from_json(cls, raw: str) -> ACPMessage:
        return cls.model_validate_json(raw)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ACPMessage:
        # Поддерживаем legacy-поле `type`, чтобы переход на новый wire-формат был плавным.
        normalized = dict(data)
        legacy_type = normalized.pop("type", None)
        if legacy_type == "request" and "id" not in normalized:
            normalized["id"] = uuid4().hex[:8]
        return cls.model_validate(normalized)

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


def is_parse_error(exc: Exception) -> bool:
    return isinstance(exc, ValidationError)
