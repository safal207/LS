import pytest

from modules.web4_runtime.rtt import RttConfig, RttSession


def test_rtt_config_rejects_non_positive_max_queue() -> None:
    with pytest.raises(ValueError, match="max_queue"):
        RttConfig(max_queue=0)


def test_rtt_session_accepts_valid_config() -> None:
    session = RttSession(config=RttConfig(max_queue=1))
    assert session.config.max_queue == 1
