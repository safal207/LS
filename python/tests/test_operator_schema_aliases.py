from __future__ import annotations

from shared import OperatorUtterance, ensure_operator_item
from shared.config_loader import _load_app_aliases


def test_operator_utterance_alias_roundtrip() -> None:
    utterance = OperatorUtterance(
        text="Summarize the operator request.",
        source="local_stt",
        interviewer_profile={"pressure_level": 0.2},
    )
    item = ensure_operator_item(utterance, default_source="local_stt")

    assert item["text"] == "Summarize the operator request."
    assert item["source"] == "local_stt"
    assert item["_interviewer_profile"]["pressure_level"] == 0.2
    assert item["_operator_profile"]["pressure_level"] == 0.2
    assert item["operator_profile"]["pressure_level"] == 0.2
    assert utterance.operator_profile == {"pressure_level": 0.2}


def test_operator_utterance_prefers_operator_profile_inputs() -> None:
    item = ensure_operator_item(
        {
            "text": "Summarize the operator request.",
            "source": "local_stt",
            "_operator_profile": {"pressure_level": 0.4},
        },
        default_source="local_stt",
    )

    assert item["_operator_profile"]["pressure_level"] == 0.4
    assert item["_interviewer_profile"]["pressure_level"] == 0.4


def test_operator_runtime_is_valid_app_alias() -> None:
    aliases = _load_app_aliases()

    assert aliases["operator_runtime"] == "ghostgpt"
