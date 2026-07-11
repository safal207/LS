import pytest

from tools.deepseek_causal_review_adapter import (
    DeepSeekAdapterError,
    adapt_deepseek_lane,
)


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 875,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def finding(source_id="finding-1"):
    return {
        "source_id": source_id,
        "severity": "medium",
        "title": "Candidate",
        "location": {"path": "tools/example.py", "line": 10},
        "causal_chain": {
            "change": "A boundary changed.",
            "root_cause": "An invariant is absent.",
            "failure_mechanism": "Input bypasses validation.",
            "observable_effect": "Malformed data is accepted.",
            "impact": "Metrics can be corrupted.",
        },
        "evidence": [
            {
                "type": "patch",
                "reference": "tools/example.py:10",
                "excerpt": "Validation is absent.",
            }
        ],
        "confidence": 0.7,
        "reproduction": "Submit malformed input.",
        "recommendation": "Restore the invariant.",
    }


def lane():
    return {
        "schema_version": "ls.deepseek-causal-lane.v0.1",
        "target": target(),
        "model": {
            "requested": "deepseek/deepseek-r1",
            "provider": "deepseek/deepseek-r1",
        },
        "execution": {
            "status": "COMPLETED",
            "provenance": "MATCHED",
            "details": "Exact provider identity was recorded.",
        },
        "findings": [finding()],
        "dedupe_overrides": {},
        "tests_to_run": [],
        "human_decision_points": [],
    }


def test_invalid_severity_fails_with_contract_error():
    raw = lane()
    raw["findings"][0]["severity"] = "urgent"
    with pytest.raises(DeepSeekAdapterError, match="must be one of"):
        adapt_deepseek_lane(raw)


def test_duplicate_source_ids_are_rejected():
    raw = lane()
    raw["findings"].append(finding())
    with pytest.raises(DeepSeekAdapterError, match="source_id values must be unique"):
        adapt_deepseek_lane(raw)


def test_unknown_override_source_id_is_rejected():
    raw = lane()
    raw["dedupe_overrides"] = {"missing": "review.some-root-cause"}
    with pytest.raises(DeepSeekAdapterError, match="unknown source ids: missing"):
        adapt_deepseek_lane(raw)


def test_not_run_lane_cannot_carry_overrides():
    raw = lane()
    raw["execution"] = {
        "status": "NOT_RUN",
        "provenance": "UNVERIFIED",
        "details": "Credential missing.",
    }
    raw["model"]["provider"] = None
    raw["findings"] = []
    raw["dedupe_overrides"] = {"ghost": "review.some-root-cause"}
    with pytest.raises(DeepSeekAdapterError, match="must not contain dedupe overrides"):
        adapt_deepseek_lane(raw)
