from __future__ import annotations

import json
from pathlib import Path

import pytest

from ls_agent_trust.cross_thread import EventType
from ls_agent_trust.validator import validate_event_document


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize(
    "filename,expected_type",
    [
        ("verified-result.json", EventType.RESULT),
        ("unverified-state.json", EventType.STATE_UPDATE),
        ("action-request.json", EventType.ACTION_REQUEST),
        ("stale-event.json", EventType.STATE_UPDATE),
    ],
)
def test_examples_validate_against_protocol_schema(
    filename: str, expected_type: EventType
) -> None:
    document = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))

    event = validate_event_document(document)

    assert event.event_type == expected_type
    assert event.schema_version == "cross-thread-event/v0.1"


def test_schema_rejects_missing_source_identity() -> None:
    document = json.loads(
        (EXAMPLES / "verified-result.json").read_text(encoding="utf-8")
    )
    del document["source"]["agent_id"]

    with pytest.raises(ValueError, match="agent_id"):
        validate_event_document(document)


def test_schema_rejects_execution_authority_with_wrong_type() -> None:
    document = json.loads(
        (EXAMPLES / "action-request.json").read_text(encoding="utf-8")
    )
    document["authority"]["may_authorize_execution"] = "yes"

    with pytest.raises(ValueError, match="may_authorize_execution"):
        validate_event_document(document)
