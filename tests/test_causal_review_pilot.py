import copy

import pytest

from tools.causal_review_adapters import adapt_external_review
from tools.causal_review_pilot import PilotError, build_pilot_report
from tools.deepseek_causal_review_adapter import adapt_deepseek_lane


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 875,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def qodo_bundle(*, status="COMPLETED", provenance="MATCHED", key=None):
    bundle = {
        "provider": "qodo",
        "target": target(),
        "execution": {
            "status": status,
            "provenance": provenance,
            "details": "Exact Qodo thread collection status.",
        },
        "threads": [
            {
                "id": "qodo-1",
                "author": {"login": "qodo-code-review"},
                "path": "tools/example.py",
                "line": 10,
                "is_resolved": False,
                "is_outdated": False,
                "source_url": "https://github.example/qodo-1",
                "body": (
                    '1\\. Missing invariant <code>Bug</code>\n'
                    '<pre>Input bypasses validation and corrupts metrics.</pre>'
                ),
            }
        ],
        "dedupe_overrides": {},
    }
    if key:
        bundle["dedupe_overrides"] = {"qodo-1": key}
    return bundle


def coderabbit_diagnostic():
    return {
        "provider": "coderabbit",
        "target": target(),
        "execution": {
            "status": "DIAGNOSTIC",
            "provenance": "UNVERIFIED",
            "details": "No provider-authored thread found.",
        },
        "threads": [],
        "dedupe_overrides": {},
    }


def deepseek_lane(*, completed=False, key=None):
    findings = []
    provider_model = None
    status = "NOT_RUN"
    provenance = "UNVERIFIED"
    details = "DeepSeek credential was not configured."
    overrides = {}
    if completed:
        status = "COMPLETED"
        provenance = "MATCHED"
        provider_model = "deepseek/deepseek-r1"
        details = "Exact DeepSeek model provenance matched."
        findings = [
            {
                "source_id": "deepseek-1",
                "severity": "high",
                "title": "Missing invariant",
                "location": {"path": "tools/example.py", "line": 10},
                "causal_chain": {
                    "change": "Validation was removed.",
                    "root_cause": "The input invariant is absent.",
                    "failure_mechanism": "Malformed input reaches metrics.",
                    "observable_effect": "Metrics contain invalid values.",
                    "impact": "The report becomes unreliable.",
                },
                "evidence": [
                    {
                        "type": "patch",
                        "reference": "tools/example.py:10",
                        "excerpt": "Validation is absent.",
                    }
                ],
                "confidence": 0.8,
                "reproduction": "Submit malformed input.",
                "recommendation": "Restore validation.",
            }
        ]
        if key:
            overrides = {"deepseek-1": key}
    return {
        "schema_version": "ls.deepseek-causal-lane.v0.1",
        "target": target(),
        "model": {
            "requested": "deepseek/deepseek-r1",
            "provider": provider_model,
        },
        "execution": {
            "status": status,
            "provenance": provenance,
            "details": details,
        },
        "findings": findings,
        "dedupe_overrides": overrides,
        "tests_to_run": [],
        "human_decision_points": [],
    }


def test_incomplete_lanes_increase_provisional_human_queue():
    qodo = qodo_bundle()
    coderabbit = coderabbit_diagnostic()
    deepseek = deepseek_lane()
    report = build_pilot_report(
        [qodo, coderabbit, deepseek],
        [
            adapt_external_review(qodo),
            adapt_external_review(coderabbit),
            adapt_deepseek_lane(deepseek),
        ],
        measurement_class="PILOT",
    )

    assert report["raw_finding_count"] == 1
    assert report["root_cause_cluster_count"] == 1
    assert report["incomplete_review_count"] == 2
    assert report["adjudication_item_count"] == 3
    assert report["human_queue_reduction"] == pytest.approx(-2.0)
    assert report["production_claim_allowed"] is False
    assert report["human_adjudication"] == "PENDING"


def test_explicit_cross_provider_mapping_reduces_queue_provisionally():
    key = "validation.input-invariant"
    qodo = qodo_bundle(key=key)
    deepseek = deepseek_lane(completed=True, key=key)
    report = build_pilot_report(
        [qodo, deepseek],
        [adapt_external_review(qodo), adapt_deepseek_lane(deepseek)],
    )

    assert report["raw_finding_count"] == 2
    assert report["evidence_bound_count"] == 2
    assert report["root_cause_cluster_count"] == 1
    assert report["corroborated_cluster_count"] == 1
    assert report["adjudication_item_count"] == 1
    assert report["human_queue_reduction"] == pytest.approx(0.5)


def test_raw_review_target_mismatch_is_rejected():
    qodo = qodo_bundle()
    review = adapt_external_review(qodo)
    mismatched = copy.deepcopy(qodo)
    mismatched["target"]["head_sha"] = "c" * 40
    with pytest.raises(PilotError, match="raw/review target mismatch"):
        build_pilot_report([mismatched], [review])


def test_raw_review_status_mismatch_is_rejected():
    qodo = qodo_bundle()
    review = adapt_external_review(qodo)
    qodo["execution"]["status"] = "DIAGNOSTIC"
    with pytest.raises(PilotError, match="execution status mismatch"):
        build_pilot_report([qodo], [review])


def test_raw_review_provider_mismatch_is_rejected():
    qodo = qodo_bundle()
    review = adapt_external_review(qodo)
    qodo["provider"] = "coderabbit"
    with pytest.raises(PilotError, match="provider mismatch"):
        build_pilot_report([qodo], [review])


def test_malformed_thread_boolean_is_rejected():
    qodo = qodo_bundle()
    review = adapt_external_review(qodo)
    qodo["threads"][0]["is_resolved"] = "false"
    with pytest.raises(PilotError, match="must be a boolean"):
        build_pilot_report([qodo], [review])


def test_zero_raw_findings_produces_null_reduction_metrics():
    deepseek = deepseek_lane()
    review = adapt_deepseek_lane(deepseek)
    report = build_pilot_report([deepseek], [review])
    assert report["raw_finding_count"] == 0
    assert report["contract_rejection_rate"] is None
    assert report["human_queue_reduction"] is None


def test_empty_pilot_is_rejected():
    with pytest.raises(PilotError, match="at least one reviewer lane"):
        build_pilot_report([], [])


def test_unknown_measurement_class_is_rejected():
    deepseek = deepseek_lane()
    with pytest.raises(PilotError, match="measurement_class"):
        build_pilot_report(
            [deepseek],
            [adapt_deepseek_lane(deepseek)],
            measurement_class="PRODUCTION",
        )
