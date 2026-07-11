from tools.causal_review_pilot import build_pilot_report


def native_review(reviewer_id="grok", status="COMPLETED"):
    completed = status == "COMPLETED"
    return {
        "schema_version": "ls.causal-review.v0.1",
        "reviewer": {
            "id": reviewer_id,
            "display_name": reviewer_id.title(),
            "model": "model-v1",
        },
        "target": {
            "repository": "safal207/LS",
            "pr_number": 42,
            "head_sha": "a" * 40,
            "patch_sha256": "sha256:" + "b" * 64,
        },
        "execution": {
            "status": status,
            "provenance": "MATCHED" if completed else "UNVERIFIED",
            "details": "Native causal lane.",
        },
        "verdict": "COMMENT" if completed else None,
        "risk_level": "medium" if completed else "none",
        "findings": (
            [
                {
                    "id": "GROK-1",
                    "severity": "medium",
                    "title": "Missing boundary",
                    "claim_status": "CANDIDATE",
                    "location": {"path": "a.py", "line": 1},
                    "causal_chain": {
                        "change": "A boundary changed.",
                        "root_cause": "Validation is absent.",
                        "failure_mechanism": "Malformed input crosses the boundary.",
                        "observable_effect": "Invalid state is stored.",
                        "impact": "Behavior is unreliable.",
                    },
                    "evidence": [
                        {
                            "type": "patch",
                            "reference": "a.py:1",
                            "excerpt": "+value = 1",
                        }
                    ],
                    "confidence": 0.8,
                    "reproduction": "Submit malformed input.",
                    "recommendation": "Restore validation.",
                    "dedupe_key": "native.grok.missing-boundary",
                }
            ]
            if completed
            else []
        ),
        "tests_to_run": [],
        "human_decision_points": [],
    }


def test_native_review_can_bind_to_itself_as_raw_evidence():
    grok = native_review()
    report = build_pilot_report([grok], [grok], measurement_class="ENSEMBLE")
    assert report["raw_finding_count"] == 1
    assert report["evidence_bound_count"] == 1
    assert report["root_cause_cluster_count"] == 1
    assert report["incomplete_review_count"] == 0


def test_incomplete_native_review_adds_human_queue_item():
    grok = native_review(status="NOT_RUN")
    report = build_pilot_report([grok], [grok], measurement_class="ENSEMBLE")
    assert report["raw_finding_count"] == 0
    assert report["incomplete_review_count"] == 1
    assert report["adjudication_item_count"] == 1
