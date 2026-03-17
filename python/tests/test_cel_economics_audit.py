from modules.cel.economics_audit import EconomicsAudit


def test_economics_audit_summary_and_efficiency() -> None:
    events = [
        {"event_type": "proposal_created", "ts": 100, "data": {"proposal_id": "p1"}},
        {"event_type": "artifact_verified", "ts": 130, "data": {"proposal_id": "p1", "verdict": "verified"}},
        {"event_type": "payout_released", "ts": 160, "data": {"proposal_id": "p1", "amount_ct": 12.5}},
        {"event_type": "proposal_created", "ts": 200, "data": {"proposal_id": "p2"}},
        {"event_type": "artifact_verified", "ts": 250, "data": {"proposal_id": "p2", "verdict": "rejected"}},
        {"event_type": "task_disputed", "ts": 270, "data": {"proposal_id": "p2"}},
        {"event_type": "rollback_applied", "ts": 280, "data": {"proposal_id": "p2"}},
        {"event_type": "payout_released", "ts": 400, "data": {"proposal_id": "p2", "amount_ct": 5.0}},
    ]

    report = EconomicsAudit().summarize(events)

    assert report.total_events == 8
    assert report.proposal_count == 2
    assert report.gmv_ct == 17.5
    assert report.payout_events == 2
    assert report.median_payout_latency_s == 130.0
    assert report.verification_pass_rate == 0.5
    assert report.dispute_rate == 0.5
    assert report.rollback_rate == 0.5
    assert 0.0 <= report.economic_efficiency_score <= 1.0


def test_economics_audit_empty() -> None:
    report = EconomicsAudit().summarize([])
    assert report.total_events == 0
    assert report.proposal_count == 0
    assert report.economic_efficiency_score == 0.0


def test_economics_audit_clamps_rates_to_one() -> None:
    events = [
        {"event_type": "proposal_created", "ts": 100, "data": {"proposal_id": "p1"}},
        {"event_type": "task_disputed", "ts": 110, "data": {"proposal_id": "p1"}},
        {"event_type": "task_disputed", "ts": 120, "data": {"proposal_id": "p1"}},
        {"event_type": "rollback_applied", "ts": 130, "data": {"proposal_id": "p1"}},
        {"event_type": "rollback_applied", "ts": 140, "data": {"proposal_id": "p1"}},
    ]
    report = EconomicsAudit().summarize(events)
    assert report.dispute_rate == 1.0
    assert report.rollback_rate == 1.0
