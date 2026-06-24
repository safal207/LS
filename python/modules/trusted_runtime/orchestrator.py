from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, Sequence

from .contracts import (
    CognitiveTrail,
    RoleAssignment,
    TaskEnvelope,
    TrailEvent,
    TrailEventType,
    WorkflowPlan,
    WorkflowStep,
)


JsonObject = Mapping[str, Any]

ROLE_CAPABILITIES: Mapping[str, str] = {
    "researcher": "research",
    "implementer": "implementation",
    "critic": "risk_critique",
    "verifier": "evidence_verification",
    "summarizer": "summarization",
}

ROLE_ACTIONS: Mapping[str, str] = {
    "researcher": "Research evidence and constraints for: {intent}",
    "implementer": "Implement a bounded solution for: {intent}",
    "critic": "Critique risks, assumptions, and failure modes for: {intent}",
    "verifier": "Verify evidence and acceptance criteria for: {intent}",
    "summarizer": "Summarize findings and the recommended decision for: {intent}",
}


class OrchestrationDepthError(RuntimeError):
    """Raised when recursive plan revision exceeds the configured limit."""


@dataclass(frozen=True)
class OrchestratorConfig:
    max_depth: int = 2
    max_steps: int = 8
    default_roles: tuple[str, ...] = (
        "researcher",
        "implementer",
        "critic",
        "verifier",
        "summarizer",
    )
    actor: str = "orchestrator:local-deterministic"

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least one")
        if not self.actor:
            raise ValueError("actor must not be empty")
        unknown = set(self.default_roles) - set(ROLE_CAPABILITIES)
        if unknown:
            raise ValueError(f"unknown default roles: {sorted(unknown)}")


