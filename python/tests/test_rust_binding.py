import pytest

from python.rust_bridge import RustOptimizer


@pytest.fixture
def rust_optimizer(tmp_path):
    rust = RustOptimizer(
        db_path=str(tmp_path / "patterns.db"),
        transport_config={
            "heartbeat_ms": 5_000,
            "max_channels": 8,
            "max_queue_depth": 8,
            "max_payload_bytes": 1024,
        },
    )
    yield rust
    rust.close()


def test_rust_binding_transport_roundtrip(rust_optimizer) -> None:
    rust = rust_optimizer
    assert rust.available, "ghostgpt_core is not available"

    session_id = rust.create_session("peer-ci")
    assert session_id is not None

    channel_id = rust.open_channel("state", session_id)
    assert channel_id is not None

    payload = b"ping"
    assert rust.send(channel_id, payload)
    assert rust.queue_len(channel_id) == 1

    received = rust.receive(channel_id)
    assert bytes(received) == payload
    assert rust.queue_len(channel_id) == 0


def test_rust_binding_max_payload_exceeded(rust_optimizer) -> None:
    rust = rust_optimizer
    assert rust.available, "ghostgpt_core is not available"

    session_id = rust.create_session("peer-ci")
    assert session_id is not None

    channel_id = rust.open_channel("state", session_id)
    assert channel_id is not None

    large_payload = b"x" * 2048
    assert rust.send(channel_id, large_payload) is False
