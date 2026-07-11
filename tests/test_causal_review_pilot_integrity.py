import copy

import pytest

from tools.causal_review_adapters import adapt_external_review
from tools.causal_review_pilot import PilotError, build_pilot_report


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 876,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def qodo_bundle(thread_id="qodo-1"):
    return {
        "provider": "qodo",
        "target": target(),
        "execution": {
            "status": "COMPLETED",
            "provenance": "MATCHED",
            "details": "Exact Qodo thread was collected.",
        },
        "threads": [
            {
                "id": thread_id,
                "author": {"login": "qodo-code-review"},
                "path": "tools/example.py",
                "line": 10,
                "is_resolved": False,
                "is_outdated": False,
                "source_url": f"https://github.example/{thread_id}",
                "body": (
                    '1\\. Missing invariant <code>Bug</code>\n'
                    '<pre>Input bypasses validation.</pre>'
                ),
            }
        ],
        "dedupe_overrides": {},
    }


def test_duplicate_provider_lanes_are_rejected():
    first = qodo_bundle("qodo-1")
    second = qodo_bundle("qodo-2")
    with pytest.raises(PilotError, match="one lane per provider"):
        build_pilot_report(
            [first, second],
            [adapt_external_review(first), adapt_external_review(second)],
        )


def test_missing_adapted_finding_is_rejected():
    raw = qodo_bundle()
    review = adapt_external_review(raw)
    review["findings"] = []
    review["risk_level"] = "none"
    with pytest.raises(PilotError, match="finding count mismatch"):
        build_pilot_report([raw], [review])


def test_extra_adapted_finding_is_rejected():
    raw = qodo_bundle()
    review = adapt_external_review(raw)
    review["findings"].append(copy.deepcopy(review["findings"][0]))
    review["findings"][1]["id"] = "QODO-EXTRA"
    with pytest.raises(PilotError, match="finding count mismatch"):
        build_pilot_report([raw], [review])


def test_resolved_raw_thread_requires_zero_active_findings():
    raw = qodo_bundle()
    raw["threads"][0]["is_resolved"] = True
    review = adapt_external_review(raw)
    report = build_pilot_report([raw], [review])
    assert report["raw_finding_count"] == 1
    assert report["ignored_thread_count"] == 1
    assert report["evidence_bound_count"] == 0
