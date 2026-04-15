"""Тесты для ACPTransportService request_with_callbacks."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

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
    async def test_handle_client_rpc_logs_tool_lifecycle_trace(self) -> None:
        """Логируется полный trace lifecycle для fs/read_text_file."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        service._logger = MagicMock()  # noqa: SLF001 - test setup
        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True
        service._transport = transport  # noqa: SLF001 - test setup

        await service._handle_notification_or_client_rpc(  # noqa: SLF001 - test target
            method="session/prompt",
            request_id="req-1",
            notification_data={
                "jsonrpc": "2.0",
                "id": "rpc-1",
                "method": "fs/read_text_file",
                "params": {"path": "/tmp/demo.txt"},
            },
            on_update=None,
            on_fs_read=lambda _: "demo-content",
            on_fs_write=None,
            on_terminal_create=None,
            on_terminal_output=None,
            on_terminal_wait=None,
            on_terminal_release=None,
            on_terminal_kill=None,
        )

        transport.send_str.assert_awaited_once()
        debug_events = [call.args[0] for call in service._logger.debug.call_args_list if call.args]
        assert "tool_lifecycle_rpc_received" in debug_events
        assert "tool_lifecycle_callback_start" in debug_events
        assert "tool_lifecycle_callback_done" in debug_events
        assert "tool_lifecycle_response_sending" in debug_events
        assert "tool_lifecycle_response_sent" in debug_events

    @pytest.mark.asyncio
    async def test_request_with_callbacks_logs_notification_failure(self) -> None:
        """Ошибка client-rpc callback логируется, а запрос завершается ответом."""
        service = ACPTransportService(host="127.0.0.1", port=8765)
        service._logger = MagicMock()  # noqa: SLF001 - test setup
        queues = RoutingQueues()
        service._queues = queues  # noqa: SLF001 - test setup

        transport = AsyncMock(spec=WebSocketTransport)
        transport.is_connected.return_value = True

        async def send_str_side_effect(raw_payload: str) -> None:
            payload = json.loads(raw_payload)

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
            on_fs_read=lambda _: (_ for _ in ()).throw(ValueError("boom")),
        )

        assert response["result"]["status"] == "ok"
        warning_events = [
            call.args[0] for call in service._logger.warning.call_args_list if call.args
        ]
        assert "tool_lifecycle_notification_failed" in warning_events
