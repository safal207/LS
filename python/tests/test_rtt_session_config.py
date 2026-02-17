import pytest

from modules.web4_runtime.rtt import BackpressureError, RttConfig, RttSession


@pytest.mark.parametrize("bad_value", [-100, -1, 0])
def test_rtt_config_rejects_non_positive_max_queue(bad_value: int) -> None:
    with pytest.raises(ValueError, match=r"max_queue must be >= 1"):
        RttConfig(max_queue=bad_value)


def test_rtt_session_accepts_valid_config() -> None:
    session = RttSession(config=RttConfig(max_queue=1))
    assert session.config.max_queue == 1


def test_rtt_session_max_queue_boundary_triggers_backpressure_error() -> None:
    session = RttSession[str](config=RttConfig(max_queue=1, backpressure_policy="error"))
    session.send("first")
    with pytest.raises(BackpressureError, match="backpressure"):
        session.send("second")
