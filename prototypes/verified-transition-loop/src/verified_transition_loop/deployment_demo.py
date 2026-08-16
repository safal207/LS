from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from .core import (
    AuthorizationReceipt,
    EvidenceBundle,
    EvidenceLedger,
    ObservedOutcome,
    OutcomeReceipt,
    OutcomeVerdict,
    TransitionIntent,
    TransitionProposal,
    TransitionVerdict,
    evaluate_transition,
    verify_authorized_outcome,
)


@dataclass(frozen=True)
class DeploymentDemoResult:
    deploy_authorization: AuthorizationReceipt
    deploy_outcome: OutcomeReceipt
    rollback_authorization: AuthorizationReceipt | None
    rollback_outcome: OutcomeReceipt | None
    final_state: str
    ledger_valid: bool
    ledger_head: str


def run_deployment_demo(
    *,
    fail_health: bool,
    now_ms: int = 1_800_000_000_000,
    previous_sha: str = "a" * 40,
    candidate_sha: str = "b" * 40,
) -> DeploymentDemoResult:
    """Run a deterministic, side-effect-free deployment transition demo."""
    ledger = EvidenceLedger()

    deploy_action = f"deploy:{candidate_sha}"
    intent = TransitionIntent(
        intent_id="intent-deploy-001",
        actor="ai-coding-agent",
        action=deploy_action,
        purpose="publish the reviewed candidate commit",
    )
    proposal = TransitionProposal(
        transition_id="transition-deploy-001",
        intent_id=intent.intent_id,
        pre_state=f"production:{previous_sha}",
        action=deploy_action,
        expected_post_state=f"production:{candidate_sha}",
        invariants=("commit_matches", "artifact_matches", "health_ok"),
    )
    evidence = EvidenceBundle(
        mission_aligned=True,
        exact_source_bound=True,
        tests_passed=True,
        approval_current=True,
        approval_valid_until_ms=now_ms + 60_000,
        evidence_refs=(
            f"git:{candidate_sha}",
            "tests:green",
            "approval:deploy-001",
            "artifact:sha256-demo",
        ),
    )
    deploy_auth = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=evidence,
        verifier_id="pre-action-verifier",
        executor_id="deployment-executor",
        now_ms=now_ms,
    )
    ledger.append("transition_intent", asdict(intent))
    ledger.append("transition_proposal", asdict(proposal))
    ledger.append("authorization_receipt", asdict(deploy_auth))

    if deploy_auth.verdict is not TransitionVerdict.AUTHORIZE:
        raise RuntimeError("reference deployment scenario must authorize")

    observed = ObservedOutcome(
        transition_id=proposal.transition_id,
        observed_post_state=f"production:{candidate_sha}",
        invariant_results=(
            ("commit_matches", True),
            ("artifact_matches", True),
            ("health_ok", not fail_health),
        ),
        rollback_available=True,
    )
    deploy_outcome = verify_authorized_outcome(
        proposal=proposal,
        authorization=deploy_auth,
        outcome=observed,
        verifier_id="post-action-verifier",
    )
    ledger.append("observed_outcome", asdict(observed))
    ledger.append("outcome_receipt", asdict(deploy_outcome))

    rollback_auth: AuthorizationReceipt | None = None
    rollback_outcome: OutcomeReceipt | None = None
    final_state = observed.observed_post_state

    if deploy_outcome.verdict is OutcomeVerdict.ROLLBACK:
        rollback_action = f"rollback:{candidate_sha}->{previous_sha}"
        rollback_intent = TransitionIntent(
            intent_id="intent-rollback-001",
            actor="vtl-recovery-controller",
            action=rollback_action,
            purpose="restore the last verified production state",
        )
        rollback_proposal = TransitionProposal(
            transition_id="transition-rollback-001",
            intent_id=rollback_intent.intent_id,
            pre_state=f"production:{candidate_sha}",
            action=rollback_action,
            expected_post_state=f"production:{previous_sha}",
            invariants=("commit_restored", "health_ok"),
        )
        rollback_evidence = EvidenceBundle(
            mission_aligned=True,
            exact_source_bound=True,
            tests_passed=True,
            approval_current=True,
            approval_valid_until_ms=now_ms + 60_000,
            evidence_refs=(
                "policy:auto-rollback-on-health-failure",
                f"last-verified:{previous_sha}",
                f"failed-transition:{deploy_outcome.outcome_id}",
            ),
        )
        rollback_auth = evaluate_transition(
            intent=rollback_intent,
            proposal=rollback_proposal,
            evidence=rollback_evidence,
            verifier_id="recovery-policy-verifier",
            executor_id="rollback-executor",
            now_ms=now_ms,
        )
        ledger.append("recovery_intent", asdict(rollback_intent))
        ledger.append("recovery_proposal", asdict(rollback_proposal))
        ledger.append("recovery_authorization_receipt", asdict(rollback_auth))

        if rollback_auth.verdict is not TransitionVerdict.AUTHORIZE:
            raise RuntimeError("reference rollback scenario must authorize")

        recovered = ObservedOutcome(
            transition_id=rollback_proposal.transition_id,
            observed_post_state=f"production:{previous_sha}",
            invariant_results=(
                ("commit_restored", True),
                ("health_ok", True),
            ),
            rollback_available=False,
        )
        rollback_outcome = verify_authorized_outcome(
            proposal=rollback_proposal,
            authorization=rollback_auth,
            outcome=recovered,
            verifier_id="recovery-outcome-verifier",
        )
        ledger.append("recovery_observed_outcome", asdict(recovered))
        ledger.append("recovery_outcome_receipt", asdict(rollback_outcome))
        final_state = recovered.observed_post_state

    records = ledger.records
    return DeploymentDemoResult(
        deploy_authorization=deploy_auth,
        deploy_outcome=deploy_outcome,
        rollback_authorization=rollback_auth,
        rollback_outcome=rollback_outcome,
        final_state=final_state,
        ledger_valid=EvidenceLedger.verify(records),
        ledger_head=records[-1].record_hash,
    )


def main() -> None:
    healthy = run_deployment_demo(fail_health=False)
    failing = run_deployment_demo(fail_health=True)
    print(
        json.dumps(
            {
                "healthy": {
                    "deploy": healthy.deploy_outcome.verdict.value,
                    "final_state": healthy.final_state,
                    "ledger_valid": healthy.ledger_valid,
                    "ledger_head": healthy.ledger_head,
                },
                "health_failure": {
                    "deploy": failing.deploy_outcome.verdict.value,
                    "rollback": (
                        failing.rollback_outcome.verdict.value
                        if failing.rollback_outcome
                        else None
                    ),
                    "final_state": failing.final_state,
                    "ledger_valid": failing.ledger_valid,
                    "ledger_head": failing.ledger_head,
                },
                "side_effects_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
