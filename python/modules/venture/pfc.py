from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Dict, List, Literal, Optional
from uuid import uuid4

DecisionKind = Literal["admission", "gate", "allocation"]
DecisionValue = Literal["accept", "reject", "queue", "pass", "hold", "freeze", "kill", "rebalance"]
Stage = Literal["incubation", "early_pmf", "scale", "frozen", "killed"]


class PortfolioFlowError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class IdeaObject:
    idea_id: str
    title: str
    upside: float
    p_success: float
    execution_risk_penalty: float = 0.0


@dataclass(frozen=True)
class ValidationRecord:
    validation_record_id: str
    idea_id: str
    project_type: str
    signup_rate: float = 0.0
    cac_proxy: float = 0.0
    time_to_mvp_days: int = 0


@dataclass
class ProjectObject:
    project_id: str
    idea_id: str
    stage: Stage = "incubation"
    budget: float = 0.0
    frozen: bool = False
    killed: bool = False


@dataclass
class PortfolioState:
    treasury: float
    active_projects: Dict[str, ProjectObject] = field(default_factory=dict)
    admission_queue: List[str] = field(default_factory=list)
    reprioritization_counters: Dict[str, int] = field(default_factory=dict)
    focus_window_until: Dict[str, datetime] = field(default_factory=dict)


@dataclass(frozen=True)
class GateThresholds:
    activation_rate: float = 0.25
    retention_d7: float = 0.2
    retention_d30: float = 0.1
    ltv_cac: float = 2.5
    payback_period_months: float = 12.0
    gross_margin: float = 0.55


@dataclass(frozen=True)
class WIPLimits:
    max_active_projects_total: int = 12
    max_active_projects_incubation: int = 5
    max_active_projects_scale: int = 3


@dataclass(frozen=True)
class PFCPPolicy:
    policy_version: str = "pfc-policy-v1"
    dynamic_cutoff_base: float = 75_000.0
    min_runway_by_project_type: Dict[str, float] = field(default_factory=lambda: {"default": 10_000.0})
    top_tier_budget_share: float = 0.7
    min_focus_window_hours: int = 24
    max_reprioritizations_per_week: int = 5
    reserved_capacity_for_winners: float = 0.25
    wip_limits: WIPLimits = field(default_factory=WIPLimits)
    gates: GateThresholds = field(default_factory=GateThresholds)


@dataclass(frozen=True)
class PFCDecision:
    decision_id: str
    decision_type: DecisionKind
    entity_id: str
    decision: DecisionValue
    reasons: List[str]
    policy_version: str
    trace_id: str
    created_at: datetime
    expected_value: Optional[float] = None
    dynamic_cutoff: Optional[float] = None


@dataclass(frozen=True)
class LedgerEvent:
    event_type: str
    entity_id: str
    trace_id: str
    payload: Dict[str, object]
    at: datetime


