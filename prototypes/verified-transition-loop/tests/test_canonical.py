from __future__ import annotations

import json
from pathlib import Path

import pytest

from verified_transition_loop.canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    canonical_sha256,
    strict_loads,
    verify_fixture,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "canonical-proof-v0.10.json"


def test_machine_readable_fixture_passes() -> None:
    result = verify_fixture(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert result["canonical_profile"] == CANONICAL_PROFILE
    assert result["summary"] == {
        "total": 16,
        "passed": 16,
        "failed": 0,
        "all_passed": True,
    }


def test_utf16_key_order_matches_jcs_requirement() -> None:
    value = {"\ue000": "bmp-private", "😀": "grinning", "a": "ascii"}
    assert canonical_bytes(value).decode("utf-8") == (
        '{"a":"ascii","😀":"grinning","\ue000":"bmp-private"}'
    )


def test_unicode_is_not_normalized() -> None:
    composed = strict_loads('{"text":"é"}')
    decomposed = strict_loads('{"text":"é"}')
    assert canonical_bytes(composed) != canonical_bytes(decomposed)
    assert canonical_sha256(composed) != canonical_sha256(decomposed)


def test_duplicate_names_fail_closed() -> None:
    with pytest.raises(CanonicalizationError) as excinfo:
        strict_loads('{"a":1,"a":2}')
    assert excinfo.value.code == "DUPLICATE_KEY"


@pytest.mark.parametrize("raw", ['{"x":1.5}', '{"x":1e3}'])
def test_floating_point_forms_are_outside_profile(raw: str) -> None:
    with pytest.raises(CanonicalizationError) as excinfo:
        strict_loads(raw)
    assert excinfo.value.code == "UNSUPPORTED_NUMBER"


def test_unsafe_integer_fails_closed() -> None:
    with pytest.raises(CanonicalizationError) as excinfo:
        canonical_bytes({"x": MAX_SAFE_INTEGER + 1})
    assert excinfo.value.code == "INTEGER_OUT_OF_RANGE"


def test_lone_surrogate_fails_closed() -> None:
    with pytest.raises(CanonicalizationError) as excinfo:
        strict_loads('{"x":"\\ud800"}')
    assert excinfo.value.code == "INVALID_UNICODE_SCALAR"


def test_whitespace_and_escape_spelling_do_not_change_bytes() -> None:
    first = strict_loads('{ "b" : 2, "a" : "caf\\u00e9" }')
    second = strict_loads('{"a":"café","b":2}')
    assert canonical_bytes(first) == canonical_bytes(second)
