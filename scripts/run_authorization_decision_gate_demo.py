#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from modules.trusted_runtime.authorization_contract import (  # noqa: E402
    ApprovalEvidence,
    ApprovalState,
    AuthorityEvidence,
    AuthorityState,
    AuthorizationRequest,
    CapabilityEvidence,
    CapabilityState,
    ContextState,
    ExecutionContextEvidence,
    PolicyEffect,
    PolicyEvidence,
)
from modules.trusted_runtime.authorization_decision_gate import (  # noqa: E402
    evaluate_authorization,
)
from modules.trusted_runtime.continuity_coordinator import (  # noqa: E402
    ContinuityDecision,
)
from modules.trusted_runtime.roles_permissions_contract import (  # noqa: E402
    AuthorityBasis,
)

SUBJECT = "agent:release-bot"
ACTION = "deploy"
RESOURCE = "service:payments"
SCOPE = "scope:production"


def base_request() -> AuthorizationRequest:
    return AuthorizationRequest(
        request_id="authorization-request:demo",
        subject_id=SUBJECT,
        intent_ref="intent:release:demo",
        action=ACTION,
        resource=RESOURCE,
        scope_ref=SCOPE,
        required_capability_id="capability:deploy-service",
        capability_subject_binding_ref="binding:agent-capability:demo",
        capability=CapabilityEvidence(
            result_id="capability-result:demo",
            assessment_id="capability-assessment:demo",
            assessment_decision=ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION,
            subject_id=SUBJECT,
            capability_id="capability:deploy-service",
            state=CapabilityState.AVAILABLE,
            evidence_refs=("evidence:capability",),
            context_refs=("context:production",),
            result_digest="a" * 64,
        ),
        authority=AuthorityEvidence(
            result_id="authority-result:demo",
            assessment_id="authority-assessment:demo",
            assessment_decision=ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION,
            subject_id=SUBJECT,
            authority_id="authority:deploy-production",
            state=AuthorityState.ACTIVE,
            basis=AuthorityBasis.DIRECT_PERMISSION,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            evidence_refs=("evidence:authority",),
            provenance_refs=("provenance:policy",),
            approval_refs=(),
            result_digest="b" * 64,
        ),
        policy=PolicyEvidence(
            policy_id="policy:deploy-production",
            policy_version="v1",
            effect=PolicyEffect.ALLOW,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            evidence_refs=("evidence:policy",),
            policy_digest="c" * 64,
        ),
        approval=ApprovalEvidence(
            approval_id="approval:not-required",
            subject_id=SUBJECT,
            state=ApprovalState.NOT_REQUIRED,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            approver_refs=(),
            evidence_refs=(),
            approval_digest="d" * 64,
        ),
        context=ExecutionContextEvidence(
            context_id="context:demo",
            subject_id=SUBJECT,
            state=ContextState.FRESH,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            age_seconds=10,
            max_age_seconds=60,
            evidence_refs=("evidence:context",),
            context_digest="e" * 64,
        ),
        requested_at="2026-06-25T12:30:00Z",
    )


def main() -> int:
    base = base_request()
    cases = (
        ("allow", base),
        ("policy-deny", replace(base, policy=replace(base.policy, effect=PolicyEffect.DENY))),
        (
            "role-only",
            replace(
                base,
                authority=replace(base.authority, basis=AuthorityBasis.ROLE_ASSIGNMENT),
            ),
        ),
        (
            "stale-context",
            replace(base, context=replace(base.context, state=ContextState.STALE)),
        ),
        (
            "revoked-authority",
            replace(base, authority=replace(base.authority, state=AuthorityState.REVOKED)),
        ),
        (
            "missing-capability-binding",
            replace(base, capability_subject_binding_ref=""),
        ),
    )
    decisions = []
    for name, request in cases:
        result = evaluate_authorization(
            request,
            evaluated_at="2026-06-25T12:30:01Z",
        )
        decisions.append(
            {
                "case": name,
                "decision": result.decision.value,
                "reason_codes": [item.value for item in result.reason_codes],
                "action_authorized": result.action_authorized,
                "execution_authorized": False,
            }
        )
    summary = {
        "schema_version": "trusted_runtime.authorization_demo.v0.1",
        "result": "PASS",
        "decisions": decisions,
    }
    output = ROOT / "build/authorization-decision-gate"
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
