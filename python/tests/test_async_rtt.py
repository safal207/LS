import asyncio

import pytest

from modules.web4_runtime.async_rtt import AsyncRttSession
from modules.web4_runtime.rtt import RttConfig


def test_async_send_receive() -> None:
    async def run() -> None:
        session = AsyncRttSession[str](config=RttConfig(max_queue=10, enable_priority_queue=True))

        await session.send_async("msg1")
        await session.send_async("msg2", priority=5)

        assert await session.receive_async() == "msg2"
        assert await session.receive_async() == "msg1"

    asyncio.run(run())


def test_async_backpressure() -> None:
    async def run() -> None:
        session = AsyncRttSession[str](
            config=RttConfig(max_queue=2, backpressure_policy="block", block_timeout_s=0.1)
        )

        await session.send_async("a")
        await session.send_async("b")

        with pytest.raises(RuntimeError, match="timeout"):
            await session.send_async("c")

    asyncio.run(run())


def test_async_concurrent_producers() -> None:
    async def run() -> None:
        session = AsyncRttSession[int](config=RttConfig(max_queue=100))

        async def producer(start: int) -> None:
            for i in range(10):
                await session.send_async(start + i)

        await asyncio.gather(
            producer(0),
            producer(100),
            producer(200),
        )

        received = []
        while (msg := await session.receive_async()) is not None:
            received.append(msg)

        assert len(received) == 30

    asyncio.run(run())
