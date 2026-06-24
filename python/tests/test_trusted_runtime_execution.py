from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.adapters.capu import CaPUConfig, CaPUExecutionAdapter
from modules.trusted_runtime.authorization import ProofPathAuthorizationBundleAdapter
from modules.trusted_runtime.contracts import (
    CognitiveTrail,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)
from modules.trusted_runtime.evidence import DeterministicEvidenceGateAdapter
from modules.trusted_runtime.execution import (
    CaPUDecisionCode,
    DeterministicExecutionController,
    DurableCommitError,
    ExecutionControlDisabledError,
    ExecutionInterrupted,
    ExecutionState,
    InMemoryExecutionJournal,
    JsonFileExecutionJournal,
    ProtectedAction,
    ReviewResultFileExecutor,
    append_execution_record,
    attach_execution_record,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/execution"
SCHEMA = ROOT / "schemas/trusted_runtime/execution_record.schema.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _allow_request() -> dict:
    return {
        "request_id": "evidence-request-capu",
        "task_id": "task-capu-001",
        "trail_id": "trail-capu-001",
        "actor": "human:owner",
        "intent_ref": "intent:artifact-write-capu",
        "scope": ["artifact:write"],
        "evidence_refs": ["evidence:review-capu"],
        "policy_version": "policy.trusted-runtime.v0.1",
        "causal_audit_ref": "event-causal-audit-capu",
        "causal_authorization_allowed": True,
        "created_at": "2026-06-23T10:00:00Z",
        "artifact_digest": "evidence-sha256-capu",
        "artifact_verified": True,
        "missing_evidence_refs": [],
        "risk_flags": [],
        "escalation_reasons": [],
        "metadata": {},
    }


def _bundle():
    request = _allow_request()
    decision = DeterministicEvidenceGateAdapter().decide(request)
    intent = {
        "intent_id": request["intent_ref"],
        "task_id": request["task_id"],
        "trail_id": request["trail_id"],
        "actor": request["actor"],
        "action_ref": "artifact:write:review-result",
        "scope": request["scope"],
        "issued_at": "2026-06-23T10:00:00Z",
        "expires_at": "2026-06-23T11:00:00Z",
        "nonce": "nonce-capu-001",
        "policy_version": request["policy_version"],
        "evidence_refs": request["evidence_refs"],
        "evidence_digest": request["artifact_digest"],
        "causal_audit_refs": [request["causal_audit_ref"]],
        "parent_cause": request["causal_audit_ref"],
        "metadata": {},
    }
    return ProofPathAuthorizationBundleAdapter().build(decision, intent)


def _action(**overrides) -> ProtectedAction:
    payload = {
        "action_id": "action-review-001",
        "action_ref": "artifact:write:review-result",
        "scope": ("artifact:write",),
        "payload": {"status": "approved", "summary": "review complete"},
        "idempotency_key": "review-result-001",
        "requested_at": "2026-06-23T10:00:00Z",
        "mature_after": None,
        "expires_at": "2026-06-23T10:59:00Z",
        "metadata": {},
    }
    payload.update(overrides)
    return ProtectedAction(**payload)


class CommitAssertingExecutor(ReviewResultFileExecutor):
    def __init__(self, root: Path, journal: InMemoryExecutionJournal) -> None:
        super().__init__(root)
        self.journal = journal

    def execute(self, execution_id, action, now):
        committed = self.journal.load(execution_id)
        assert committed is not None
        assert committed.state is ExecutionState.COMMITTED
        assert committed.committed_at is not None
        return super().execute(execution_id, action, now)


def test_effect_is_invoked_only_after_durable_commit(tmp_path: Path) -> None:
    journal = InMemoryExecutionJournal()
    executor = CommitAssertingExecutor(tmp_path / "effects", journal)
    controller = DeterministicExecutionController(journal, executor)

    record = controller.run(_bundle(), _action(), now="2026-06-23T10:05:00Z")

    states = [transition.state for transition in record.transitions]
    assert record.state is ExecutionState.EXECUTED
    assert states.index(ExecutionState.COMMITTED) < states.index(ExecutionState.EXECUTED)
    assert record.decision_code is CaPUDecisionCode.COMMIT_EXECUTED
    assert record.effect_succeeded is True
    assert executor.execute_calls == 1


def test_hold_produces_no_effect_and_releases_when_mature(tmp_path: Path) -> None:
    fixture = _load("hold.json")
    journal = InMemoryExecutionJournal()
    executor = ReviewResultFileExecutor(tmp_path / "effects")
    controller = DeterministicExecutionController(journal, executor)
    action = ProtectedAction.from_mapping(fixture["action"])
    bundle = _bundle()

    held = controller.run(
        bundle,
        action,
        now=fixture["now"],
        preconditions_met=fixture["preconditions_met"],
    )

    assert held.state.value == fixture["expected_state"]
    assert held.decision_code.value == fixture["expected_code"]
    assert held.effect_attempted is False
    assert executor.execute_calls == 0

    released = controller.recover(
        bundle,
        action,
        now="2026-06-23T10:06:00Z",
        preconditions_met=True,
    )
    assert released.state is ExecutionState.EXECUTED
    assert executor.execute_calls == 1


def test_scope_rejection_produces_no_effect(tmp_path: Path) -> None:
    journal = InMemoryExecutionJournal()
    executor = ReviewResultFileExecutor(tmp_path / "effects")
    controller = DeterministicExecutionController(journal, executor)

    record = controller.run(
        _bundle(),
        _action(scope=("deploy:production",)),
        now="2026-06-23T10:05:00Z",
    )

    assert record.state is ExecutionState.REJECTED
    assert record.decision_code is CaPUDecisionCode.REJECT_POLICY
    assert record.effect_attempted is False
    assert executor.execute_calls == 0


def test_commit_failure_produces_no_effect(tmp_path: Path) -> None:
    fixture = _load("commit_failure.json")
    journal = InMemoryExecutionJournal()
    journal.fail_next_save = fixture["fail_next_save"]
    executor = ReviewResultFileExecutor(tmp_path / "effects")
    controller = DeterministicExecutionController(journal, executor)

    with pytest.raises(DurableCommitError, match=fixture["expected_error"]) as error:
        controller.run(_bundle(), _action(), now=fixture["now"])

    assert error.value.record.state is ExecutionState.REJECTED
    assert error.value.record.decision_code is CaPUDecisionCode.ABORT_INTERNAL_ERROR
    assert error.value.record.effect_attempted is False
    assert executor.execute_calls == fixture["expected_effect_calls"]


def test_retry_after_success_does_not_duplicate_effect(tmp_path: Path) -> None:
    journal = InMemoryExecutionJournal()
    executor = ReviewResultFileExecutor(tmp_path / "effects")
    controller = DeterministicExecutionController(journal, executor)
    bundle = _bundle()
    action = _action()

    first = controller.run(bundle, action, now="2026-06-23T10:05:00Z")
    second = controller.run(bundle, action, now="2026-06-23T10:06:00Z")

    assert first.execution_id == second.execution_id
    assert first.effect_ref == second.effect_ref
    assert executor.execute_calls == 1


def test_recovery_after_commit_completes_one_effect(tmp_path: Path) -> None:
    fixture = _load("interrupted_after_commit.json")
    journal_path = tmp_path / "journal.json"
    effects = tmp_path / "effects"
    bundle = _bundle()
    action = _action()
    first_executor = ReviewResultFileExecutor(effects)
    first = DeterministicExecutionController(
        JsonFileExecutionJournal(journal_path),
        first_executor,
    )

    with pytest.raises(ExecutionInterrupted) as interrupted:
        first.run(
            bundle,
            action,
            now=fixture["now"],
            interrupt_after_commit=True,
        )

    assert interrupted.value.boundary == fixture["boundary"]
    assert interrupted.value.record.state is ExecutionState.COMMITTED
    assert first_executor.execute_calls == 0

    second_executor = ReviewResultFileExecutor(effects)
    second = DeterministicExecutionController(
        JsonFileExecutionJournal(journal_path),
        second_executor,
    )
    recovered = second.recover(
        bundle,
        action,
        now=fixture["recover_at"],
    )

    assert recovered.state.value == fixture["expected_state"]
    assert second_executor.execute_calls == 1
    assert len(list(effects.glob("*.review.json"))) == fixture["expected_effect_files"]


def test_recovery_after_effect_inspects_without_duplicate(tmp_path: Path) -> None:
    fixture = _load("interrupted_after_effect.json")
    journal_path = tmp_path / "journal.json"
    effects = tmp_path / "effects"
    bundle = _bundle()
    action = _action()
    first_executor = ReviewResultFileExecutor(effects)
    first = DeterministicExecutionController(
        JsonFileExecutionJournal(journal_path),
        first_executor,
    )

    with pytest.raises(ExecutionInterrupted) as interrupted:
        first.run(
            bundle,
            action,
            now=fixture["now"],
            interrupt_after_effect=True,
        )

    assert interrupted.value.boundary == fixture["boundary"]
    assert interrupted.value.record.state is ExecutionState.COMMITTED
    assert first_executor.execute_calls == 1

    second_executor = ReviewResultFileExecutor(effects)
    second = DeterministicExecutionController(
        JsonFileExecutionJournal(journal_path),
        second_executor,
    )
    recovered = second.recover(
        bundle,
        action,
        now=fixture["recover_at"],
    )

    assert recovered.state.value == fixture["expected_state"]
    assert recovered.effect_succeeded is True
    assert second_executor.execute_calls == fixture["expected_new_effect_calls"]
    assert len(list(effects.glob("*.review.json"))) == 1


def test_expired_action_never_commits_or_executes(tmp_path: Path) -> None:
    journal = InMemoryExecutionJournal()
    executor = ReviewResultFileExecutor(tmp_path / "effects")
    controller = DeterministicExecutionController(journal, executor)

    record = controller.run(
        _bundle(),
        _action(expires_at="2026-06-23T10:01:00Z"),
        now="2026-06-23T10:02:00Z",
    )

    assert record.state is ExecutionState.EXPIRED
    assert record.decision_code is CaPUDecisionCode.TTL_EXPIRED
    assert all(
        transition.state is not ExecutionState.COMMITTED
        for transition in record.transitions
    )
    assert executor.execute_calls == 0


def test_capu_adapter_is_disabled_by_default(tmp_path: Path) -> None:
    with pytest.raises(ExecutionControlDisabledError):
        CaPUExecutionAdapter().run(
            _bundle(),
            _action(),
            now="2026-06-23T10:05:00Z",
        )

    controller = DeterministicExecutionController(
        InMemoryExecutionJournal(),
        ReviewResultFileExecutor(tmp_path / "effects"),
    )
    enabled = CaPUExecutionAdapter(
        CaPUConfig(enabled=True),
        controller,
    )
    assert enabled.run(
        _bundle(),
        _action(),
        now="2026-06-23T10:05:00Z",
    ).state is ExecutionState.EXECUTED


def test_execution_record_matches_schema(tmp_path: Path) -> None:
    controller = DeterministicExecutionController(
        InMemoryExecutionJournal(),
        ReviewResultFileExecutor(tmp_path / "effects"),
    )
    record = controller.run(
        _bundle(),
        _action(),
        now="2026-06-23T10:05:00Z",
    )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(record.to_dict())) == []


