import asyncio

import pytest

from modules.web4_runtime.async_rtt import AsyncRttSession
from modules.web4_runtime.flow import GlobalFlowController
from modules.web4_runtime.rtt import BackpressureError, DisconnectedError, RttConfig


def test_async_rtt_send_receive_roundtrip() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=2))
        await session.send_async("ping")
        assert await session.receive_async() == "ping"

    asyncio.run(scenario())


def test_async_rtt_wait_message_timeout() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=1))
        assert await session.wait_message(timeout_s=0.01) is None

    asyncio.run(scenario())


def test_async_rtt_wait_message_receives_when_published() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=2))

        async def producer() -> None:
            await asyncio.sleep(0.01)
            await session.send_async("msg")

        task = asyncio.create_task(producer())
        assert await session.wait_message(timeout_s=0.2) == "msg"
        await task

    asyncio.run(scenario())


def test_async_rtt_disconnect_wakes_blocked_sender() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=1, backpressure_policy="block", block_timeout_s=1.0))
        await session.send_async("first")

        task = asyncio.create_task(session.send_async("second"))
        await asyncio.sleep(0)
        await session.disconnect()

        with pytest.raises(DisconnectedError, match="disconnected"):
            await task

    asyncio.run(scenario())


def test_async_rtt_backpressure_error_policy() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=1, backpressure_policy="error"))
        await session.send_async("first")
        with pytest.raises(BackpressureError, match="backpressure"):
            await session.send_async("second")

    asyncio.run(scenario())


def test_async_rtt_dropnewest_policy() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=1, backpressure_policy="dropnewest"))
        await session.send_async("first")
        await session.send_async("second")
        assert await session.receive_async() == "first"
        assert await session.receive_async() is None

    asyncio.run(scenario())


def test_async_rtt_dropoldest_policy() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=1, backpressure_policy="dropoldest"))
        await session.send_async("first")
        await session.send_async("second")
        assert await session.receive_async() == "second"

    asyncio.run(scenario())


def test_async_rtt_priority_queue_ordering() -> None:
    async def scenario() -> None:
        session = AsyncRttSession[str](
            config=RttConfig(max_queue=3, backpressure_policy="dropnewest", enable_priority_queue=True)
        )
        await session.send_async("low", priority=1)
        await session.send_async("high", priority=9)
        assert await session.receive_async() == "high"
        assert await session.receive_async() == "low"

    asyncio.run(scenario())


def test_async_rtt_with_global_flow_controller() -> None:
    async def scenario() -> None:
        flow = GlobalFlowController(total_limit=1, per_session_limit=1)
        session = AsyncRttSession[str](
            config=RttConfig(max_queue=10, backpressure_policy="error"),
            flow_controller=flow,
        )
        await session.send_async("first")
        with pytest.raises(BackpressureError, match="backpressure"):
            await session.send_async("second")
        assert await session.receive_async() == "first"
        await session.send_async("third")
        assert await session.receive_async() == "third"

    asyncio.run(scenario())


def test_async_dropoldest_swap_keeps_global_pending_consistent() -> None:
    async def scenario() -> None:
        flow = GlobalFlowController(total_limit=10, per_session_limit=10)
        session = AsyncRttSession[str](
            config=RttConfig(max_queue=1, backpressure_policy="dropoldest"),
            flow_controller=flow,
        )

        await session.send_async("first")
        assert flow.total_pending == 1

        await session.send_async("second")
        assert session.pending == 1
        assert flow.total_pending == 1
        assert await session.receive_async() == "second"
        assert flow.total_pending == 0

    asyncio.run(scenario())


def test_async_block_sender_wakes_on_global_dequeue() -> None:
    async def scenario() -> None:
        flow = GlobalFlowController(total_limit=1, per_session_limit=1)
        owner = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="error"),
            flow_controller=flow,
        )
        blocked = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="block", block_timeout_s=1.0),
            flow_controller=flow,
        )

        await owner.send_async("first")
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        task = asyncio.create_task(blocked.send_async("second"))
        await asyncio.sleep(0.05)
        assert task.done() is False

        assert await owner.receive_async() == "first"
        await task
        elapsed = loop.time() - started_at
        assert elapsed < 0.45
        assert await blocked.receive_async() == "second"
        assert flow.total_pending == 0

    asyncio.run(scenario())


def test_async_notify_tasks_are_executed_and_do_not_leak() -> None:
    async def scenario() -> None:
        flow = GlobalFlowController(total_limit=2, per_session_limit=2)
        session = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="error"),
            flow_controller=flow,
        )

        await session.send_async("seed")
        assert await session.receive_async() == "seed"

        session._notify_global_space_available()
        for _ in range(10):
            if len(session._notify_tasks) == 0:
                break
            await asyncio.sleep(0)
        assert len(session._notify_tasks) == 0

    asyncio.run(scenario())
