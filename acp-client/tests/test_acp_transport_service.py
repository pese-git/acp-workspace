"""Тесты для ACPTransportService request_with_callbacks."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from acp_client.infrastructure.services.acp_transport_service import ACPTransportService
from acp_client.infrastructure.services.routing_queues import RoutingQueues
from acp_client.infrastructure.transport import WebSocketTransport


class TestACPTransportServiceRequestWithCallbacks:
    """Тесты обработки server->client RPC внутри request_with_callbacks."""

    @pytest.mark.asyncio
    async def test_permission_request_with_id_is_handled(self) -> None:
        """Клиент отвечает на session/request_permission c id и завершает запрос."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        queues = RoutingQueues()
        service._queues = queues  # noqa: SLF001 - test setup

        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True
        sent_messages: list[dict[str, object]] = []

        async def send_str_side_effect(raw_payload: str) -> None:
            payload = json.loads(raw_payload)
            sent_messages.append(payload)

            if payload.get("method") != "session/prompt":
                return

            if not isinstance(payload.get("id"), str | int):
                return
            request_id: str | int = payload["id"]

            async def produce_server_messages() -> None:
                await queues.permission_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": "perm-1",
                        "method": "session/request_permission",
                        "params": {
                            "sessionId": "sess-1",
                            "options": [{"optionId": "allow_once", "kind": "allow_once"}],
                        },
                    }
                )
                response_queue = await queues.get_or_create_response_queue(request_id)
                await response_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"status": "ok"},
                    }
                )

            asyncio.create_task(produce_server_messages())

        transport.send_str = AsyncMock(side_effect=send_str_side_effect)
        service._transport = transport  # noqa: SLF001 - test setup

        response = await service.request_with_callbacks(
            method="session/prompt",
            params={"sessionId": "sess-1", "prompt": [{"type": "text", "text": "hi"}]},
            on_permission=lambda _: "allow_once",
        )

        assert response["result"]["status"] == "ok"

        permission_reply = next(
            message
            for message in sent_messages
            if message.get("id") == "perm-1" and "result" in message
        )
        assert permission_reply["result"] == {
            "outcome": {"outcome": "selected", "optionId": "allow_once"}
        }

    @pytest.mark.asyncio
    async def test_fs_read_request_with_id_is_handled(self) -> None:
        """Клиент отвечает на fs/read_text_file и завершает исходный запрос."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        queues = RoutingQueues()
        service._queues = queues  # noqa: SLF001 - test setup

        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True
        sent_messages: list[dict[str, object]] = []

        async def send_str_side_effect(raw_payload: str) -> None:
            payload = json.loads(raw_payload)
            sent_messages.append(payload)

            if payload.get("method") != "session/prompt":
                return

            if not isinstance(payload.get("id"), str | int):
                return
            request_id: str | int = payload["id"]

            async def produce_server_messages() -> None:
                await queues.notification_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": "rpc-1",
                        "method": "fs/read_text_file",
                        "params": {"sessionId": "sess-1", "path": "/tmp/demo.txt"},
                    }
                )
                response_queue = await queues.get_or_create_response_queue(request_id)
                await response_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"status": "ok"},
                    }
                )

            asyncio.create_task(produce_server_messages())

        transport.send_str = AsyncMock(side_effect=send_str_side_effect)
        service._transport = transport  # noqa: SLF001 - test setup

        response = await service.request_with_callbacks(
            method="session/prompt",
            params={"sessionId": "sess-1", "prompt": [{"type": "text", "text": "read"}]},
            on_fs_read=lambda path: f"content from {path}",
        )

        assert response["result"]["status"] == "ok"

        fs_reply = next(
            message
            for message in sent_messages
            if message.get("id") == "rpc-1" and "result" in message
        )
        assert fs_reply["result"] == {"content": "content from /tmp/demo.txt"}

    @pytest.mark.asyncio
    async def test_unknown_server_rpc_with_id_gets_fallback_response(self) -> None:
        """На неизвестный server->client RPC отправляется пустой response."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        queues = RoutingQueues()
        service._queues = queues  # noqa: SLF001 - test setup

        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True
        sent_messages: list[dict[str, object]] = []

        async def send_str_side_effect(raw_payload: str) -> None:
            payload = json.loads(raw_payload)
            sent_messages.append(payload)

            if payload.get("method") != "session/prompt":
                return

            if not isinstance(payload.get("id"), str | int):
                return
            request_id: str | int = payload["id"]

            async def produce_server_messages() -> None:
                await queues.notification_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": "rpc-unknown-1",
                        "method": "custom/unknown_rpc",
                        "params": {"sessionId": "sess-1"},
                    }
                )
                response_queue = await queues.get_or_create_response_queue(request_id)
                await response_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"status": "ok"},
                    }
                )

            asyncio.create_task(produce_server_messages())

        transport.send_str = AsyncMock(side_effect=send_str_side_effect)
        service._transport = transport  # noqa: SLF001 - test setup

        response = await service.request_with_callbacks(
            method="session/prompt",
            params={"sessionId": "sess-1", "prompt": [{"type": "text", "text": "hi"}]},
        )

        assert response["result"]["status"] == "ok"

        fallback_reply = next(
            message
            for message in sent_messages
            if message.get("id") == "rpc-unknown-1" and "result" in message
        )
        assert fallback_reply["result"] == {}

    @pytest.mark.asyncio
    async def test_turn_complete_finishes_prompt_without_response_message(self) -> None:
        """session/turn_complete завершает session/prompt без RPC response."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        queues = RoutingQueues()
        service._queues = queues  # noqa: SLF001 - test setup

        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True

        async def send_str_side_effect(raw_payload: str) -> None:
            payload = json.loads(raw_payload)
            if payload.get("method") != "session/prompt":
                return

            async def produce_server_messages() -> None:
                await queues.notification_queue.put(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/turn_complete",
                        "params": {
                            "sessionId": "sess-1",
                            "stopReason": "end_turn",
                        },
                    }
                )

            asyncio.create_task(produce_server_messages())

        transport.send_str = AsyncMock(side_effect=send_str_side_effect)
        service._transport = transport  # noqa: SLF001 - test setup

        response = await service.request_with_callbacks(
            method="session/prompt",
            params={"sessionId": "sess-1", "prompt": [{"type": "text", "text": "hello"}]},
        )

        assert isinstance(response.get("result"), dict)
        assert response["result"].get("stopReason") == "end_turn"
