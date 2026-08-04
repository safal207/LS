"""Seven-agent product council built on the CrossThreadEvent contract.

The offline path is deterministic and safe to run in CI. The profiles are also
suitable as system prompts for a live agent framework integration.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from .cross_thread import (
    Authority,
    CapabilityGrant,
    CrossThreadEvent,
    CrossThreadRuntime,
    DecisionReceipt,
    DispositionStatus,
    EventType,
    InMemoryEvidenceStore,
    VerificationStatus,
)
from .runtime import DispatchReceipt, ResultReceipt, TrustRuntime


class CouncilRole(StrEnum):
    IDEA = "idea"
    CUSTOMER = "customer"
    CONSUMER = "consumer"
    DESIGNER = "designer"
    EXECUTOR = "executor"
    STABILIZER = "stabilizer"
    INNOVATOR = "innovator"


@dataclass(frozen=True)
class AgentProfile:
    role: CouncilRole
    name: str
    russian_name: str
    mission: str
    deliverables: tuple[str, ...]
    authority_scope: tuple[str, ...]
    prohibited: tuple[str, ...]
    system_prompt: str


AGENT_PROFILES: tuple[AgentProfile, ...] = (
    AgentProfile(
        role=CouncilRole.IDEA,
        name="Idea Agent",
        russian_name="Агент Идея",
        mission="Turn an ambiguous opportunity into a falsifiable product hypothesis.",
        deliverables=("problem hypothesis", "value hypothesis", "success metric"),
        authority_scope=("propose_direction",),
        prohibited=("claim market validation", "authorize implementation"),
        system_prompt=(
            "You are the Idea Agent. Form one clear, falsifiable idea. State the user problem, "
            "the proposed value, assumptions, and a measurable success condition. Do not treat "
            "enthusiasm as evidence and do not authorize execution."
        ),
    ),
    AgentProfile(
        role=CouncilRole.CUSTOMER,
        name="Customer Agent",
        russian_name="Агент Заказчик",
        mission="Translate the idea into an explicit contract, scope, constraints, and acceptance criteria.",
        deliverables=("scope", "acceptance criteria", "non-goals", "budget boundary"),
        authority_scope=("define_requirements",),
        prohibited=("change the core goal silently", "approve unverified completion"),
        system_prompt=(
            "You are the Customer Agent. Act as the accountable buyer. Convert the idea into "
            "testable requirements, constraints, non-goals, and acceptance criteria. Reject "
            "vague outcomes and hidden scope expansion."
        ),
    ),
    AgentProfile(
        role=CouncilRole.CONSUMER,
        name="Consumer Agent",
        russian_name="Агент Потребитель",
        mission="Represent the real end user and expose friction, misunderstanding, and adoption risk.",
        deliverables=("user journey", "pain points", "failure modes", "adoption threshold"),
        authority_scope=("evaluate_experience",),
        prohibited=("invent customer approval", "hide accessibility or trust risks"),
        system_prompt=(
            "You are the Consumer Agent. Evaluate the proposal from the end user's point of "
            "view. Describe the journey, friction, trust concerns, accessibility concerns, and "
            "the minimum value required for adoption."
        ),
    ),
    AgentProfile(
        role=CouncilRole.DESIGNER,
        name="Designer Agent",
        russian_name="Агент Проектировщик",
        mission="Produce the smallest architecture that satisfies the verified contract and user needs.",
        deliverables=("components", "data flow", "invariants", "trade-offs", "test seams"),
        authority_scope=("design_system", "request_implementation"),
        prohibited=("bypass constraints", "assume evidence is true"),
        system_prompt=(
            "You are the Designer Agent. Design the smallest system that meets accepted "
            "requirements. Preserve authority boundaries, evidence flow, failure modes, and "
            "test seams. Explain trade-offs and do not smuggle implementation authority into design."
        ),
    ),
    AgentProfile(
        role=CouncilRole.EXECUTOR,
        name="Executor Agent",
        russian_name="Агент Исполнитель",
        mission="Implement only the bounded design and return evidence-bound results.",
        deliverables=("implementation", "test evidence", "limitations", "completion receipt"),
        authority_scope=("write_patch", "run_tests"),
        prohibited=("deploy", "merge", "claim completion without evidence"),
        system_prompt=(
            "You are the Executor Agent. Implement only the bounded approved design. Produce "
            "the smallest change, run focused tests, preserve evidence references, and report "
            "limitations. Never claim deployment or merge."
        ),
    ),
    AgentProfile(
        role=CouncilRole.STABILIZER,
        name="Stabilizer Agent",
        russian_name="Агент Стабилизатор",
        mission="Attack the result for correctness, safety, recoverability, and operational stability.",
        deliverables=("risk review", "negative tests", "stability verdict", "blockers"),
        authority_scope=("review_evidence", "block_release"),
        prohibited=("waive missing evidence", "convert recommendation into approval"),
        system_prompt=(
            "You are the Stabilizer Agent. Be adversarial. Verify evidence, stale-state handling, "
            "idempotency, rollback, permissions, and failure containment. Fail closed when proof "
            "is missing. A recommendation is never execution authority."
        ),
    ),
    AgentProfile(
        role=CouncilRole.INNOVATOR,
        name="Innovator Agent",
        russian_name="Агент Новатор",
        mission="Find a materially better next version without weakening current safety boundaries.",
        deliverables=("x10 opportunity", "alternative design", "experiment", "do-not-break list"),
        authority_scope=("propose_experiment",),
        prohibited=("expand authority", "invalidate the stable baseline without evidence"),
        system_prompt=(
            "You are the Innovator Agent. Seek a 10x improvement or simpler alternative, but "
            "preserve all verified invariants and authority limits. Propose an experiment with "
            "a falsifiable outcome rather than replacing the stable baseline on intuition."
        ),
    ),
)


@dataclass(frozen=True)
class CouncilStage:
    role: CouncilRole
    profile_name: str
    dispatch: DispatchReceipt
    result: ResultReceipt
    event: CrossThreadEvent
    decision: DecisionReceipt
    artifact: Mapping[str, Any]


@dataclass(frozen=True)
class CouncilRun:
    trajectory_id: str
    brief: str
    stages: tuple[CouncilStage, ...]
    trust_ledger_valid: bool
    cross_thread_audit_valid: bool
    final_verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "brief": self.brief,
            "stages": [
                {
                    "role": stage.role.value,
                    "profile_name": stage.profile_name,
                    "dispatch": asdict(stage.dispatch),
                    "result": asdict(stage.result),
                    "event": stage.event.to_dict(),
                    "decision": {
                        **asdict(stage.decision),
                        "status": stage.decision.status.value,
                    },
                    "artifact": dict(stage.artifact),
                }
                for stage in self.stages
            ],
            "trust_ledger_valid": self.trust_ledger_valid,
            "cross_thread_audit_valid": self.cross_thread_audit_valid,
            "final_verdict": self.final_verdict,
        }


class SevenAgentCouncil:
    """Deterministic reference workflow for seven durable peer agents."""

    FLOW: tuple[CouncilRole, ...] = (
        CouncilRole.IDEA,
        CouncilRole.CUSTOMER,
        CouncilRole.CONSUMER,
        CouncilRole.DESIGNER,
        CouncilRole.EXECUTOR,
        CouncilRole.STABILIZER,
        CouncilRole.INNOVATOR,
    )

    def __init__(self) -> None:
        self.trust = TrustRuntime()
        self.cross_thread = CrossThreadRuntime()
        self.evidence = InMemoryEvidenceStore()
        self.profiles = {profile.role: profile for profile in AGENT_PROFILES}
        self._register_threads_and_capabilities()

    @staticmethod
    def _thread_id(role: CouncilRole) -> str:
        return f"thread:{role.value}"

    def _register_threads_and_capabilities(self) -> None:
        for profile in AGENT_PROFILES:
            self.cross_thread.register_thread(
                thread_id=self._thread_id(profile.role),
                agent_id=profile.name,
                role=profile.role.value,
            )

        for index, role in enumerate(self.FLOW):
            next_role = self.FLOW[(index + 1) % len(self.FLOW)]
            max_authority = Authority(
                may_inform=True,
                may_request_action=(role == CouncilRole.DESIGNER),
                may_authorize_execution=False,
            )
            allowed_types: tuple[EventType, ...]
            if role == CouncilRole.DESIGNER:
                allowed_types = (EventType.ACTION_REQUEST,)
            elif role in {
                CouncilRole.IDEA,
                CouncilRole.INNOVATOR,
            }:
                allowed_types = (EventType.PROPOSAL,)
            else:
                allowed_types = (EventType.RESULT, EventType.STATE_UPDATE)
            grant = CapabilityGrant.build(
                source_thread_id=self._thread_id(role),
                target_thread_id=self._thread_id(next_role),
                allowed_event_types=allowed_types,
                max_authority=max_authority,
                allow_read=True,
                requires_target_consent=True,
            )
            self.cross_thread.grant_capability(grant)

    @staticmethod
    def _trajectory_id(brief: str) -> str:
        digest = hashlib.sha256(brief.encode("utf-8")).hexdigest()[:16]
        return f"project:{digest}"

    @staticmethod
    def _artifact(role: CouncilRole, brief: str, prior: Mapping[str, Any]) -> dict[str, Any]:
        if role == CouncilRole.IDEA:
            return {
                "problem_hypothesis": f"Teams need a safer way to coordinate durable agents for: {brief}",
                "value_hypothesis": "Typed evidence-aware handoffs reduce false completion and authority confusion.",
                "success_metric": "100% of state-bearing handoffs are evidence-verified before acceptance.",
                "assumptions": ["agents have stable thread identities", "evidence can be referenced"],
            }
        if role == CouncilRole.CUSTOMER:
            return {
                "scope": "A vendor-neutral typed event contract and seven-agent reference workflow.",
                "acceptance_criteria": [
                    "duplicate events are idempotent",
                    "stale state is rejected",
                    "verified claims require checked evidence",
                    "no agent may silently authorize execution",
                ],
                "non_goals": ["executing deploy or merge", "proving evidence truth without a verifier"],
                "source": prior,
            }
        if role == CouncilRole.CONSUMER:
            return {
                "user_journey": [
                    "define goal",
                    "watch specialist agents exchange typed receipts",
                    "inspect evidence and blockers",
                    "approve protected effects separately",
                ],
                "friction": ["too much protocol ceremony", "unclear rejected-state reason"],
                "adoption_threshold": "One-command offline demo plus machine-readable audit trail.",
                "trust_requirement": "Every decision explains why it was accepted, deferred, or rejected.",
            }
        if role == CouncilRole.DESIGNER:
            return {
                "components": [
                    "CrossThreadEvent",
                    "CapabilityGrant",
                    "EvidenceChecker",
                    "DecisionReceipt",
                    "CrossThreadRuntime",
                    "SevenAgentCouncil",
                ],
                "invariants": [
                    "delivery != verification != acceptance != authority",
                    "state updates require verified evidence",
                    "authority is capped by the receiver-side capability",
                    "audit records form a hash chain",
                ],
                "test_seams": ["evidence checker", "clock", "capability registry", "state version"],
                "trade_off": "Strict fail-closed behavior may defer useful but unverified updates.",
            }
        if role == CouncilRole.EXECUTOR:
            return {
                "implementation": [
                    "typed Python dataclasses and enums",
                    "deterministic evidence store",
                    "fail-closed receiver",
                    "seven-agent offline workflow",
                    "JSON Schema and examples",
                    "pytest conformance suite",
                ],
                "tests_expected": 12,
                "limitations": [
                    "no cryptographic agent identity",
                    "no network transport",
                    "no real external effect execution",
                ],
            }
        if role == CouncilRole.STABILIZER:
            return {
                "negative_tests": [
                    "forged evidence digest",
                    "replayed event id",
                    "stale sequence",
                    "revoked capability",
                    "archived sender",
                    "authority escalation",
                    "unauthorized audit read",
                ],
                "residual_risks": [
                    "local evidence registry can be compromised with the host",
                    "hash chain needs an external checkpoint for suffix-truncation detection",
                ],
                "verdict": "HOLD unless all conformance tests pass; otherwise ACCEPT AS ADVISORY PROTOTYPE.",
            }
        return {
            "x10_opportunity": "Standardize DecisionReceipt alongside CrossThreadEvent across agent frameworks.",
            "alternative": "Use signed content-addressed evidence manifests when cryptographic identity is available.",
            "experiment": "Integrate the fixture with Codex, OpenAI Agents SDK, and one non-OpenAI framework.",
            "do_not_break": [
                "human authority separation",
                "evidence verification before state acceptance",
                "idempotency",
                "stale-state rejection",
            ],
        }

    def run(self, brief: str) -> CouncilRun:
        normalized_brief = brief.strip()
        if not normalized_brief:
            raise ValueError("brief must not be empty")
        trajectory_id = self._trajectory_id(normalized_brief)
        prior_artifact: Mapping[str, Any] = {"brief": normalized_brief}
        stages: list[CouncilStage] = []

        for index, role in enumerate(self.FLOW, start=1):
            profile = self.profiles[role]
            next_role = self.FLOW[index % len(self.FLOW)]
            task = f"{profile.mission} Project brief: {normalized_brief}"
            dispatch = self.trust.issue_dispatch(
                parent_agent="Human" if index == 1 else self.profiles[self.FLOW[index - 2]].name,
                child_agent=profile.name,
                task=task,
                constraints=("advisory only", "preserve evidence", "no external effects"),
                authority_scope=profile.authority_scope,
            )
            artifact = self._artifact(role, normalized_brief, prior_artifact)
            artifact_json = json.dumps(artifact, sort_keys=True, ensure_ascii=False)
            evidence_ref = self.evidence.put(
                f"artifact:{trajectory_id}:{role.value}:{index}",
                artifact_json,
                media_type="application/json",
            )
            result = self.trust.submit_result(
                dispatch_id=dispatch.receipt_id,
                agent=profile.name,
                status="COMPLETED",
                summary=f"{profile.name} produced its bounded artifact.",
                evidence=(f"{evidence_ref.ref}#sha256={evidence_ref.sha256}",),
            )

            if role == CouncilRole.DESIGNER:
                event_type = EventType.ACTION_REQUEST
                authority = Authority(may_inform=True, may_request_action=True)
                verification = VerificationStatus.VERIFIED
            elif role in {CouncilRole.IDEA, CouncilRole.INNOVATOR}:
                event_type = EventType.PROPOSAL
                authority = Authority(may_inform=True)
                verification = VerificationStatus.UNVERIFIED
            else:
                event_type = EventType.RESULT
                authority = Authority(may_inform=True)
                verification = VerificationStatus.VERIFIED

            event = CrossThreadEvent.build(
                trajectory_id=trajectory_id,
                continuation_id=f"{role.value}-{index}",
                source_thread_id=self._thread_id(role),
                source_agent_id=profile.name,
                source_role=role.value,
                target_thread_id=self._thread_id(next_role),
                event_type=event_type,
                subject=f"council.{role.value}.artifact",
                payload=artifact,
                evidence_refs=(evidence_ref,) if verification == VerificationStatus.VERIFIED else (),
                verification_status=verification,
                authority=authority,
                sequence=index,
            )
            decision = self.cross_thread.receive(
                event,
                evidence_checker=self.evidence.verify,
            )
            if decision.status != DispositionStatus.ACCEPTED:
                raise RuntimeError(
                    f"council stage {role.value} was not accepted: {decision.reason}"
                )
            stages.append(
                CouncilStage(
                    role=role,
                    profile_name=profile.name,
                    dispatch=dispatch,
                    result=result,
                    event=event,
                    decision=decision,
                    artifact=artifact,
                )
            )
            prior_artifact = artifact

        stabilizer = next(stage for stage in stages if stage.role == CouncilRole.STABILIZER)
        final_verdict = str(stabilizer.artifact["verdict"])
        return CouncilRun(
            trajectory_id=trajectory_id,
            brief=normalized_brief,
            stages=tuple(stages),
            trust_ledger_valid=self.trust.verify_ledger(),
            cross_thread_audit_valid=self.cross_thread.verify_audit(),
            final_verdict=final_verdict,
        )


def agent_profile(role: CouncilRole | str) -> AgentProfile:
    normalized = CouncilRole(str(role))
    return next(profile for profile in AGENT_PROFILES if profile.role == normalized)


def build_openai_agents_team() -> Any:
    """Build the seven SDK agents without making an API call.

    Import is local so the deterministic protocol remains usable without the
    optional OpenAI Agents SDK installed.
    """

    try:
        from agents import Agent, handoff
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "openai-agents is required to build the live seven-agent team"
        ) from exc

    built: dict[CouncilRole, Any] = {}
    next_agent: Any | None = None
    for profile in reversed(AGENT_PROFILES):
        instructions = profile.system_prompt
        handoffs: list[Any] = []
        if next_agent is not None:
            instructions += (
                f" When finished, hand off the bounded artifact to {next_agent.name}. "
                "Do not expand authority and preserve evidence references."
            )
            handoffs = [handoff(agent=next_agent)]
        agent = Agent(
            name=profile.name,
            handoff_description=profile.mission,
            instructions=instructions,
            handoffs=handoffs,
        )
        built[profile.role] = agent
        next_agent = agent
    return built[CouncilRole.IDEA]