def test_execution_transitions_extend_trail_and_artifact(tmp_path: Path) -> None:
    bundle = _bundle()
    controller = DeterministicExecutionController(
        InMemoryExecutionJournal(),
        ReviewResultFileExecutor(tmp_path / "effects"),
    )
    record = controller.run(
        bundle,
        _action(),
        now="2026-06-23T10:05:00Z",
    )
    root = TrailEvent(
        event_id="event-task-received-capu",
        task_id=bundle.task_id,
        trail_id=bundle.trail_id,
        event_type=TrailEventType.TASK_RECEIVED,
        actor="runtime:ls",
        created_at="2026-06-23T10:00:00Z",
        parent_cause=bundle.task_id,
        evidence_refs=(),
        payload={},
    )
    authorization = TrailEvent(
        event_id="event-authorization-capu",
        task_id=bundle.task_id,
        trail_id=bundle.trail_id,
        event_type=TrailEventType.AUTHORIZATION_ISSUED,
        actor="adapter:proofpath",
        created_at="2026-06-23T10:00:01Z",
        parent_cause=root.event_id,
        evidence_refs=bundle.evidence_refs,
        payload={"authorization_ref": bundle.authorization_ref},
    )
    trail = CognitiveTrail(
        task_id=bundle.task_id,
        trail_id=bundle.trail_id,
        actor="runtime:ls",
        created_at="2026-06-23T10:00:00Z",
        events=(root, authorization),
    )

    extended = append_execution_record(
        trail,
        record,
        parent_event_id=authorization.event_id,
    )

    execution_events = extended.events[2:]
    assert execution_events[0].parent_cause == authorization.event_id
    assert execution_events[-1].event_type is TrailEventType.EXECUTION_COMPLETED
    assert any(
        event.event_type is TrailEventType.EXECUTION_COMMITTED
        for event in execution_events
    )
    assert execution_events[-1].payload["decision_code"] == "COMMIT_EXECUTED"

    artifact = ReusableArtifact(
        artifact_id="artifact-capu-001",
        task_id=bundle.task_id,
        trail_id=bundle.trail_id,
        created_at="2026-06-23T10:06:00Z",
        route_refs=(),
        evidence_refs=bundle.evidence_refs,
        contribution_refs=(),
        decision_ref=bundle.decision_ref,
        execution_ref=None,
        replay_ref=None,
    )
    attached = attach_execution_record(artifact, record)
    assert attached.execution_ref is not None
    assert attached.execution_ref.startswith("execution-record:sha256:")
