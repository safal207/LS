import asyncio

import pytest

from modules.web4_runtime.async_rtt import AsyncRttSession
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
