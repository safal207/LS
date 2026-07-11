import copy
import json

import pytest

from tools.causal_review import (
    ContractError,
    cluster_reviews,
    parse_model_json,
    render_markdown,
    validate_review,
)


def review_payload(reviewer_id="grok", dedupe_key="ci.force-push.head-race"):
    return {
        "schema_version": "ls.causal-review.v0.1",
        "reviewer": {
            "id": reviewer_id,
            "display_name": reviewer_id.title(),
            "model": "example-model",
        },
        "target": {
            "repository": "safal207/example",
            "pr_number": 57,
            "head_sha": "a" * 40,
            "patch_sha256": "sha256:" + "b" * 64,
        },
        "execution": {
            "status": "COMPLETED",
            "provenance": "MATCHED",
            "details": "Provider identity matched the configured reviewer.",
        },
        "verdict": "REQUEST_CHANGES",
        "risk_level": "high",
        "findings": [
            {
                "id": "REV-001",
                "severity": "high",
                "title": "Review can publish against a stale head",
                "claim_status": "REPRODUCED",
                "location": {
                    "path": ".github/workflows/reviewer.yml",
                    "line": 42,
                },
                "causal_chain": {
                    "change": "The workflow fetches a PR patch.",
                    "root_cause": "The current head is not rechecked after patch retrieval.",
                    "failure_mechanism": "A force-push can replace the reviewed commit before publication.",
                    "observable_effect": "The workflow publishes a verdict for an obsolete patch.",
                    "impact": "Unreviewed code can appear to have passed review.",
                },
                "evidence": [
                    {
                        "type": "patch",
                        "reference": ".github/workflows/reviewer.yml:42-68",
                        "excerpt": "The publication step has no second head-SHA check.",
                    }
                ],
                "confidence": 0.96,
                "reproduction": "Force-push after patch fetch and before comment publication.",
                "recommendation": "Recheck the exact head before and after patch retrieval.",
                "dedupe_key": dedupe_key,
            }
        ],
        "tests_to_run": [
            "Simulate a force-push between patch retrieval and publication."
        ],
        "human_decision_points": [
            "Decide whether a stale-head mismatch should fail or remain advisory."
        ],
    }


def test_valid_completed_review_is_normalized():
    review = validate_review(review_payload())
    assert review["execution"]["status"] == "COMPLETED"
    assert review["findings"][0]["dedupe_key"] == "ci.force-push.head-race"
    assert review["findings"][0]["confidence"] == 0.96


def test_missing_evidence_is_rejected():
    payload = review_payload()
    payload["findings"][0]["evidence"] = []
    with pytest.raises(ContractError, match="at least one"):
        validate_review(payload)


def test_completed_review_requires_matched_provenance():
    payload = review_payload()
    payload["execution"]["provenance"] = "MISMATCH"
    with pytest.raises(ContractError, match="provenance=MATCHED"):
        validate_review(payload)


def test_not_run_lane_cannot_launder_a_verdict():
    payload = review_payload()
    payload["execution"] = {
        "status": "NOT_RUN",
        "provenance": "UNVERIFIED",
        "details": "Credential was unavailable.",
    }
    payload["verdict"] = None
    payload["risk_level"] = "none"
    payload["findings"] = []

    review = validate_review(payload)
    assert review["verdict"] is None
    assert review["findings"] == []


def test_not_run_lane_with_verdict_is_rejected():
    payload = review_payload()
    payload["execution"]["status"] = "NOT_RUN"
    payload["execution"]["provenance"] = "UNVERIFIED"
    with pytest.raises(ContractError, match="must not publish a verdict"):
        validate_review(payload)


def test_duplicate_finding_ids_are_rejected():
    payload = review_payload()
    payload["findings"].append(copy.deepcopy(payload["findings"][0]))
    with pytest.raises(ContractError, match="duplicate finding id"):
        validate_review(payload)


def test_fenced_model_json_is_parsed():
    payload = {"verdict": "COMMENT", "findings": []}
    parsed = parse_model_json("```json\n" + json.dumps(payload) + "\n```")
    assert parsed == payload


def test_same_root_cause_clusters_across_reviewers():
    grok = review_payload("grok")
    qodo = review_payload("qodo")
    qodo["findings"][0]["id"] = "QODO-017"

    result = cluster_reviews([grok, qodo])

    assert result["cluster_count"] == 1
    cluster = result["clusters"][0]
    assert cluster["status"] == "CORROBORATED"
    assert cluster["support_count"] == 2
    assert cluster["reviewer_ids"] == ["grok", "qodo"]


def test_same_symptom_with_different_root_causes_is_not_merged():
    first = review_payload("grok", "ci.force-push.head-race")
    second = review_payload("qodo", "ci.comment.permissions")
    second["findings"][0]["id"] = "QODO-002"
    second["findings"][0]["causal_chain"]["observable_effect"] = (
        first["findings"][0]["causal_chain"]["observable_effect"]
    )

    result = cluster_reviews([first, second])

    assert result["cluster_count"] == 2
    assert {item["dedupe_key"] for item in result["clusters"]} == {
        "ci.force-push.head-race",
        "ci.comment.permissions",
    }


def test_markdown_renders_the_causal_chain():
    markdown = render_markdown(review_payload())
    assert "Root cause:" in markdown
    assert "Failure mechanism:" in markdown
    assert "Observable effect:" in markdown
    assert "Root-cause key:" in markdown
