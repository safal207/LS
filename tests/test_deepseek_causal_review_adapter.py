import copy

import pytest

from tools.deepseek_causal_review_adapter import (
    DeepSeekAdapterError,
    adapt_deepseek_lane,
)


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 874,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def native_finding(source_id="deepseek-1"):
    return {
        "source_id": source_id,
        "severity": "high",
        "title": "Patch digest is not bound to reviewed bytes",
        "location": {"path": "tools/reviewer.py", "line": 42},
        "causal_chain": {
            "change": "The reviewer receives a transformed patch.",
            "root_cause": "The recorded digest is computed from different bytes.",
            "failure_mechanism": "The artifact attests content the model did not receive.",
            "observable_effect": "Replaying the recorded digest yields a different prompt payload.",
            "impact": "Audit evidence can falsely appear reproducible.",
        },
        "evidence": [
            {
                "type": "patch",
                "reference": "tools/reviewer.py:42-61",
                "excerpt": "Digest is computed before transformation.",
            }
        ],
        "confidence": 0.88,
        "reproduction": "Compare the recorded digest with the exact transmitted bytes.",
        "recommendation": "Hash the exact bytes sent to the model or fail closed.",
    }


def lane(*, status="COMPLETED", provenance="MATCHED", findings=None):
    return {
        "schema_version": "ls.deepseek-causal-lane.v0.1",
        "target": target(),
        "model": {
            "requested": "deepseek/deepseek-r1",
            "provider": "deepseek/deepseek-r1" if status == "COMPLETED" else None,
        },
        "execution": {
            "status": status,
            "provenance": provenance,
            "details": "Wrapper-recorded DeepSeek execution metadata.",
        },
        "findings": [native_finding()] if findings is None else findings,
        "dedupe_overrides": {},
        "tests_to_run": ["Replay the digest comparison."],
        "human_decision_points": ["Confirm whether audit mismatch is release-blocking."],
    }


def test_completed_native_finding_remains_advisory_candidate():
    review = adapt_deepseek_lane(lane())

    assert review["reviewer"] == {
        "id": "deepseek",
        "display_name": "DeepSeek",
        "model": "deepseek/deepseek-r1",
    }
    assert review["verdict"] == "COMMENT"
    assert review["risk_level"] == "high"
    finding = review["findings"][0]
    assert finding["claim_status"] == "CANDIDATE"
    assert finding["causal_chain"]["root_cause"].startswith("The recorded digest")
    assert finding["dedupe_key"].startswith("external.deepseek.")


def test_not_run_lane_is_explicit_and_findingless():
    review = adapt_deepseek_lane(
        lane(status="NOT_RUN", provenance="UNVERIFIED", findings=[])
    )

    assert review["execution"]["status"] == "NOT_RUN"
    assert review["verdict"] is None
    assert review["risk_level"] == "none"
    assert review["findings"] == []


def test_not_run_lane_cannot_smuggle_findings():
    with pytest.raises(DeepSeekAdapterError, match="must not contain findings"):
        adapt_deepseek_lane(
            lane(status="NOT_RUN", provenance="UNVERIFIED")
        )


def test_completed_lane_requires_matched_provider_model():
    raw = lane()
    raw["model"]["provider"] = "deepseek/deepseek-v3"
    with pytest.raises(DeepSeekAdapterError, match="model mismatch"):
        adapt_deepseek_lane(raw)


def test_completed_lane_requires_matched_provenance():
    with pytest.raises(DeepSeekAdapterError, match="requires provenance=MATCHED"):
        adapt_deepseek_lane(lane(provenance="MISMATCH"))


def test_missing_native_causal_field_fails_closed():
    raw = lane()
    del raw["findings"][0]["causal_chain"]
    with pytest.raises(DeepSeekAdapterError, match="missing required properties: causal_chain"):
        adapt_deepseek_lane(raw)


def test_explicit_override_can_map_reviewed_root_cause():
    raw = lane()
    raw["dedupe_overrides"] = {
        "deepseek-1": "review.patch-byte-attestation"
    }
    review = adapt_deepseek_lane(raw)
    assert review["findings"][0]["dedupe_key"] == "review.patch-byte-attestation"


def test_override_cannot_impersonate_provider_local_namespace():
    raw = lane()
    raw["dedupe_overrides"] = {
        "deepseek-1": "external.deepseek.fake"
    }
    with pytest.raises(DeepSeekAdapterError, match="reserved external"):
        adapt_deepseek_lane(raw)


def test_unknown_root_property_is_rejected():
    raw = lane()
    raw["provider_verdict"] = "APPROVE"
    with pytest.raises(DeepSeekAdapterError, match="unknown properties: provider_verdict"):
        adapt_deepseek_lane(raw)


def test_invalid_exact_target_is_rejected_by_base_contract():
    raw = copy.deepcopy(lane())
    raw["target"]["head_sha"] = "not-a-sha"
    with pytest.raises(Exception, match="head_sha"):
        adapt_deepseek_lane(raw)