class PortfolioFlowController:
    def __init__(self, state: PortfolioState, policy: Optional[PFCPPolicy] = None) -> None:
        self._state = state
        self._policy = policy or PFCPPolicy()
        self._decisions: List[PFCDecision] = []
        self._ledger_events: List[LedgerEvent] = []
        self._lock = RLock()

    @property
    def state(self) -> PortfolioState:
        return self._state

    def list_decisions(self) -> List[PFCDecision]:
        with self._lock:
            return list(self._decisions)

    def list_ledger_events(self) -> List[LedgerEvent]:
        with self._lock:
            return list(self._ledger_events)

    def evaluate_admission(
        self,
        idea: IdeaObject,
        validation: ValidationRecord,
        required_capital: float,
        trace_id: Optional[str] = None,
    ) -> PFCDecision:
        if validation.idea_id != idea.idea_id:
            raise PortfolioFlowError("MISMATCHED_IDEA", "validation.idea_id must match idea.idea_id")
        if required_capital <= 0:
            raise PortfolioFlowError("INVALID_CAPITAL", "required_capital must be > 0")

        with self._lock:
            trace = trace_id or str(uuid4())
            expected_value = self._expected_value(idea, required_capital)
            cutoff = self._dynamic_cutoff()
            reasons: List[str] = []

            if expected_value < cutoff:
                reasons.append("ev_below_cutoff")
                decision = self._record_decision(
                    decision_type="admission",
                    entity_id=idea.idea_id,
                    decision="reject",
                    reasons=reasons,
                    trace_id=trace,
                    expected_value=expected_value,
                    dynamic_cutoff=cutoff,
                )
                self._record_event("PFC_ADMISSION_DECIDED", idea.idea_id, trace, decision)
                return decision

            if not self._has_wip_slot(stage="incubation"):
                if idea.idea_id not in self._state.admission_queue:
                    self._state.admission_queue.append(idea.idea_id)
                reasons.append("wip_limit_reached")
                decision = self._record_decision(
                    decision_type="admission",
                    entity_id=idea.idea_id,
                    decision="queue",
                    reasons=reasons,
                    trace_id=trace,
                    expected_value=expected_value,
                    dynamic_cutoff=cutoff,
                )
                self._record_event("PFC_ADMISSION_DECIDED", idea.idea_id, trace, decision)
                return decision

            minimum_runway = self._minimum_runway(validation.project_type)
            if self._state.treasury < minimum_runway:
                reasons.append("insufficient_treasury")
                decision = self._record_decision(
                    decision_type="admission",
                    entity_id=idea.idea_id,
                    decision="reject",
                    reasons=reasons,
                    trace_id=trace,
                    expected_value=expected_value,
                    dynamic_cutoff=cutoff,
                )
                self._record_event("PFC_ADMISSION_DECIDED", idea.idea_id, trace, decision)
                return decision

            if self._state.treasury < required_capital:
                reasons.append("insufficient_treasury_for_capital")
                decision = self._record_decision(
                    decision_type="admission",
                    entity_id=idea.idea_id,
                    decision="reject",
                    reasons=reasons,
                    trace_id=trace,
                    expected_value=expected_value,
                    dynamic_cutoff=cutoff,
                )
                self._record_event("PFC_ADMISSION_DECIDED", idea.idea_id, trace, decision)
                return decision

            self._state.treasury -= required_capital
            project = ProjectObject(
                project_id=f"project_{idea.idea_id}",
                idea_id=idea.idea_id,
                stage="incubation",
                budget=required_capital,
            )
            self._state.active_projects[project.project_id] = project
            self._state.focus_window_until[project.project_id] = self._now() + timedelta(
                hours=self._policy.min_focus_window_hours
            )
            reasons.extend(["ev_above_cutoff", "wip_slot_available", "treasury_ok"])
            decision = self._record_decision(
                decision_type="admission",
                entity_id=idea.idea_id,
                decision="accept",
                reasons=reasons,
                trace_id=trace,
                expected_value=expected_value,
                dynamic_cutoff=cutoff,
            )
            self._record_event("PFC_ADMISSION_DECIDED", idea.idea_id, trace, decision)
            return decision

    def evaluate_gate(
        self,
        project_id: str,
        stage: Stage,
        metrics: Dict[str, float],
        trace_id: Optional[str] = None,
    ) -> PFCDecision:
        with self._lock:
            project = self._state.active_projects.get(project_id)
            if project is None:
                raise PortfolioFlowError("PROJECT_NOT_FOUND", f"unknown project_id: {project_id}")

            trace = trace_id or str(uuid4())
            reasons: List[str] = []
            decision_value: DecisionValue = "hold"

            if stage == "early_pmf":
                if (
                    metrics.get("activation_rate", 0.0) >= self._policy.gates.activation_rate
                    and metrics.get("retention_d7", 0.0) >= self._policy.gates.retention_d7
                    and metrics.get("retention_d30", 0.0) >= self._policy.gates.retention_d30
                ):
                    decision_value = "pass"
                    project.stage = "scale"
                    reasons.append("early_pmf_thresholds_met")
                elif metrics.get("retention_d30", 0.0) < (self._policy.gates.retention_d30 * 0.5):
                    decision_value = "freeze"
                    project.stage = "frozen"
                    project.frozen = True
                    reasons.append("retention_d30_critical")
                else:
                    decision_value = "hold"
                    reasons.append("retention_d30_below_threshold")

            elif stage == "scale":
                if (
                    metrics.get("ltv_cac", 0.0) >= self._policy.gates.ltv_cac
                    and metrics.get("payback_period_months", 999.0) <= self._policy.gates.payback_period_months
                    and metrics.get("gross_margin", 0.0) >= self._policy.gates.gross_margin
                ):
                    decision_value = "pass"
                    reasons.append("scale_thresholds_met")
                else:
                    decision_value = "kill"
                    project.stage = "killed"
                    project.killed = True
                    reasons.append("scale_thresholds_failed")
                    self._state.treasury += project.budget
            else:
                decision_value = "hold"
                reasons.append("stage_not_supported_v1")

            decision = self._record_decision(
                decision_type="gate",
                entity_id=project_id,
                decision=decision_value,
                reasons=reasons,
                trace_id=trace,
            )
            self._record_event("PFC_GATE_EVALUATED", project_id, trace, decision)
            if decision_value == "freeze":
                self._record_event("PFC_PROJECT_FROZEN", project_id, trace, {"reason": reasons})
            if decision_value == "kill":
                self._record_event("PFC_PROJECT_KILLED", project_id, trace, {"reason": reasons})
            return decision

    def rebalance_allocations(self, trace_id: Optional[str] = None) -> PFCDecision:
        with self._lock:
            trace = trace_id or str(uuid4())
            projects = [p for p in self._state.active_projects.values() if not p.killed and not p.frozen]
            if not projects:
                decision = self._record_decision(
                    decision_type="allocation",
                    entity_id="portfolio",
                    decision="rebalance",
                    reasons=["no_active_projects"],
                    trace_id=trace,
                )
                self._record_event("PFC_ALLOCATION_UPDATED", "portfolio", trace, decision)
                return decision

            total_budget = sum(p.budget for p in projects)
            ordered = sorted(projects, key=lambda p: p.budget, reverse=True)
            top_count = max(1, int(round(len(ordered) * 0.2)))
            top_projects = ordered[:top_count]
            others = ordered[top_count:]
            top_budget = total_budget * self._policy.top_tier_budget_share
            other_budget = total_budget - top_budget

            if top_projects:
                per_top = top_budget / len(top_projects)
                for p in top_projects:
                    p.budget = per_top
            if others:
                per_other = other_budget / len(others)
                for p in others:
                    p.budget = per_other

            decision = self._record_decision(
                decision_type="allocation",
                entity_id="portfolio",
                decision="rebalance",
                reasons=["capital_concentration_applied"],
                trace_id=trace,
            )
            self._record_event("PFC_ALLOCATION_UPDATED", "portfolio", trace, decision)
            return decision

    def reprioritize_project(self, project_id: str) -> None:
        with self._lock:
            if project_id not in self._state.active_projects:
                raise PortfolioFlowError("PROJECT_NOT_FOUND", f"unknown project_id: {project_id}")
            now = self._now()
            focus_until = self._state.focus_window_until.get(project_id, now)
            if now < focus_until:
                raise PortfolioFlowError("FOCUS_WINDOW_ACTIVE", "cannot reprioritize before focus window expires")
            cnt = self._state.reprioritization_counters.get(project_id, 0)
            if cnt >= self._policy.max_reprioritizations_per_week:
                raise PortfolioFlowError("REPRIORITIZATION_LIMIT", "max reprioritizations per week reached")
            self._state.reprioritization_counters[project_id] = cnt + 1

    def trace_project(self, project_id: str) -> List[PFCDecision]:
        with self._lock:
            return [d for d in self._decisions if d.entity_id in {project_id, self._project_idea_id(project_id)}]

    def _project_idea_id(self, project_id: str) -> str:
        project = self._state.active_projects.get(project_id)
        return project.idea_id if project else ""

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _expected_value(self, idea: IdeaObject, required_capital: float) -> float:
        return (idea.p_success * idea.upside) - required_capital - idea.execution_risk_penalty

    def _dynamic_cutoff(self) -> float:
        saturation = len(self._state.active_projects) / max(1, self._policy.wip_limits.max_active_projects_total)
        return self._policy.dynamic_cutoff_base * (1.0 + saturation)

    def _minimum_runway(self, project_type: str) -> float:
        return self._policy.min_runway_by_project_type.get(
            project_type, self._policy.min_runway_by_project_type.get("default", 10_000.0)
        )

    def _has_wip_slot(self, stage: Stage) -> bool:
        limits = self._policy.wip_limits
        active = [p for p in self._state.active_projects.values() if not p.killed]
        if len(active) >= limits.max_active_projects_total:
            return False
        if stage == "incubation":
            cnt = sum(1 for p in active if p.stage == "incubation")
            return cnt < limits.max_active_projects_incubation
        if stage == "scale":
            cnt = sum(1 for p in active if p.stage == "scale")
            return cnt < limits.max_active_projects_scale
        return True

    def _record_decision(
        self,
        decision_type: DecisionKind,
        entity_id: str,
        decision: DecisionValue,
        reasons: List[str],
        trace_id: str,
        expected_value: Optional[float] = None,
        dynamic_cutoff: Optional[float] = None,
    ) -> PFCDecision:
        row = PFCDecision(
            decision_id=str(uuid4()),
            decision_type=decision_type,
            entity_id=entity_id,
            decision=decision,
            reasons=list(reasons),
            policy_version=self._policy.policy_version,
            trace_id=trace_id,
            created_at=self._now(),
            expected_value=expected_value,
            dynamic_cutoff=dynamic_cutoff,
        )
        self._decisions.append(row)
        return row

    def _record_event(self, event_type: str, entity_id: str, trace_id: str, payload: object) -> None:
        serialized_payload = payload
        if isinstance(payload, PFCDecision):
            serialized_payload = {
                "decision_id": payload.decision_id,
                "decision": payload.decision,
                "reasons": payload.reasons,
                "policy_version": payload.policy_version,
            }
        event = LedgerEvent(
            event_type=event_type,
            entity_id=entity_id,
            trace_id=trace_id,
            payload=serialized_payload if isinstance(serialized_payload, dict) else {"value": serialized_payload},
            at=self._now(),
        )
        self._ledger_events.append(event)
