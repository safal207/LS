import copy

import pytest

from tools.causal_review import ContractError
from tools.causal_review_adapters import (
    AdapterError,
    adapt_external_review,
    build_noise_report,
)


def target():
    return {
        "repository": "safal207/LS",
        "pr_number": 866,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + "b" * 64,
    }


def qodo_thread(thread_id="qodo-thread", *, resolved=False, outdated=False):
    return {
        "id": thread_id,
        "author": {"login": "qodo-code-review"},
        "path": "tools/reviewer.py",
        "line": 42,
        "is_resolved": resolved,
        "is_outdated": outdated,
        "source_url": f"https://github.example/review/{thread_id}",
        "body": (
            '<img alt="Action required">\n\n'
            '1\\. Patch fence can be broken <code>Bug</code> <code>Security</code>\n\n'
            '<pre>Raw patch content can close a Markdown fence and escape the data boundary.</pre>\n\n'
            '## Implementation guidance\n'
            'Transport the patch as a JSON string and treat it only as data.\n'
            '```'
        ),
    }


def coderabbit_thread(thread_id="coderabbit-thread", *, resolved=False, outdated=False):
    return {
        "id": thread_id,
        "author": {"login": "coderabbitai"},
        "path": "tools/reviewer.py",
        "line": 42,
        "is_resolved": resolved,
        "is_outdated": outdated,
        "source_url": f"https://github.example/review/{thread_id}",
        "body": (
            '_Data Integrity_ | _🟠 Major_ | _Quick win_\n\n'
            '**Patch framing is unsafe.**\n\n'
            'Raw patch content can close a Markdown fence and escape the data boundary.\n'
            '<details><summary>Prompt for AI Agents</summary>more</details>'
        ),
    }


def bundle(provider, threads, *, status="COMPLETED", provenance="MATCHED"):
    return {
        "provider": provider,
        "target": target(),
        "execution": {
            "status": status,
            "provenance": provenance,
            "details": f"{provider} author and target metadata were verified.",
        },
        "threads": threads,
        "dedupe_overrides": {},
    }


def test_qodo_thread_becomes_evidence_bound_candidate():
    review = adapt_external_review(bundle("qodo", [qodo_thread()]))

    assert review["reviewer"]["id"] == "qodo"
    assert review["verdict"] == "COMMENT"
    assert review["risk_level"] == "high"
    assert len(review["findings"]) == 1
    finding = review["findings"][0]
    assert finding["title"] == "Patch fence can be broken"
    assert finding["claim_status"] == "CANDIDATE"
    assert finding["evidence"][0]["reference"].endswith("qodo-thread")
    assert finding["dedupe_key"].startswith("external.qodo.")


def test_coderabbit_thread_maps_major_to_high_without_gate_authority():
    review = adapt_external_review(bundle("coderabbit", [coderabbit_thread()]))

    assert review["reviewer"]["display_name"] == "CodeRabbit"
    assert review["verdict"] == "COMMENT"
    assert review["risk_level"] == "high"
    finding = review["findings"][0]
    assert finding["title"] == "Patch framing is unsafe."
    assert finding["severity"] == "high"
    assert finding["dedupe_key"].startswith("external.coderabbit.")


def test_resolved_and_outdated_threads_leave_the_active_queue():
    review = adapt_external_review(
        bundle(
            "qodo",
            [
                qodo_thread("resolved", resolved=True),
                qodo_thread("outdated", outdated=True),
            ],
        )
    )

    assert review["findings"] == []
    assert review["risk_level"] == "none"
    assert any("2 resolved or outdated" in item for item in review["human_decision_points"])


def test_unexpected_author_fails_provenance_closed():
    raw = qodo_thread()
    raw["author"]["login"] = "untrusted-review-bot"

    with pytest.raises(AdapterError, match="does not match qodo"):
        adapt_external_review(bundle("qodo", [raw]))


def test_not_run_external_lane_cannot_publish_findings_or_verdict():
    raw = bundle("qodo", [qodo_thread()], status="NOT_RUN", provenance="UNVERIFIED")
    review = adapt_external_review(raw)

    assert review["execution"]["status"] == "NOT_RUN"
    assert review["verdict"] is None
    assert review["risk_level"] == "none"
    assert review["findings"] == []


def test_similar_provider_wording_does_not_auto_corroborate():
    qodo = bundle("qodo", [qodo_thread()])
    coderabbit = bundle("coderabbit", [coderabbit_thread()])
    qodo_review = adapt_external_review(qodo)
    coderabbit_review = adapt_external_review(coderabbit)

    report = build_noise_report(
        [qodo, coderabbit],
        [qodo_review, coderabbit_review],
    )

    assert report["raw_finding_count"] == 2
    assert report["evidence_bound_count"] == 2
    assert report["root_cause_cluster_count"] == 2
    assert report["corroborated_cluster_count"] == 0
    assert report["provider_local_key_count"] == 2
    assert report["human_queue_reduction"] == 0.0


def test_explicit_human_override_can_create_corroboration():
    qodo = bundle("qodo", [qodo_thread()])
    coderabbit = bundle("coderabbit", [coderabbit_thread()])
    qodo["dedupe_overrides"] = {"qodo-thread": "prompt.patch-framing-boundary"}
    coderabbit["dedupe_overrides"] = {
        "coderabbit-thread": "prompt.patch-framing-boundary"
    }

    report = build_noise_report(
        [qodo, coderabbit],
        [adapt_external_review(qodo), adapt_external_review(coderabbit)],
    )

    assert report["root_cause_cluster_count"] == 1
    assert report["corroborated_cluster_count"] == 1
    assert report["explicit_override_count"] == 2
    assert report["causal_deduplication_rate"] == pytest.approx(0.5)
    assert report["human_queue_reduction"] == pytest.approx(0.5)


def test_resolved_threads_are_counted_as_raw_but_not_evidence_bound():
    qodo = bundle(
        "qodo",
        [qodo_thread("active"), qodo_thread("resolved", resolved=True)],
    )
    review = adapt_external_review(qodo)

    report = build_noise_report([qodo], [review])

    assert report["raw_finding_count"] == 2
    assert report["ignored_thread_count"] == 1
    assert report["evidence_bound_count"] == 1
    assert report["contract_rejection_rate"] == pytest.approx(0.5)


def test_noise_report_rejects_different_exact_targets():
    qodo = bundle("qodo", [qodo_thread()])
    coderabbit = bundle("coderabbit", [coderabbit_thread()])
    coderabbit["target"] = copy.deepcopy(target())
    coderabbit["target"]["head_sha"] = "c" * 40

    with pytest.raises(ContractError, match="must share repository"):
        build_noise_report(
            [qodo, coderabbit],
            [adapt_external_review(qodo), adapt_external_review(coderabbit)],
        )
