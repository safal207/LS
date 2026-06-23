from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .contracts import (
    CognitiveTrail,
    RoleAssignment,
    RouteDecision,
    TaskEnvelope,
    TrailEvent,
    TrailEventType,
    WorkflowPlan,
    WorkflowStep,
)
from .pr_review_analysis import DiffAnalysis, build_contributions
from .routing import (
    BackendCandidate,
    DeterministicRoutingAdapter,
    route_decision_event,
)


@dataclass(frozen=True)
class PlannedPRReview:
    plan: WorkflowPlan
    routes: tuple[RouteDecision, ...]
    contributions: tuple[dict[str, Any], ...]
    trail: CognitiveTrail


ROLE_SPECS = (
    ("reviewer", "code_review", "Review correctness and maintainability."),
    ("risk_critic", "risk_critique", "Challenge risk and unsafe assumptions."),
    ("verifier", "evidence_verification", "Verify tests and evidence links."),
)


def plan_pr_review(
    analysis: DiffAnalysis,
    *,
    scenario: str,
    created_at: str,
) -> PlannedPRReview:
    task_id = f"task-trusted-pr-review-{scenario}"
    trail_id = f"trail-trusted-pr-review-{scenario}"
    task = TaskEnvelope(
        task_id=task_id,
        trail_id=trail_id,
        intent=f"Review a git diff under the Trusted Runtime {scenario.upper()} scenario.",
        actor="human:review-owner",
        created_at=created_at,
        evidence_refs=(analysis.evidence_refs[0],),
        metadata={
            "product_slice": "trusted-pr-review-mvp",
            "scenario": scenario,
            "diff_digest": analysis.diff_digest,
        },
    )
    roles = tuple(
        RoleAssignment(
            role_id=role_id,
            capability=capability,
            actor=f"local:{role_id}",
            parent_cause=task_id,
        )
        for role_id, capability, _ in ROLE_SPECS
    )
    steps: list[WorkflowStep] = []
    previous: str | None = None
    for index, (role_id, _, action) in enumerate(ROLE_SPECS, start=1):
        step_id = f"step-{index:02d}-{role_id}"
        steps.append(
            WorkflowStep(
                step_id=step_id,
                role_id=role_id,
                action=action,
                parent_cause=previous or task_id,
                depends_on=(previous,) if previous else (),
                evidence_refs=(analysis.evidence_refs[0],) if index == 1 else (),
            )
        )
        previous = step_id
    plan = WorkflowPlan(task=task, roles=roles, steps=tuple(steps))

    received = TrailEvent(
        event_id="event-pr-review-task-received",
        task_id=task_id,
        trail_id=trail_id,
        event_type=TrailEventType.TASK_RECEIVED,
        actor=task.actor,
        created_at=created_at,
        parent_cause=task_id,
        evidence_refs=task.evidence_refs,
        payload={
            "intent": task.intent,
            "scenario": scenario,
            "diff_digest": analysis.diff_digest,
        },
    )
    created = TrailEvent(
        event_id="event-pr-review-plan-created",
        task_id=task_id,
        trail_id=trail_id,
        event_type=TrailEventType.PLAN_CREATED,
        actor="planner:trusted-pr-review",
        created_at=created_at,
        parent_cause=received.event_id,
        evidence_refs=task.evidence_refs,
        payload={
            "role_ids": [role.role_id for role in roles],
            "step_ids": [step.step_id for step in steps],
        },
    )
    trail = CognitiveTrail(
        task_id=task_id,
        trail_id=trail_id,
        actor="runtime:ls",
        created_at=created_at,
        events=(received, created),
    )

    router = DeterministicRoutingAdapter(
        (
            BackendCandidate(
                backend_id="backend:local-reviewer",
                capabilities=("code_review",),
                latency_ms=15.0,
                reliability=0.99,
                load=0.10,
                privacy="local",
            ),
            BackendCandidate(
                backend_id="backend:local-risk-critic",
                capabilities=("risk_critique",),
                latency_ms=18.0,
                reliability=0.99,
                load=0.12,
                privacy="local",
            ),
            BackendCandidate(
                backend_id="backend:local-verifier",
                capabilities=("evidence_verification",),
                latency_ms=12.0,
                reliability=0.995,
                load=0.08,
                privacy="local",
            ),
            BackendCandidate(
                backend_id="backend:local-fallback",
                capabilities=(
                    "code_review",
                    "risk_critique",
                    "evidence_verification",
                ),
                latency_ms=40.0,
                reliability=0.97,
                load=0.25,
                privacy="local",
                fallback=True,
            ),
        ),
        adapter_name="dao-lim-local-reference",
    )
    routes: list[RouteDecision] = []
    parent = trail.events[-1].event_id
    for role in roles:
        route = router.route(
            {
                "route_id": f"route-pr-review-{role.role_id}",
                "task_id": task_id,
                "trail_id": trail_id,
                "role_id": role.role_id,
                "capability": role.capability,
                "actor": "adapter:dao-lim-local-reference",
                "created_at": created_at,
                "parent_cause": parent,
                "constraints": {
                    "required_privacy": "local",
                    "min_reliability": 0.95,
                    "max_load": 0.80,
                    "allow_fallback": True,
                },
            }
        )
        event = route_decision_event(
            route,
            event_id=f"event-route-{role.role_id}",
            parent_cause=parent,
        )
        routes.append(route)
        trail = replace(trail, events=(*trail.events, event))
        parent = event.event_id

    contributions = build_contributions(analysis)
    route_by_role = {route.role_id: route for route in routes}
    for contribution in contributions:
        role_id = str(contribution["role_id"])
        event = TrailEvent(
            event_id=f"event-work-{role_id}",
            task_id=task_id,
            trail_id=trail_id,
            event_type=TrailEventType.WORK_COMPLETED,
            actor=route_by_role[role_id].selected_backend,
            created_at=created_at,
            parent_cause=parent,
            evidence_refs=analysis.evidence_refs,
            payload={
                "role_id": role_id,
                "route_id": route_by_role[role_id].route_id,
                "contribution_ref": contribution["contribution_ref"],
                "artifact_digest": analysis.analysis_digest,
                "summary": contribution["summary"],
            },
        )
        trail = replace(trail, events=(*trail.events, event))
        parent = event.event_id

    return PlannedPRReview(
        plan=plan,
        routes=tuple(routes),
        contributions=contributions,
        trail=trail,
    )
