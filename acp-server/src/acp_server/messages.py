from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ACPMessage:
    id: str
    type: str
    jsonrpc: str = "2.0"
    method: str | None = None
    params: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @classmethod
    def request(cls, method: str, params: dict[str, Any] | None = None) -> ACPMessage:
        return cls(id=uuid4().hex[:8], type="request", method=method, params=params or {})

    @classmethod
    def from_json(cls, raw: str) -> ACPMessage:
        data = json.loads(raw)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ACPMessage:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data["id"],
            type=data["type"],
            method=data.get("method"),
            params=data.get("params"),
            result=data.get("result"),
            error=data.get("error"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id, "type": self.type}
        if self.method is not None:
            payload["method"] = self.method
        if self.params is not None:
            payload["params"] = self.params
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload
