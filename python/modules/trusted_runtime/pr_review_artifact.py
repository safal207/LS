"""Trusted PR review artifact rendering."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .authorization import AuthorizationBundle
from .causal import CausalAuditReport
from .contracts import EvidenceDecision, ReusableArtifact, RouteDecision, WorkflowPlan
from .execution import ExecutionRecord
from .pr_review_analysis import DiffAnalysis, canonical_json
from .replay_models import ReplayOutcome


PR_REVIEW_ARTIFACT_VERSION = "trusted_runtime.pr_review_artifact.v0.1"


def build_pr_review_artifact(
    *,
    scenario: str,
    created_at: str,
    analysis: DiffAnalysis,
    plan: WorkflowPlan,
    routes: Sequence[RouteDecision],
    contributions: Sequence[Mapping[str, Any]],
    causal_audit: CausalAuditReport,
    evidence_decision: EvidenceDecision,
    decision_ref: str,
    authorization: AuthorizationBundle,
    execution: ExecutionRecord,
    replay: ReplayOutcome,
    reusable_artifact: ReusableArtifact,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": PR_REVIEW_ARTIFACT_VERSION,
        "scenario": scenario.upper(),
        "task_id": reusable_artifact.task_id,
        "trail_id": reusable_artifact.trail_id,
        "created_at": created_at,
        "source_diff": analysis.to_dict(),
        "summary": {
            "decision": evidence_decision.decision.value,
            "reason": evidence_decision.reason,
            "review": analysis.summary,
            "findings": list(analysis.findings),
        },
        "workflow_plan": plan.to_dict(),
        "routes": [route.to_dict() for route in routes],
        "contributions": [dict(item) for item in contributions],
        "causal_audit": causal_audit.to_dict(),
        "evidence_decision": {
            **evidence_decision.to_dict(),
            "decision_ref": decision_ref,
        },
        "authorization": authorization.to_dict(),
        "execution": execution.to_dict(),
        "replay": {
            "record": replay.record.to_dict(),
            "report": replay.report.to_dict(),
            "checkpoint": replay.checkpoint.to_dict(),
        },
        "reusable_artifact": reusable_artifact.to_dict(),
    }
    payload["integrity"] = {
        "algorithm": "sha256",
        "artifact_digest": hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest(),
    }
    return payload


def pretty_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
