from python.rust_bridge import RustOptimizer


def test_rust_binding_transport_roundtrip(tmp_path) -> None:
    rust = RustOptimizer(
        db_path=str(tmp_path / "patterns.db"),
        transport_config={
            "heartbeat_ms": 5_000,
            "max_channels": 8,
            "max_queue_depth": 8,
            "max_payload_bytes": 1024,
        }
    )

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
