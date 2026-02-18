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
