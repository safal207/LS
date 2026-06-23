"""End-to-end Trusted Runtime PR review MVP."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Optional

from .authorization import (
    AuthorizationBundle,
    ProofPathAuthorizationBundleAdapter,
    authorization_bundle_event,
)
from .causal import DeterministicCausalAuditAdapter, causal_audit_event
from .contracts import CognitiveTrail, DecisionCode, ReusableArtifact
from .evidence import (
    DeterministicEvidenceGateAdapter,
    evidence_decision_event,
    evidence_decision_ref,
)
from .execution import (
    DeterministicExecutionController,
    ExecutionRecord,
    ExecutionState,
    JsonFileExecutionJournal,
    ProtectedAction,
    ReviewResultFileExecutor,
    append_execution_record,
    execution_record_ref,
)
from .persistence import (
    JsonlEventStoreAdapter,
    persist_artifact_metadata,
    persist_cognitive_trail,
    trail_event_to_mapping,
)
from .pr_review_analysis import DiffAnalysis, analyze_diff
from .pr_review_artifact import build_pr_review_artifact, pretty_json
from .pr_review_markdown import render_review_markdown
from .pr_review_plan import PlannedPRReview, plan_pr_review
from .replay import replay_checked_event, replay_from_store
from .replay_models import ReplayOutcome


SCENARIOS = {"allow", "hold", "block"}
POLICY_VERSION = "policy.trusted-pr-review.v0.1"
CREATED_AT = "2026-06-23T14:00:00Z"
EXECUTE_AT = "2026-06-23T14:05:00Z"
REPLAY_AT = "2026-06-23T14:10:00Z"
DEFAULT_EXPIRES_AT = "2026-06-23T15:00:00Z"


class PRReviewMVPError(RuntimeError):
    """Raised when the deterministic product slice cannot complete safely."""


def run_trusted_pr_review(
    diff_text: str,
    *,
    scenario: str,
    output_dir: Path,
    authorization_expires_at: str = DEFAULT_EXPIRES_AT,
) -> dict[str, Any]:
    normalized_scenario = scenario.lower().strip()
    if normalized_scenario not in SCENARIOS:
        raise ValueError(
            f"unsupported PR review scenario {scenario!r}; expected one of "
            f"{sorted(SCENARIOS)}"
        )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    analysis = analyze_diff(diff_text)
    planned = plan_pr_review(
        analysis,
        scenario=normalized_scenario,
        created_at=CREATED_AT,
    )
    trail, audit, audit_event_id = _audit_trail(planned)
    decision, decision_event_id = _decide(
        trail,
        audit,
        audit_event_id,
        analysis,
        scenario=normalized_scenario,
    )
    trail = replace(
        trail,
        events=(*trail.events, evidence_decision_event(decision)),
    )

    bundle: Optional[AuthorizationBundle] = None
    execution: Optional[ExecutionRecord] = None
    if decision.decision is DecisionCode.ALLOW:
        bundle, execution, trail = _authorize_and_execute(
            trail,
            decision,
            audit_event_id,
            decision_event_id,
            analysis,
            planned,
            root,
            expires_at=authorization_expires_at,
        )

    store = JsonlEventStoreAdapter(root / "events.jsonl")
    persist_cognitive_trail(store, trail)
    replay = replay_from_store(
        store,
        trail.trail_id,
        now=REPLAY_AT,
    )
    replay_event = replay_checked_event(
        replay,
        parent_event_id=trail.events[-1].event_id,
    )
    store.append(trail_event_to_mapping(replay_event))
    trail = replace(trail, events=(*trail.events, replay_event))

    protected_files = tuple(sorted((root / "protected").glob("*.review.json")))
    protected_effect_written = bool(protected_files)
    artifact_payload: Optional[dict[str, Any]] = None
    artifact_path: Optional[Path] = None
    reusable_artifact: Optional[ReusableArtifact] = None

    if decision.decision is DecisionCode.ALLOW:
        if bundle is None or execution is None:
            raise PRReviewMVPError("ALLOW reached artifact creation without execution")
        if execution.state is not ExecutionState.EXECUTED:
            raise PRReviewMVPError(
                f"ALLOW execution did not complete: {execution.state.value}"
            )
        if not protected_effect_written:
            raise PRReviewMVPError("executed review has no protected effect file")

        reusable_artifact = ReusableArtifact(
            artifact_id=f"artifact-trusted-pr-review-{normalized_scenario}",
            task_id=trail.task_id,
            trail_id=trail.trail_id,
            created_at=REPLAY_AT,
            route_refs=tuple(route.route_id for route in planned.routes),
            evidence_refs=analysis.evidence_refs,
            contribution_refs=tuple(
                str(item["contribution_ref"])
                for item in planned.contributions
            ),
            decision_ref=evidence_decision_ref(decision),
            execution_ref=execution_record_ref(execution),
            replay_ref=replay.report_ref,
        )
        artifact_payload = build_pr_review_artifact(
            scenario=normalized_scenario,
            created_at=REPLAY_AT,
            analysis=analysis,
            plan=planned.plan,
            routes=planned.routes,
            contributions=planned.contributions,
            causal_audit=audit,
            evidence_decision=decision,
            decision_ref=evidence_decision_ref(decision),
            authorization=bundle,
            execution=execution,
            replay=replay,
            reusable_artifact=reusable_artifact,
        )
        artifact_path = root / "artifact.json"
        artifact_path.write_text(pretty_json(artifact_payload), encoding="utf-8")
        persist_artifact_metadata(
            store,
            reusable_artifact,
            actor="runtime:ls",
            parent_event_id=replay_event.event_id,
        )
        _write_bundle(root / "proofpath", bundle.to_files())

    _write_bundle(root / "replay", replay.export_files())
    _write_json(root / "workflow-plan.json", planned.plan.to_dict())
    _write_json(root / "causal-audit.json", audit.to_dict())
    _write_json(
        root / "evidence-decision.json",
        {
            **decision.to_dict(),
            "decision_ref": evidence_decision_ref(decision),
        },
    )
    review_markdown = render_review_markdown(
        scenario=normalized_scenario,
        analysis=analysis,
        decision=decision,
        causal_audit=audit,
        routes=planned.routes,
        contributions=planned.contributions,
        protected_effect_written=protected_effect_written,
        replay_decision=replay.record.decision.value,
        artifact=artifact_payload,
    )
    (root / "review.md").write_text(review_markdown, encoding="utf-8")

    result = {
        "scenario": normalized_scenario,
        "task_id": trail.task_id,
        "trail_id": trail.trail_id,
        "decision": decision.decision.value,
        "decision_reason": decision.reason,
        "causal_authorization_allowed": audit.authorization_allowed,
        "authorization_created": bundle is not None,
        "execution_state": execution.state.value if execution is not None else None,
        "protected_effect_written": protected_effect_written,
        "protected_effect_files": [str(path) for path in protected_files],
        "replay_decision": replay.record.decision.value,
        "replay_ref": replay.report_ref,
        "artifact_written": artifact_path is not None,
        "artifact_path": str(artifact_path) if artifact_path is not None else None,
        "event_store_path": str(store.path),
        "review_path": str(root / "review.md"),
    }
    _write_json(root / "run-summary.json", result)
    return result


def _audit_trail(
    planned: PlannedPRReview,
) -> tuple[CognitiveTrail, Any, str]:
    report = DeterministicCausalAuditAdapter().audit(planned.trail)
    event = causal_audit_event(
        report,
        parent_cause=planned.trail.events[-1].event_id,
    )
    trail = replace(planned.trail, events=(*planned.trail.events, event))
    return trail, report, event.event_id


def _decide(
    trail: CognitiveTrail,
    audit: Any,
    audit_event_id: str,
    analysis: DiffAnalysis,
    *,
    scenario: str,
):
    missing_evidence = (
        ("evidence:required-changed-tests",)
        if scenario == "hold"
        else ()
    )
    risk_flags = analysis.risk_flags if scenario == "block" else ()
    if scenario == "block" and not risk_flags:
        risk_flags = ("policy_block_requested",)
    request = {
        "request_id": f"evidence-request-pr-review-{scenario}",
        "task_id": trail.task_id,
        "trail_id": trail.trail_id,
        "actor": "human:review-owner",
        "intent_ref": f"intent:trusted-pr-review:{scenario}",
        "scope": ["artifact:write"],
        "evidence_refs": list(analysis.evidence_refs),
        "policy_version": POLICY_VERSION,
        "causal_audit_ref": audit_event_id,
        "causal_authorization_allowed": audit.authorization_allowed,
        "created_at": CREATED_AT,
        "artifact_digest": analysis.analysis_digest,
        "artifact_verified": True,
        "missing_evidence_refs": list(missing_evidence),
        "risk_flags": list(risk_flags),
        "escalation_reasons": [],
        "metadata": {"product_slice": "trusted-pr-review-mvp"},
    }
    decision = DeterministicEvidenceGateAdapter().decide(request)
    event = evidence_decision_event(decision)
    return decision, event.event_id


def _authorize_and_execute(
    trail: CognitiveTrail,
    decision: Any,
    audit_event_id: str,
    decision_event_id: str,
    analysis: DiffAnalysis,
    planned: PlannedPRReview,
    root: Path,
    *,
    expires_at: str,
) -> tuple[AuthorizationBundle, ExecutionRecord, CognitiveTrail]:
    intent = {
        "intent_id": "intent:trusted-pr-review:allow",
        "task_id": trail.task_id,
        "trail_id": trail.trail_id,
        "actor": "human:review-owner",
        "action_ref": "artifact:write:trusted-pr-review",
        "scope": ["artifact:write"],
        "issued_at": CREATED_AT,
        "expires_at": expires_at,
        "nonce": "nonce-trusted-pr-review-allow",
        "policy_version": POLICY_VERSION,
        "evidence_refs": list(analysis.evidence_refs),
        "evidence_digest": analysis.analysis_digest,
        "causal_audit_refs": [audit_event_id],
        "parent_cause": audit_event_id,
        "metadata": {"product_slice": "trusted-pr-review-mvp"},
    }
    bundle = ProofPathAuthorizationBundleAdapter().build(decision, intent)
    authorization_event = authorization_bundle_event(bundle)
    if authorization_event.parent_cause != decision_event_id:
        raise PRReviewMVPError(
            "authorization event is not descended from the evidence decision"
        )
    trail = replace(trail, events=(*trail.events, authorization_event))

    action = ProtectedAction(
        action_id="action-write-trusted-pr-review",
        action_ref="artifact:write:trusted-pr-review",
        scope=("artifact:write",),
        payload={
            "status": "approved",
            "summary": analysis.summary,
            "findings": list(analysis.findings),
            "route_refs": [route.route_id for route in planned.routes],
            "contribution_refs": [
                item["contribution_ref"] for item in planned.contributions
            ],
            "evidence_refs": list(analysis.evidence_refs),
        },
        idempotency_key="trusted-pr-review-allow",
        requested_at=CREATED_AT,
        expires_at=expires_at,
        metadata={"product_slice": "trusted-pr-review-mvp"},
    )
    controller = DeterministicExecutionController(
        JsonFileExecutionJournal(root / "execution-journal.json"),
        ReviewResultFileExecutor(root / "protected"),
    )
    execution = controller.run(bundle, action, now=EXECUTE_AT)
    trail = append_execution_record(
        trail,
        execution,
        parent_event_id=authorization_event.event_id,
    )
    return bundle, execution, trail


def _write_bundle(root: Path, files: Mapping[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
