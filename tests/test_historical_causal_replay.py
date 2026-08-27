import copy

import pytest

from tools.historical_causal_replay import (
    ReplayError,
    build_replay,
    summarize_replays,
)


def record(
    source_id,
    reviewer_id,
    adjudication,
    root_cause_key=None,
    *,
    commit_sha="a" * 40,
):
    return {
        "source_id": source_id,
        "reviewer_id": reviewer_id,
        "source_url": f"https://github.com/safal207/LS/pull/874#discussion_r{source_id}",
        "commit_sha": commit_sha,
        "title": f"Finding {source_id}",
        "adjudication": adjudication,
        "root_cause_key": root_cause_key,
    }


def replay_payload():
    return {
        "schema_version": "ls.historical-causal-replay.v0.1",
        "repository": "safal207/LS",
        "pr_number": 874,
        "head_sha": "a" * 40,
        "records": [
            record("1", "qodo", "TRUE_REPRODUCED", "metrics.target-binding"),
            record("2", "coderabbit", "TRUE_CONFIRMED", "metrics.target-binding"),
            record("3", "qodo", "TRUE_REPRODUCED", "metrics.boolean-coercion"),
            record("4", "coderabbit", "FALSE_POSITIVE"),
            record("5", "grok", "REQUIRES_HUMAN_DECISION"),
        ],
    }


def test_replay_clusters_true_findings_and_preserves_false_pending():
    report = build_replay(replay_payload())
    assert report["raw_finding_count"] == 5
    assert report["true_finding_count"] == 3
    assert report["false_positive_count"] == 1
    assert report["pending_decision_count"] == 1
    assert report["root_cause_cluster_count"] == 2
    assert report["corroborated_cluster_count"] == 1
    assert report["adjudication_item_count"] == 3
    assert report["causal_deduplication_rate"] == pytest.approx(1 - 2 / 3)
    assert report["human_queue_reduction"] == pytest.approx(0.4)
    assert report["measurement_status"] == "PARTIAL"
    assert report["production_claim_allowed"] is False


def test_completed_replay_is_measured_but_not_a_production_claim():
    payload = replay_payload()
    payload["records"] = payload["records"][:-1]
    report = build_replay(payload)
    assert report["measurement_status"] == "MEASURED"
    assert report["human_adjudication"] == "COMPLETE"
    assert report["production_claim_allowed"] is False


def test_cross_head_record_is_rejected():
    payload = replay_payload()
    payload["records"][0]["commit_sha"] = "c" * 40
    with pytest.raises(ReplayError, match="does not match replay head"):
        build_replay(payload)


def test_true_finding_requires_normalized_root_cause_key():
    payload = replay_payload()
    payload["records"][0]["root_cause_key"] = None
    with pytest.raises(ReplayError, match="root_cause_key is required"):
        build_replay(payload)


def test_duplicate_source_id_is_rejected():
    payload = replay_payload()
    payload["records"].append(copy.deepcopy(payload["records"][0]))
    with pytest.raises(ReplayError, match="duplicate source_id"):
        build_replay(payload)


def test_source_url_must_point_to_target_repository():
    payload = replay_payload()
    payload["records"][0]["source_url"] = "https://github.com/other/repo/pull/1"
    with pytest.raises(ReplayError, match="must point to safal207/LS"):
        build_replay(payload)


def test_summary_does_not_merge_clusters_across_targets():
    first = build_replay(replay_payload())
    second_payload = replay_payload()
    second_payload["pr_number"] = 875
    second_payload["head_sha"] = "c" * 40
    for item in second_payload["records"]:
        item["commit_sha"] = "c" * 40
        item["source_url"] = item["source_url"].replace("/874", "/875")
    second = build_replay(second_payload)
    summary = summarize_replays([first, second])
    assert summary["target_count"] == 2
    assert summary["raw_finding_count"] == 10
    assert summary["root_cause_cluster_count"] == 4
    assert summary["human_queue_reduction"] == pytest.approx(0.4)


def test_duplicate_summary_target_is_rejected():
    report = build_replay(replay_payload())
    with pytest.raises(ReplayError, match="duplicate replay target"):
        summarize_replays([report, report])
