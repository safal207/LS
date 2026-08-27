from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
    UseTimeReceipt,
    UseTimeVerdict,
    UseTokenRegistry,
    evaluate_transition,
    revalidate_authorization_for_use,
    verify_executed_outcome,
)


@dataclass(frozen=True)
class DeploymentDemoResult:
    deploy_authorization: AuthorizationReceipt
    deploy_use: UseTimeReceipt
    deploy_outcome: OutcomeReceipt | None
    rollback_authorization: AuthorizationReceipt | None
    rollback_use: UseTimeReceipt | None
    rollback_outcome: OutcomeReceipt | None
    final_state: str
    execution_performed: bool
    rollback_execution_performed: bool
    ledger_valid: bool
    ledger_head: str


def run_deployment_demo(
    *,
    fail_health: bool,
    drift_before_execute: bool = False,
    now_ms: int = 1_800_000_000_000,
    previous_sha: str = "a" * 40,
    candidate_sha: str = "b" * 40,
) -> DeploymentDemoResult:
    """Run a deterministic, side-effect-free deployment transition demo."""
    ledger = EvidenceLedger()
    use_registry = UseTokenRegistry()

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
        source_ref=f"git:{candidate_sha}",
        policy_ref="policy:production-deploy-v1",
        approval_ref="approval:deploy-001",
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

    current_evidence = evidence
    if drift_before_execute:
        current_evidence = replace(
            evidence,
            policy_ref="policy:production-deploy-v2",
        )

    deploy_use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=deploy_auth,
        current_evidence=current_evidence,
        executor_id="deployment-executor",
        now_ms=now_ms + 1_000,
        execution_nonce="deploy-occurrence-001",
    )
    ledger.append("use_time_receipt", asdict(deploy_use))

    execution_performed = use_registry.consume(deploy_use)
    ledger.append(
        "execution_permit_consumption",
        {
            "use_id": deploy_use.use_id,
            "accepted": execution_performed,
            "simulated": True,
        },
    )

    if not execution_performed:
        records = ledger.records
        return DeploymentDemoResult(
            deploy_authorization=deploy_auth,
            deploy_use=deploy_use,
            deploy_outcome=None,
            rollback_authorization=None,
            rollback_use=None,
            rollback_outcome=None,
            final_state=proposal.pre_state,
            execution_performed=False,
            rollback_execution_performed=False,
            ledger_valid=EvidenceLedger.verify(records),
            ledger_head=records[-1].record_hash,
        )

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
    deploy_outcome = verify_executed_outcome(
        proposal=proposal,
        authorization=deploy_auth,
        use_receipt=deploy_use,
        outcome=observed,
        verifier_id="post-action-verifier",
    )
    ledger.append("observed_outcome", asdict(observed))
    ledger.append("outcome_receipt", asdict(deploy_outcome))

    rollback_auth: AuthorizationReceipt | None = None
    rollback_use: UseTimeReceipt | None = None
    rollback_outcome: OutcomeReceipt | None = None
    rollback_execution_performed = False
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
            source_ref=f"git:{previous_sha}",
            policy_ref="policy:auto-rollback-v1",
            approval_ref=f"approval:auto-rollback:{deploy_outcome.outcome_id}",
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

        rollback_use = revalidate_authorization_for_use(
            proposal=rollback_proposal,
            authorization=rollback_auth,
            current_evidence=rollback_evidence,
            executor_id="rollback-executor",
            now_ms=now_ms + 2_000,
            execution_nonce="rollback-occurrence-001",
        )
        ledger.append("recovery_use_time_receipt", asdict(rollback_use))
        rollback_execution_performed = use_registry.consume(rollback_use)
        ledger.append(
            "recovery_execution_permit_consumption",
            {
                "use_id": rollback_use.use_id,
                "accepted": rollback_execution_performed,
                "simulated": True,
            },
        )

        if not rollback_execution_performed:
            raise RuntimeError("reference rollback use-time revalidation must execute")

        recovered = ObservedOutcome(
            transition_id=rollback_proposal.transition_id,
            observed_post_state=f"production:{previous_sha}",
            invariant_results=(
                ("commit_restored", True),
                ("health_ok", True),
            ),
            rollback_available=False,
        )
        rollback_outcome = verify_executed_outcome(
            proposal=rollback_proposal,
            authorization=rollback_auth,
            use_receipt=rollback_use,
            outcome=recovered,
            verifier_id="recovery-outcome-verifier",
        )
        ledger.append("recovery_observed_outcome", asdict(recovered))
        ledger.append("recovery_outcome_receipt", asdict(rollback_outcome))
        final_state = recovered.observed_post_state

    records = ledger.records
    return DeploymentDemoResult(
        deploy_authorization=deploy_auth,
        deploy_use=deploy_use,
        deploy_outcome=deploy_outcome,
        rollback_authorization=rollback_auth,
        rollback_use=rollback_use,
        rollback_outcome=rollback_outcome,
        final_state=final_state,
        execution_performed=execution_performed,
        rollback_execution_performed=rollback_execution_performed,
        ledger_valid=EvidenceLedger.verify(records),
        ledger_head=records[-1].record_hash,
    )


def main() -> None:
    healthy = run_deployment_demo(fail_health=False)
    failing = run_deployment_demo(fail_health=True)
    drifted = run_deployment_demo(fail_health=False, drift_before_execute=True)
    print(
        json.dumps(
            {
                "healthy": {
                    "use_time": healthy.deploy_use.verdict.value,
                    "deploy": healthy.deploy_outcome.verdict.value if healthy.deploy_outcome else None,
                    "final_state": healthy.final_state,
                    "ledger_valid": healthy.ledger_valid,
                    "ledger_head": healthy.ledger_head,
                },
                "health_failure": {
                    "use_time": failing.deploy_use.verdict.value,
                    "deploy": failing.deploy_outcome.verdict.value if failing.deploy_outcome else None,
                    "rollback_use_time": (
                        failing.rollback_use.verdict.value
                        if failing.rollback_use
                        else None
                    ),
                    "rollback": (
                        failing.rollback_outcome.verdict.value
                        if failing.rollback_outcome
                        else None
                    ),
                    "final_state": failing.final_state,
                    "ledger_valid": failing.ledger_valid,
                    "ledger_head": failing.ledger_head,
                },
                "pre_execute_drift": {
                    "use_time": drifted.deploy_use.verdict.value,
                    "execution_performed": drifted.execution_performed,
                    "deploy": None,
                    "final_state": drifted.final_state,
                    "ledger_valid": drifted.ledger_valid,
                    "ledger_head": drifted.ledger_head,
                },
                "external_side_effects_performed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
