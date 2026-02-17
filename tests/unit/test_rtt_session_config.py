import pytest

from python.modules.web4_runtime.rtt import RttConfig, RttSession


def test_rtt_session_rejects_non_positive_max_queue() -> None:
    with pytest.raises(ValueError, match="max_queue"):
        RttSession(config=RttConfig(max_queue=0))
