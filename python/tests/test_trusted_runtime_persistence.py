from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.contracts import (
    CognitiveTrail,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)
from modules.trusted_runtime.persistence import (
    GENESIS_HASH,
    EventStoreConflictError,
    EventStoreCorruptionError,
    EventStoreDisabledError,
    EventStoreUnavailableError,
    InMemoryEventStoreAdapter,
    JsonlEventStoreAdapter,
    LiminalDBConfig,
    LiminalDBEventStoreAdapter,
    digest_json,
    normalize_event_mapping,
    persist_artifact_metadata,
    persist_cognitive_trail,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/replay"
SCHEMAS = ROOT / "schemas/trusted_runtime"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _specs(limit: int | None = None) -> list[dict]:
    fixture = _load("clean_path.json")
    events = []
    for item in fixture["events"]:
        event = dict(item)
        event["task_id"] = fixture["task_id"]
        event["trail_id"] = fixture["trail_id"]
        events.append(event)
    return events if limit is None else events[:limit]


def _trail(limit: int | None = None) -> CognitiveTrail:
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
        for item in _specs(limit)
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


def test_jsonl_store_builds_hash_chain_and_redacts_payloads(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    store = JsonlEventStoreAdapter(path)
    trail = _trail()

    first_refs = persist_cognitive_trail(store, trail)
    second_refs = persist_cognitive_trail(store, trail)
    events = store.read_events(trail.trail_id)

    assert first_refs == second_refs
    assert len(events) == len(trail.events)
    assert len(path.read_text(encoding="utf-8").splitlines()) == len(trail.events)
    assert events[0].previous_hash == GENESIS_HASH
    for index, event in enumerate(events):
        assert event.sequence == index
        assert event.verify_hash()
        if index:
            assert event.previous_hash == events[index - 1].event_hash

    serialized = path.read_text(encoding="utf-8")
    assert "private request text" not in serialized
    assert "private model result" not in serialized
    assert "[REDACTED]" in serialized
    assert "payload.prompt" in events[0].redacted_fields
    assert "payload.raw_output" in events[3].redacted_fields
    assert events[0].payload_digest == digest_json(
        normalize_event_mapping(_specs()[0])
    )

    validator = Draft202012Validator(_schema("durable_event.schema.json"))
    assert list(validator.iter_errors(events[0].to_dict())) == []


def test_duplicate_event_id_with_new_content_fails_closed(tmp_path: Path) -> None:
    store = JsonlEventStoreAdapter(tmp_path / "events.jsonl")
    event = _specs()[0]
    store.append(event)
    changed = json.loads(json.dumps(event))
    changed["payload"]["intent"] = "different intent"

    with pytest.raises(EventStoreConflictError, match="different content"):
        store.append(changed)


def test_reordered_jsonl_events_are_detected(tmp_path: Path) -> None:
    fixture = _load("reordered.json")
    path = tmp_path / "events.jsonl"
    store = JsonlEventStoreAdapter(path)
    persist_cognitive_trail(store, _trail())
    lines = path.read_text(encoding="utf-8").splitlines()
    left, right = (index - 1 for index in fixture["swap_lines"])
    lines[left], lines[right] = lines[right], lines[left]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    scan = store.scan("trail-replay-001")

    assert not scan.is_valid
    assert scan.events == ()
    assert any(
        finding.code == fixture["expected_store_code"]
        for finding in scan.findings
    )
    with pytest.raises(EventStoreCorruptionError):
        store.read_events("trail-replay-001")


def test_corrupted_tail_preserves_last_valid_prefix(tmp_path: Path) -> None:
    fixture = _load("corrupted.json")
    path = tmp_path / "events.jsonl"
    store = JsonlEventStoreAdapter(path)
    persist_cognitive_trail(store, _trail(limit=3))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(fixture["corrupted_tail"] + "\n")

    scan = store.scan("trail-replay-001")

    assert len(scan.events) == 3
    assert scan.last_valid_event is not None
    assert scan.last_valid_event.event_id == "event-route"
    assert scan.stopped_at_line == 4
    assert scan.findings[0].code == "CORRUPTED_JSON"
    with pytest.raises(EventStoreCorruptionError):
        store.read_events("trail-replay-001")


def test_in_memory_store_has_same_idempotent_contract() -> None:
    store = InMemoryEventStoreAdapter()
    trail = _trail(limit=4)

    first = persist_cognitive_trail(store, trail)
    second = persist_cognitive_trail(store, trail)

    assert first == second
    assert store.scan(trail.trail_id).is_valid
    assert len(store.read_events(trail.trail_id)) == 4


def test_artifact_metadata_is_appended_after_the_workflow(tmp_path: Path) -> None:
    store = JsonlEventStoreAdapter(tmp_path / "events.jsonl")
    trail = _trail()
    persist_cognitive_trail(store, trail)
    artifact = ReusableArtifact(
        artifact_id="artifact-replay-001",
        task_id=trail.task_id,
        trail_id=trail.trail_id,
        created_at="2026-06-23T13:00:10Z",
        route_refs=("route:review-001",),
        evidence_refs=("evidence:review-001",),
        contribution_refs=("contribution:review-001",),
        decision_ref="decision:review-001",
        execution_ref="execution-record:review-001",
        replay_ref="conformance-report:review-001",
    )

    reference = persist_artifact_metadata(
        store,
        artifact,
        actor="runtime:ls",
        parent_event_id="event-executed",
    )
    events = store.read_events(trail.trail_id)

    assert reference == events[-1].event_ref
    assert events[-1].event_type == "ARTIFACT_CREATED"
    assert events[-1].parent_event_id == "event-executed"
    assert events[-1].payload["payload"]["artifact_id"] == artifact.artifact_id


class FakeLiminalClient:
    def __init__(self, events: list[dict]) -> None:
        self.events = list(events)

    def append_event(self, event: dict) -> str:
        self.events.append(event)
        return str(event["event_ref"])

    def read_events(self, trail_id: str) -> list[dict]:
        return [event for event in self.events if event["trail_id"] == trail_id]


def test_liminaldb_adapter_is_feature_flagged_and_validates_reads() -> None:
    source = InMemoryEventStoreAdapter()
    persist_cognitive_trail(source, _trail(limit=3))
    payloads = [event.to_dict() for event in source.read_events("trail-replay-001")]

    with pytest.raises(EventStoreDisabledError):
        LiminalDBEventStoreAdapter().read("trail-replay-001")
    with pytest.raises(EventStoreUnavailableError):
        LiminalDBEventStoreAdapter(LiminalDBConfig(enabled=True)).read(
            "trail-replay-001"
        )

    client = FakeLiminalClient(payloads)
    adapter = LiminalDBEventStoreAdapter(
        LiminalDBConfig(enabled=True),
        client,
    )
    loaded = adapter.read("trail-replay-001")

    assert len(loaded) == 3
    assert loaded[-1]["event_id"] == "event-route"
    assert adapter.append(payloads[-1]) == payloads[-1]["event_ref"]
