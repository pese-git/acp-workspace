"""Тесты для проверки синхронизации конкурентных вызовов receive().

Проверяет исправление race condition:
- RuntimeError: Concurrent call to receive() is not allowed

Сценарий:
- Сеанс 1 отправляет session/prompt с request_with_callbacks()
- Во время обработки updates Сеанс 2 пытается создаться (вызывает receive())
- AsyncMock WebSocket имитирует то, что он не допускает конкурентные receive()
- asyncio.Lock в ACPTransportService предотвращает эту ошибку
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from acp_client.infrastructure.services.acp_transport_service import ACPTransportService


class TestConcurrentReceiveCalls:
    """Тесты конкурентного доступа к receive() на одном WebSocket."""

    @pytest.mark.asyncio
    async def test_concurrent_receive_calls_are_serialized(self) -> None:
        """Конкурентные вызовы receive() выполняются последовательно благодаря Lock.

        Сценарий: Две задачи одновременно пытаются вызвать receive()
        на одном транспорте. Без Lock это вызовет RuntimeError от aiohttp.
        С Lock обе задачи выполняются успешно (одна ждет другую).
        """
        # Создаем mock WebSocket транспорт
        mock_transport = AsyncMock()
        mock_transport.is_connected = Mock(return_value=True)

        # Счетчик одновременных вызовов receive_text()
        concurrent_calls = 0
        max_concurrent_calls = 0

        async def receive_text_with_concurrent_check():
            """Имитирует receive_text() с проверкой на конкурентные вызовы."""
            nonlocal concurrent_calls, max_concurrent_calls

            concurrent_calls += 1
            max_concurrent_calls = max(max_concurrent_calls, concurrent_calls)

            # Если два вызова одновременны, это эмулирует ошибку aiohttp
            if concurrent_calls > 1:
                raise RuntimeError("Concurrent call to receive() is not allowed")

            try:
                # Имитируем задержку обработки сообщения
                await asyncio.sleep(0.01)
                return '{"jsonrpc": "2.0", "id": 1, "result": {}}'
            finally:
                concurrent_calls -= 1

        mock_transport.receive_text = receive_text_with_concurrent_check

        # Создаем сервис с реальным Lock (а не mock)
        service = ACPTransportService(
            host="127.0.0.1",
            port=8080,
        )
        service._transport = mock_transport
        service._server_capabilities = {}

        # Две конкурентные задачи вызывают receive()
        async def call_receive(task_id: int):
            """Вспомогательная функция для вызова receive()."""
            try:
                result = await service.receive()
                return {"success": True, "task_id": task_id, "result": result}
            except RuntimeError as e:
                return {"success": False, "task_id": task_id, "error": str(e)}

        # Запускаем обе задачи одновременно
        task1 = asyncio.create_task(call_receive(1))
        task2 = asyncio.create_task(call_receive(2))

        # Дожидаемся обеих задач
        results = await asyncio.gather(task1, task2)

        # Проверяем результаты
        assert len(results) == 2
        assert all(result["success"] for result in results), (
            f"Одна из задач не выполнилась: {results}"
        )
        assert max_concurrent_calls == 1, (
            f"Lock не работает - было {max_concurrent_calls} одновременных вызовов"
        )

    @pytest.mark.asyncio
    async def test_multiple_tasks_waiting_on_receive_lock(self) -> None:
        """Проверяет, что несколько задач корректно ждут Lock при вызове receive().

        Сценарий: Три задачи вызывают receive() одновременно.
        С Lock все выполняются успешно в порядке очереди.
        """
        mock_transport = AsyncMock()
        mock_transport.is_connected = Mock(return_value=True)

        call_order = []

        async def receive_text():
            """Имитирует receive_text() с отслеживанием порядка вызовов."""
            import json

            call_order.append(len(call_order))
            await asyncio.sleep(0.001)  # Имитируем задержку сети
            return json.dumps({"jsonrpc": "2.0", "id": len(call_order), "result": {}})

        mock_transport.receive_text = receive_text

        service = ACPTransportService(
            host="127.0.0.1",
            port=8080,
        )
        service._transport = mock_transport
        service._server_capabilities = {}

        # Три задачи вызывают receive() конкурентно
        async def receive_message(task_id: int):
            """Вспомогательная функция для вызова receive()."""
            try:
                result = await service.receive()
                return {"success": True, "task_id": task_id, "result": result}
            except RuntimeError as e:
                return {"success": False, "task_id": task_id, "error": str(e)}

        # Запускаем три задачи одновременно
        tasks = [asyncio.create_task(receive_message(i)) for i in range(3)]

        # Даем время на создание всех задач
        await asyncio.sleep(0.001)

        # Дожидаемся выполнения всех задач
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Проверяем результаты
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results), (
            f"Некоторые результаты - это исключения: {results}"
        )
        assert all(r["success"] for r in results), (
            f"Одна из задач не выполнилась: {results}"
        )
        # Проверяем, что все вызовы прошли в порядке
        assert len(call_order) == 3, f"Expected 3 calls, got {len(call_order)}"

    @pytest.mark.asyncio
    async def test_receive_lock_is_not_none(self) -> None:
        """Проверяет, что Lock инициализирован в __init__()."""
        service = ACPTransportService(
            host="127.0.0.1",
            port=8080,
        )

        assert hasattr(service, "_receive_lock"), "ACPTransportService должен иметь _receive_lock"
        assert isinstance(service._receive_lock, asyncio.Lock), (
            "_receive_lock должен быть asyncio.Lock"
        )