class DeterministicWorkflowOrchestrator:
    """Local provider-neutral reference planner with bounded recursion.

    The implementation performs no model calls. Identical task and context
    inputs produce identical workflow plans and trail events.
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None) -> None:
        self.config = config or OrchestratorConfig()
        self._events_by_trail: dict[str, tuple[TrailEvent, ...]] = {}

    @property
    def adapter_name(self) -> str:
        return "local-deterministic"

    def create_plan(self, task: JsonObject, context: JsonObject) -> WorkflowPlan:
        envelope = self._task_envelope(task, depth=0)
        role_ids = self._requested_roles(context)
        roles = self._role_assignments(
            envelope,
            role_ids,
            self._available_capabilities(context),
        )
        steps = self._steps(envelope, role_ids, context)
        plan = WorkflowPlan(task=envelope, roles=roles, steps=steps)
        self._events_by_trail[envelope.trail_id] = self._initial_events(plan)
        return plan

    def assign_roles(
        self,
        plan: WorkflowPlan,
        available_capabilities: Mapping[str, str],
    ) -> WorkflowPlan:
        roles = tuple(
            replace(
                role,
                actor=self._actor_for_role(
                    role.role_id,
                    role.capability,
                    available_capabilities,
                    fallback=role.actor,
                ),
            )
            for role in plan.roles
        )
        return replace(plan, roles=roles)

    def revise_plan(
        self,
        plan: WorkflowPlan,
        results: Sequence[JsonObject],
        reason: str,
    ) -> WorkflowPlan:
        if not reason.strip():
            raise ValueError("revision reason must not be empty")

        current_depth = self._depth(plan)
        if current_depth >= self.config.max_depth:
            raise OrchestrationDepthError(
                f"revision depth {current_depth} reached configured limit "
                f"{self.config.max_depth}"
            )

        next_depth = current_depth + 1
        role_id = self._revision_role(plan)
        parent_step = plan.steps[-1].step_id
        evidence_refs = self._result_evidence(results)
        revision_step = WorkflowStep(
            step_id=f"revision-{next_depth:02d}-{role_id}",
            role_id=role_id,
            action=f"Revise plan at depth {next_depth}: {reason.strip()}",
            parent_cause=parent_step,
            depends_on=(parent_step,),
            evidence_refs=evidence_refs,
        )

        metadata = dict(plan.task.metadata)
        metadata["orchestration_depth"] = next_depth
        revised_task = replace(plan.task, metadata=metadata)
        revised_plan = replace(
            plan,
            task=revised_task,
            steps=plan.steps + (revision_step,),
        )
        self._record_revision(revised_plan, results, reason.strip(), revision_step)
        return revised_plan

    def revision_trail(self, plan: WorkflowPlan) -> CognitiveTrail:
        events = self._events_by_trail.get(plan.task.trail_id)
        if events is None:
            events = self._initial_events(plan)
            self._events_by_trail[plan.task.trail_id] = events

        return CognitiveTrail(
            task_id=plan.task.task_id,
            trail_id=plan.task.trail_id,
            actor=self.config.actor,
            created_at=plan.task.created_at,
            events=events,
        )

    def recorded_events(self, trail_id: str) -> tuple[TrailEvent, ...]:
        return self._events_by_trail.get(trail_id, ())

    def _task_envelope(self, task: JsonObject, depth: int) -> TaskEnvelope:
        metadata = dict(task.get("metadata", {}))
        metadata["orchestration_depth"] = depth
        metadata["orchestrator"] = self.adapter_name
        return TaskEnvelope(
            task_id=str(task["task_id"]),
            trail_id=str(task["trail_id"]),
            intent=str(task["intent"]),
            actor=str(task["actor"]),
            created_at=str(task["created_at"]),
            evidence_refs=tuple(str(ref) for ref in task.get("evidence_refs", ())),
            metadata=metadata,
        )

    def _requested_roles(self, context: JsonObject) -> tuple[str, ...]:
        explicit_roles = context.get("roles")
        if explicit_roles is not None:
            roles = self._unique_strings(explicit_roles)
        elif context.get("workflow") in {"multi-role", "recursive"}:
            roles = self.config.default_roles
        else:
            roles = ("summarizer",)

        unknown = set(roles) - set(ROLE_CAPABILITIES)
        if unknown:
            raise ValueError(f"unknown workflow roles: {sorted(unknown)}")
        if not roles:
            raise ValueError("workflow requires at least one role")
        return roles

    def _available_capabilities(self, context: JsonObject) -> Mapping[str, str]:
        available = context.get("available_capabilities", {})
        if not isinstance(available, Mapping):
            raise TypeError("available_capabilities must be a mapping")
        return {str(key): str(value) for key, value in available.items()}

    def _role_assignments(
        self,
        task: TaskEnvelope,
        role_ids: tuple[str, ...],
        available_capabilities: Mapping[str, str],
    ) -> tuple[RoleAssignment, ...]:
        assignments = []
        for role_id in role_ids:
            capability = ROLE_CAPABILITIES[role_id]
            actor = self._actor_for_role(
                role_id,
                capability,
                available_capabilities,
                fallback=f"local:{role_id}",
            )
            assignments.append(
                RoleAssignment(
                    role_id=role_id,
                    capability=capability,
                    actor=actor,
                    parent_cause=task.task_id,
                )
            )
        return tuple(assignments)

    @staticmethod
    def _actor_for_role(
        role_id: str,
        capability: str,
        available_capabilities: Mapping[str, str],
        fallback: str,
    ) -> str:
        return available_capabilities.get(
            role_id,
            available_capabilities.get(capability, fallback),
        )

    def _steps(
        self,
        task: TaskEnvelope,
        role_ids: tuple[str, ...],
        context: JsonObject,
    ) -> tuple[WorkflowStep, ...]:
        subtasks = context.get("subtasks")
        if subtasks is not None:
            if not isinstance(subtasks, Sequence) or isinstance(subtasks, (str, bytes)):
                raise TypeError("subtasks must be a sequence")
            specs = []
            for item in subtasks:
                if not isinstance(item, Mapping):
                    raise TypeError("each subtask must be a mapping")
                role_id = str(item["role"])
                action = str(item["action"]).strip()
                if role_id not in role_ids:
                    raise ValueError(f"subtask references undeclared role {role_id!r}")
                if not action:
                    raise ValueError("subtask action must not be empty")
                specs.append((role_id, action))
        else:
            specs = [
                (role_id, ROLE_ACTIONS[role_id].format(intent=task.intent))
                for role_id in role_ids
            ]

        if not specs:
            raise ValueError("workflow requires at least one subtask")
        if len(specs) > self.config.max_steps:
            raise ValueError(
                f"workflow has {len(specs)} subtasks; configured limit is "
                f"{self.config.max_steps}"
            )

        steps = []
        previous_step: Optional[str] = None
        for index, (role_id, action) in enumerate(specs, start=1):
            step_id = f"step-{index:02d}-{role_id}"
            parent_cause = previous_step or task.task_id
            depends_on = (previous_step,) if previous_step else ()
            evidence_refs = task.evidence_refs if index == 1 else ()
            steps.append(
                WorkflowStep(
                    step_id=step_id,
                    role_id=role_id,
                    action=action,
                    parent_cause=parent_cause,
                    depends_on=depends_on,
                    evidence_refs=evidence_refs,
                )
            )
            previous_step = step_id
        return tuple(steps)

    def _initial_events(self, plan: WorkflowPlan) -> tuple[TrailEvent, ...]:
        received = TrailEvent(
            event_id="event-task-received",
            task_id=plan.task.task_id,
            trail_id=plan.task.trail_id,
            event_type=TrailEventType.TASK_RECEIVED,
            actor=plan.task.actor,
            created_at=plan.task.created_at,
            parent_cause=plan.task.task_id,
            evidence_refs=plan.task.evidence_refs,
            payload={"intent": plan.task.intent},
        )
        created = TrailEvent(
            event_id="event-plan-created",
            task_id=plan.task.task_id,
            trail_id=plan.task.trail_id,
            event_type=TrailEventType.PLAN_CREATED,
            actor=self.config.actor,
            created_at=plan.task.created_at,
            parent_cause=received.event_id,
            evidence_refs=plan.task.evidence_refs,
            payload={
                "depth": self._depth(plan),
                "role_ids": [role.role_id for role in plan.roles],
                "step_ids": [step.step_id for step in plan.steps],
            },
        )
        return (received, created)

    def _record_revision(
        self,
        plan: WorkflowPlan,
        results: Sequence[JsonObject],
        reason: str,
        revision_step: WorkflowStep,
    ) -> None:
        events = self._events_by_trail.get(plan.task.trail_id)
        if events is None:
            events = self._initial_events(plan)
        parent_event = events[-1].event_id
        depth = self._depth(plan)
        event = TrailEvent(
            event_id=f"event-plan-revised-{depth:02d}",
            task_id=plan.task.task_id,
            trail_id=plan.task.trail_id,
            event_type=TrailEventType.PLAN_REVISED,
            actor=self.config.actor,
            created_at=plan.task.created_at,
            parent_cause=parent_event,
            evidence_refs=revision_step.evidence_refs,
            payload={
                "depth": depth,
                "reason": reason,
                "result_count": len(results),
                "step_id": revision_step.step_id,
            },
        )
        self._events_by_trail[plan.task.trail_id] = events + (event,)

    @staticmethod
    def _revision_role(plan: WorkflowPlan) -> str:
        role_ids = {role.role_id for role in plan.roles}
        for candidate in ("critic", "verifier", "summarizer"):
            if candidate in role_ids:
                return candidate
        return plan.roles[0].role_id

    @staticmethod
    def _depth(plan: WorkflowPlan) -> int:
        value = plan.task.metadata.get("orchestration_depth", 0)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("orchestration_depth must be an integer")
        return value

    @classmethod
    def _result_evidence(cls, results: Sequence[JsonObject]) -> tuple[str, ...]:
        refs = []
        for result in results:
            result_id = result.get("result_id")
            if result_id:
                refs.append(str(result_id))
            evidence = result.get("evidence_refs", ())
            if isinstance(evidence, (str, bytes)):
                raise TypeError("result evidence_refs must be a sequence")
            refs.extend(str(ref) for ref in evidence)
        return cls._deduplicate(refs)

    @classmethod
    def _unique_strings(cls, values: Any) -> tuple[str, ...]:
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            raise TypeError("roles must be a sequence")
        return cls._deduplicate(str(value) for value in values)

    @staticmethod
    def _deduplicate(values: Any) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                ordered.append(value)
        return tuple(ordered)
