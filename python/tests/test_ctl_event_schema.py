from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "ctl_event_v1.schema.json"
EXAMPLES_DIR = ROOT / "schemas" / "examples" / "ctl_events" / "v1"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = _load_json(SCHEMA_PATH)
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "filename",
    [
        "proposal_created.json",
        "proposal_purchased.json",
        "outcome_settled.json",
        "price_changed.json",
    ],
)
def test_ctl_event_examples_are_valid(filename: str, validator: Draft202012Validator) -> None:
    payload = _load_json(EXAMPLES_DIR / filename)
    validator.validate(payload)


def test_ctl_event_rejects_missing_required_field(validator: Draft202012Validator) -> None:
    payload = _load_json(EXAMPLES_DIR / "proposal_created.json")
    payload.pop("trace_id")

    with pytest.raises(ValidationError):
        validator.validate(payload)


def test_ctl_event_rejects_wrong_event_data_shape(validator: Draft202012Validator) -> None:
    payload = _load_json(EXAMPLES_DIR / "proposal_purchased.json")
    payload["data"].pop("tx_ref")

    with pytest.raises(ValidationError):
        validator.validate(payload)
