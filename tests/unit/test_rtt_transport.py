import pytest

from python.rust_bridge import RustOptimizer


def test_rtt_session_channel_lifecycle():
    optimizer = RustOptimizer()
    if not optimizer.transport_available():
        pytest.skip("Rust transport not available")

    session_id = optimizer.create_session("test-peer")
    assert session_id is not None

    channel_id = optimizer.open_channel("control", session_id=session_id)
    assert channel_id is not None

    assert optimizer.send(channel_id, b"ping")
    assert optimizer.receive(channel_id) == b"ping"

    stats = optimizer.channel_stats(channel_id)
    assert stats is not None

    optimizer.close_channel(channel_id)
    optimizer.close_session(session_id)


def test_rtt_queue_limit_enforced():
    optimizer = RustOptimizer(transport_config={"max_queue_depth": 2})
    if not optimizer.transport_available():
        pytest.skip("Rust transport not available")

    session_id = optimizer.create_session("queue-peer")
    assert session_id is not None

    channel_id = optimizer.open_channel("control", session_id=session_id)
    assert channel_id is not None

    assert optimizer.send(channel_id, b"one")
    assert optimizer.send(channel_id, b"two")
    assert not optimizer.send(channel_id, b"three")

    optimizer.close_channel(channel_id)
    optimizer.close_session(session_id)
