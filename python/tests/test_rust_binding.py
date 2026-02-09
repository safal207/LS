import pytest

try:
    from ghostgpt_core import Web4RttBinding
except ImportError:
    pytest.skip("Rust binding not built", allow_module_level=True)

def test_rust_rtt_lifecycle() -> None:
    rtt = Web4RttBinding(10)
    assert rtt.pending() == 0
    rtt.send("hello")
    assert rtt.pending() == 1
    received = rtt.receive()
    assert received == "hello"
    assert rtt.pending() == 0

def test_rust_rtt_backpressure() -> None:
    rtt = Web4RttBinding(1)
    rtt.send("one")
    with pytest.raises(RuntimeError, match="RTT binding backpressure"):
        rtt.send("two")

def test_rust_rtt_disconnect() -> None:
    rtt = Web4RttBinding(5)
    rtt.disconnect()
    with pytest.raises(RuntimeError, match="RTT binding disconnected"):
        rtt.send("fail")
    rtt.connect()
    rtt.send("ok")
