from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.contracts import (
    CognitiveTrail,
    ReplayDecision,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)
from modules.trusted_runtime.persistence import (
    InMemoryEventStoreAdapter,
    JsonlEventStoreAdapter,
)
from modules.trusted_runtime.replay import (
    DeterministicReplayAdapter,
    LTPConfig,
    LTPReplayAdapter,
    ReplayDisabledError,
    append_replay_outcome,
    attach_replay_outcome,
    replay_from_store,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/replay"
SCHEMAS = ROOT / "schemas/trusted_runtime"
NOW = "2026-06-23T13:01:00Z"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _specs(
    limit: Optional[int] = None,
    mutation: Optional[dict] = None,
) -> list[dict]:
    fixture = _load("clean_path.json")
    events = []
    for source in fixture["events"]:
        event = json.loads(json.dumps(source))
        event["task_id"] = fixture["task_id"]
        event["trail_id"] = fixture["trail_id"]
        if mutation is not None and event["event_id"] == mutation["event_id"]:
            event["payload"][mutation["payload_key"]] = mutation["replacement"]
        events.append(event)
    return events if limit is None else events[:limit]


def _store(
    specs: Optional[list[dict]] = None,
) -> InMemoryEventStoreAdapter:
    store = InMemoryEventStoreAdapter()
    for event in specs or _specs():
        store.append(event)
    return store


def _trail() -> CognitiveTrail:
    events = tuple(
        TrailEvent(
            event_id=item["event_id"],
            task_id=item["task_id"],
            trail_id=item["trail_id"],
            event_type=TrailEventType(item["event_type"]),
            actor=item["actor"],
            created_at=item["created_at"],
            parent_cause=item["parent_cause"],
            evidence_refs=tuple(item.get("evidence_refs", ())),
            payload=dict(item.get("payload", {})),
        )
        for item in _specs()
    )
    return CognitiveTrail(
        task_id="task-replay-001",
        trail_id="trail-replay-001",
        actor="runtime:ls",
        created_at="2026-06-23T13:00:00Z",
        events=events,
    )


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def test_clean_trace_is_admissible_and_exportable() -> None:
    store = _store()
    engine = DeterministicReplayAdapter()

    first = engine.replay(store.read_events("trail-replay-001"), now=NOW)
    second = engine.replay(store.read_events("trail-replay-001"), now=NOW)

    assert first.record.decision is ReplayDecision.ADMISSIBLE
    assert first.record.drift_refs == ()
    assert first.report.findings == ()
    assert first.report.verified_event_count == 9
    assert first.checkpoint.next_expected_event_type == "REPLAY_CHECKED"
    assert first.record.replay_id == second.record.replay_id
    assert first.report.report_id == second.report.report_id

    files = first.export_files()
    assert set(files) == {
        "trace.jsonl",
        "replay-record.json",
        "conformance-report.json",
        "resume-checkpoint.json",
        "README.md",
    }
    joined = "\n".join(files.values())
    assert "private request text" not in joined
    assert "private model result" not in joined
    assert "[REDACTED]" in joined
    assert "were not rerun" in files["README.md"]

    validators = {
        "replay-record.json": "replay_record.schema.json",
        "conformance-report.json": "conformance_report.schema.json",
        "resume-checkpoint.json": "resume_checkpoint.schema.json",
    }
    for output_name, schema_name in validators.items():
        payload = json.loads(files[output_name])
        validator = Draft202012Validator(_schema(schema_name))
        assert list(validator.iter_errors(payload)) == []


def test_baseline_payload_change_is_drifted() -> None:
    drift = _load("drift.json")
    baseline_store = _store()
    baseline = {
        event.event_id: event.payload_digest
        for event in baseline_store.read_events("trail-replay-001")
    }
    changed_store = _store(_specs(mutation=drift))

    outcome = DeterministicReplayAdapter().replay(
        changed_store.read_events("trail-replay-001"),
        now=NOW,
        baseline_payload_digests=baseline,
    )

    assert outcome.record.decision is ReplayDecision.DRIFTED
    assert any(
        finding.code == drift["expected_code"]
        for finding in outcome.report.findings
    )
    assert outcome.record.drift_refs


def test_authorization_after_block_is_rejected() -> None:
    rejected = _load("rejected.json")
    store = _store(_specs(mutation=rejected))

    outcome = DeterministicReplayAdapter().replay(
        store.read_events("trail-replay-001"),
        now=NOW,
    )

    assert outcome.record.decision is ReplayDecision.REJECTED
    assert any(
        finding.code == rejected["expected_code"]
        for finding in outcome.report.findings
    )


def test_partial_trace_resumes_from_last_durable_stage() -> None:
    fixture = _load("partial.json")
    store = _store(_specs(limit=fixture["event_count"]))

    outcome = replay_from_store(store, "trail-replay-001", now=NOW)

    assert outcome.record.decision.value == fixture["expected_decision"]
    assert outcome.checkpoint.last_event_id == "event-route"
    assert (
        outcome.checkpoint.next_expected_event_type
        == fixture["expected_next_event_type"]
    )
    assert any(
        finding.code == fixture["expected_code"]
        for finding in outcome.report.findings
    )


def test_corrupted_tail_replays_only_valid_prefix(tmp_path: Path) -> None:
    fixture = _load("corrupted.json")
    path = tmp_path / "events.jsonl"
    store = JsonlEventStoreAdapter(path)
    for event in _specs(limit=3):
        store.append(event)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(fixture["corrupted_tail"] + "\n")

    outcome = replay_from_store(store, "trail-replay-001", now=NOW)

    assert outcome.record.decision.value == fixture["expected_decision"]
    assert outcome.checkpoint.corrupted_tail is True
    assert outcome.checkpoint.last_event_id == "event-route"
    assert outcome.checkpoint.next_expected_event_type == "WORK_COMPLETED"
    assert any(
        finding.code == fixture["expected_code"]
        for finding in outcome.report.findings
    )


def test_tampered_durable_event_hash_is_rejected() -> None:
    store = _store()
    payloads = [event.to_dict() for event in store.read_events("trail-replay-001")]
    payloads[3]["payload"]["payload"]["artifact_digest"] = "sha256:tampered"

    outcome = DeterministicReplayAdapter().replay(payloads, now=NOW)

    assert outcome.record.decision is ReplayDecision.REJECTED
    assert any(
        finding.code == "EVENT_HASH_MISMATCH"
        for finding in outcome.report.findings
    )
    assert outcome.report.verified_event_count == 3


def test_ltp_adapter_is_disabled_by_default() -> None:
    events = _store().read_events("trail-replay-001")

    with pytest.raises(ReplayDisabledError):
        LTPReplayAdapter().replay(events, now=NOW)

    enabled = LTPReplayAdapter(LTPConfig(enabled=True))
    assert enabled.replay(events, now=NOW).record.decision is ReplayDecision.ADMISSIBLE


def test_replay_outcome_extends_trail_and_artifact() -> None:
    trail = _trail()
    outcome = DeterministicReplayAdapter().replay(
        _store().read_events(trail.trail_id),
        now=NOW,
    )

    extended = append_replay_outcome(
        trail,
        outcome,
        parent_event_id="event-executed",
    )

    assert len(extended.events) == len(trail.events) + 1
    replay_event = extended.events[-1]
    assert replay_event.event_type is TrailEventType.REPLAY_CHECKED
    assert replay_event.parent_cause == "event-executed"
    assert replay_event.payload["decision"] == "ADMISSIBLE"
    assert replay_event.payload["report_ref"] == outcome.report_ref

    artifact = ReusableArtifact(
        artifact_id="artifact-replay-001",
        task_id=trail.task_id,
        trail_id=trail.trail_id,
        created_at="2026-06-23T13:02:00Z",
        route_refs=("route:review-001",),
        evidence_refs=("evidence:review-001",),
        contribution_refs=("contribution:review-001",),
        decision_ref="decision:review-001",
        execution_ref="execution-record:review-001",
        replay_ref=None,
    )
    attached = attach_replay_outcome(artifact, outcome)

    assert attached.replay_ref == outcome.report_ref
