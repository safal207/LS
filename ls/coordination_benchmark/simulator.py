from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Set, Tuple

from .contracts import canonical_sha256, validate_route_result, validate_scenario

SAFETY_METRICS = (
    "stale_action_count",
    "dependency_violation_count",
    "unverified_release_count",
    "unauthorized_event_acceptance_count",
    "duplicate_side_effect_count",
)


@dataclass(frozen=True)
class RouteProfile:
    route_id: str
    transport: str
    durable_history: bool
    per_session_offsets: bool
    invalidates_cached_plans: bool
    validates_producer: bool
    validates_generation: bool
    deduplicates_event_ids: bool
    requires_verified_receipt: bool
    replays_on_recovery: bool
    human_relay: bool
    recovery_time_ms: int
    event_to_replan_latency_ms: int
    implementation_complexity_units: int

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RouteProfile":
        expected_schema = "ls.multi-session.route-profile.v0.1"
        if payload.get("schema") != expected_schema:
            raise ValueError("unsupported route profile schema")
        fields = {name: payload[name] for name in cls.__dataclass_fields__}
        return cls(**fields)


@dataclass
class SessionState:
    session_id: str
    plan_generation: int
    last_offset: int = 0
    seen_event_ids: Set[str] = field(default_factory=set)
    needs_replan: bool = False
    recovered: bool = False


@dataclass(frozen=True)
class RouteRun:
    result: Dict[str, Any]
    trace: Tuple[Dict[str, Any], ...]


def _trace(
    trace: List[Dict[str, Any]],
    step: str,
    outcome: str,
    **fields: Any,
) -> None:
    item = {
        "sequence": len(trace) + 1,
        "step": step,
        "outcome": outcome,
    }
    item.update(fields)
    trace.append(item)


def _endpoint_event(
    base: Mapping[str, Any],
    *,
    event_id: str,
    producer: str,
    generation: int,
    endpoint: str,
) -> Dict[str, Any]:
    event = copy.deepcopy(dict(base))
    event["event_id"] = event_id
    event["producer_session"] = producer
    event["generation"] = generation
    event["payload"]["new_value"] = endpoint
    return event


def _consume_event(
    session: SessionState,
    event: Mapping[str, Any],
    profile: RouteProfile,
    metrics: MutableMapping[str, Any],
    trace: List[Dict[str, Any]],
    *,
    expected_producer: str,
    expected_generation: int,
) -> None:
    event_id = str(event["event_id"])
    if event_id in session.seen_event_ids:
        if profile.deduplicates_event_ids:
            metrics["deduplicated_event_count"] += 1
            _trace(
                trace,
                "consume_event",
                "DEDUPLICATED",
                session_id=session.session_id,
                event_id=event_id,
            )
            return
        metrics["duplicate_side_effect_count"] += 1
        _trace(
            trace,
            "consume_event",
            "DUPLICATE_EFFECT",
            session_id=session.session_id,
            event_id=event_id,
        )

    unauthorized = event["producer_session"] != expected_producer
    if unauthorized and profile.validates_producer:
        metrics["blocked_transition_count"] += 1
        _trace(
            trace,
            "consume_event",
            "BLOCKED_UNAUTHORIZED_PRODUCER",
            session_id=session.session_id,
            event_id=event_id,
        )
        return
    if unauthorized:
        metrics["unauthorized_event_acceptance_count"] += 1
        _trace(
            trace,
            "consume_event",
            "ACCEPTED_UNAUTHORIZED_PRODUCER",
            session_id=session.session_id,
            event_id=event_id,
        )

    stale_generation = int(event["generation"]) < expected_generation
    if stale_generation and profile.validates_generation:
        metrics["blocked_transition_count"] += 1
        _trace(
            trace,
            "consume_event",
            "BLOCKED_STALE_GENERATION",
            session_id=session.session_id,
            event_id=event_id,
        )
        return

    session.seen_event_ids.add(event_id)
    if profile.invalidates_cached_plans:
        session.needs_replan = True
        session.plan_generation = int(event["generation"])
        metrics["replayed_event_count"] += int(
            session.recovered and profile.durable_history
        )
        _trace(
            trace,
            "consume_event",
            "PLAN_INVALIDATED",
            session_id=session.session_id,
            event_id=event_id,
            generation=event["generation"],
        )
    else:
        _trace(
            trace,
            "consume_event",
            "OBSERVED_WITHOUT_INVALIDATION",
            session_id=session.session_id,
            event_id=event_id,
            generation=event["generation"],
        )

    if not profile.validates_generation:
        session.plan_generation = int(event["generation"])


def _deliver(
    sessions: Mapping[str, SessionState],
    event: Mapping[str, Any],
    profile: RouteProfile,
    metrics: MutableMapping[str, Any],
    trace: List[Dict[str, Any]],
    *,
    expected_producer: str,
    expected_generation: int,
    shared_state: MutableMapping[str, Mapping[str, Any]],
    event_log: List[Mapping[str, Any]],
) -> None:
    if profile.human_relay:
        metrics["human_relay_count"] += 1
        target = sessions["database"]
        _consume_event(
            target,
            event,
            profile,
            metrics,
            trace,
            expected_producer=expected_producer,
            expected_generation=expected_generation,
        )
        return

    if profile.transport == "shared_mutable_state":
        if shared_state:
            metrics["conflict_count"] += 1
        shared_state["infra.endpoint.changed"] = event
        _trace(
            trace,
            "publish_event",
            "SHARED_STATE_OVERWRITE",
            event_id=event["event_id"],
        )
        return

    event_log.append(event)
    log_offset = len(event_log)
    _trace(
        trace,
        "publish_event",
        "APPENDED",
        event_id=event["event_id"],
        offset=log_offset,
    )
    for session_id in event["affected_sessions"]:
        session = sessions[session_id]
        if not session.recovered:
            _consume_event(
                session,
                event,
                profile,
                metrics,
                trace,
                expected_producer=expected_producer,
                expected_generation=expected_generation,
            )
            session.last_offset = log_offset


def _sync_before_action(
    session: SessionState,
    profile: RouteProfile,
    metrics: MutableMapping[str, Any],
    trace: List[Dict[str, Any]],
    *,
    shared_state: Mapping[str, Mapping[str, Any]],
    event_log: Iterable[Mapping[str, Any]],
    expected_producer: str,
    expected_generation: int,
) -> None:
    if profile.transport == "shared_mutable_state" and shared_state:
        event = shared_state["infra.endpoint.changed"]
        _consume_event(
            session,
            event,
            profile,
            metrics,
            trace,
            expected_producer=expected_producer,
            expected_generation=expected_generation,
        )
    elif profile.durable_history and profile.per_session_offsets:
        log_items = list(event_log)
        for offset, event in enumerate(
            log_items[session.last_offset :],
            start=session.last_offset + 1,
        ):
            if session.session_id in event["affected_sessions"]:
                _consume_event(
                    session,
                    event,
                    profile,
                    metrics,
                    trace,
                    expected_producer=expected_producer,
                    expected_generation=expected_generation,
                )
            session.last_offset = offset

    if session.needs_replan:
        session.needs_replan = False
        metrics["replan_count"] += 1
        _trace(
            trace,
            "replan",
            "COMPLETED",
            session_id=session.session_id,
            generation=session.plan_generation,
        )


def _derive_unsafe_verdict(metrics: Mapping[str, Any]) -> str:
    if metrics["unauthorized_event_acceptance_count"]:
        return "UNSAFE_UNAUTHORIZED_EVENT"
    if metrics["duplicate_side_effect_count"]:
        return "UNSAFE_DUPLICATE_EFFECT"
    if metrics["stale_action_count"]:
        return "UNSAFE_STALE_ACTION"
    if (
        metrics["dependency_violation_count"]
        or metrics["unverified_release_count"]
    ):
        return "UNSAFE_DEPENDENCY_RELEASE"
    return "SAFE_PARETO_CANDIDATE"


def simulate_route(
    scenario: Mapping[str, Any],
    profile: RouteProfile,
) -> RouteRun:
    """Run the frozen v0.1 failure schedule against one capability profile."""

    validate_scenario(scenario)
    sessions = {
        item["session_id"]: SessionState(
            session_id=item["session_id"],
            plan_generation=int(item.get("initial_plan_generation", 0)),
        )
        for item in scenario["sessions"]
    }
    trace: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {
        "stale_action_count": 0,
        "dependency_violation_count": 0,
        "unverified_release_count": 0,
        "unauthorized_event_acceptance_count": 0,
        "duplicate_side_effect_count": 0,
        "human_relay_count": 0,
        "recovery_time_ms": profile.recovery_time_ms,
        "event_to_replan_latency_ms": profile.event_to_replan_latency_ms,
        "conflict_count": 0,
        "replayed_event_count": 0,
        "deduplicated_event_count": 0,
        "blocked_transition_count": 0,
        "replan_count": 0,
        "implementation_complexity_units": (
            profile.implementation_complexity_units
        ),
        "evidence_completeness": (
            1.0
            if profile.requires_verified_receipt
            else (0.7 if profile.durable_history else 0.3)
        ),
    }
    shared_state: Dict[str, Mapping[str, Any]] = {}
    event_log: List[Mapping[str, Any]] = []

    base_event = next(
        item
        for item in scenario["events"]
        if item["event_type"] == "infra.endpoint.changed"
    )
    expected_producer = str(base_event["producer_session"])
    expected_generation = int(base_event["generation"])

    _deliver(
        sessions,
        base_event,
        profile,
        metrics,
        trace,
        expected_producer=expected_producer,
        expected_generation=expected_generation,
        shared_state=shared_state,
        event_log=event_log,
    )

    database = sessions["database"]
    _sync_before_action(
        database,
        profile,
        metrics,
        trace,
        shared_state=shared_state,
        event_log=event_log,
        expected_producer=expected_producer,
        expected_generation=expected_generation,
    )
    if profile.requires_verified_receipt:
        metrics["blocked_transition_count"] += 1
        _trace(
            trace,
            "premature_dependency_action",
            "BLOCKED_MISSING_RECEIPT",
            session_id="database",
        )
    else:
        metrics["dependency_violation_count"] += 1
        metrics["unverified_release_count"] += 1
        _trace(
            trace,
            "premature_dependency_action",
            "EXECUTED_UNVERIFIED",
            session_id="database",
        )

    sessions["search"].recovered = True
    sessions["search"].seen_event_ids.clear()
    sessions["search"].last_offset = 0
    _trace(
        trace,
        "session_compaction",
        "CONTEXT_REPLACED",
        session_id="search",
    )

    sessions["dashboard"].recovered = True
    sessions["dashboard"].seen_event_ids.clear()
    sessions["dashboard"].last_offset = 0
    sessions["dashboard"].plan_generation = 1
    _trace(
        trace,
        "session_replacement",
        "ZERO_CONTEXT",
        session_id="dashboard",
    )

    duplicate = copy.deepcopy(dict(base_event))
    _deliver(
        sessions,
        duplicate,
        profile,
        metrics,
        trace,
        expected_producer=expected_producer,
        expected_generation=expected_generation,
        shared_state=shared_state,
        event_log=event_log,
    )

    forged = _endpoint_event(
        base_event,
        event_id="evt-forged-endpoint",
        producer="dashboard",
        generation=3,
        endpoint="203.0.113.66",
    )
    _deliver(
        sessions,
        forged,
        profile,
        metrics,
        trace,
        expected_producer=expected_producer,
        expected_generation=expected_generation,
        shared_state=shared_state,
        event_log=event_log,
    )

    stale = _endpoint_event(
        base_event,
        event_id="evt-stale-generation-1",
        producer="migration",
        generation=1,
        endpoint="192.0.2.10",
    )
    _deliver(
        sessions,
        stale,
        profile,
        metrics,
        trace,
        expected_producer=expected_producer,
        expected_generation=expected_generation,
        shared_state=shared_state,
        event_log=event_log,
    )

    dependent_count = len(scenario["dependencies"])
    if profile.requires_verified_receipt:
        metrics["blocked_transition_count"] += dependent_count
        _trace(
            trace,
            "done_without_verification",
            "DEPENDENCIES_HELD",
            count=dependent_count,
        )
        dependency_released = False
    else:
        metrics["unverified_release_count"] += dependent_count
        _trace(
            trace,
            "done_without_verification",
            "DEPENDENCIES_RELEASED",
            count=dependent_count,
        )
        dependency_released = True

    if profile.requires_verified_receipt:
        dependency_released = True
        _trace(
            trace,
            "verified_receipt",
            "DEPENDENCIES_RELEASED",
            verifier="endpoint-health-check",
        )

    for session_id in ("database", "search", "dashboard"):
        session = sessions[session_id]
        if session.recovered and not profile.replays_on_recovery:
            _trace(
                trace,
                "recovery",
                "NO_REPLAY",
                session_id=session_id,
            )
        else:
            _sync_before_action(
                session,
                profile,
                metrics,
                trace,
                shared_state=shared_state,
                event_log=event_log,
                expected_producer=expected_producer,
                expected_generation=expected_generation,
            )

        if not dependency_released:
            metrics["dependency_violation_count"] += 1
            _trace(
                trace,
                "dependent_action",
                "BLOCKED_DEPENDENCY",
                session_id=session_id,
            )
            continue

        if session.plan_generation != expected_generation:
            metrics["stale_action_count"] += 1
            _trace(
                trace,
                "dependent_action",
                "STALE_ACTION",
                session_id=session_id,
                plan_generation=session.plan_generation,
            )
        else:
            _trace(
                trace,
                "dependent_action",
                "SAFE_ACTION",
                session_id=session_id,
                plan_generation=session.plan_generation,
            )

    verdict = _derive_unsafe_verdict(metrics)
    result = {
        "schema": "ls.multi-session.route-result.v0.1",
        "route_id": profile.route_id,
        "scenario_hash": canonical_sha256(scenario),
        "verdict": verdict,
        "metrics": metrics,
        "evidence_refs": [
            f"traces/{profile.route_id}.trace.jsonl",
            "canonical-five-session-scenario.json",
            f"routes/{profile.route_id}.json",
        ],
    }
    validate_route_result(result)
    return RouteRun(result=result, trace=tuple(trace))


def apply_pareto_frontier(
    runs: Iterable[RouteRun],
) -> Tuple[RouteRun, ...]:
    runs = tuple(runs)
    safe = [
        run
        for run in runs
        if all(
            run.result["metrics"][name] == 0
            for name in SAFETY_METRICS
        )
    ]
    objectives = (
        "human_relay_count",
        "recovery_time_ms",
        "event_to_replan_latency_ms",
        "implementation_complexity_units",
    )
    dominated: Set[str] = set()
    for candidate in safe:
        for other in safe:
            if candidate is other:
                continue
            candidate_metrics = candidate.result["metrics"]
            other_metrics = other.result["metrics"]
            if all(
                other_metrics[name] <= candidate_metrics[name]
                for name in objectives
            ) and any(
                other_metrics[name] < candidate_metrics[name]
                for name in objectives
            ):
                dominated.add(candidate.result["route_id"])

    output = []
    for run in runs:
        result = copy.deepcopy(run.result)
        if run in safe:
            result["verdict"] = (
                "SAFE_DOMINATED"
                if result["route_id"] in dominated
                else "SAFE_PARETO_CANDIDATE"
            )
        output.append(RouteRun(result=result, trace=run.trace))
    return tuple(output)


def render_markdown_report(runs: Iterable[RouteRun]) -> str:
    runs = tuple(runs)
    lines = [
        "# Multi-Session Coordination Benchmark v0.1",
        "",
        "Safety constraints are evaluated before optimization metrics.",
        "",
        "| Route | Verdict | Stale | Dependency violations | "
        "Unverified releases | Unauthorized accepts | Duplicate effects | "
        "Human relays | Recovery ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in runs:
        result = run.result
        metrics = result["metrics"]
        lines.append(
            "| {route} | {verdict} | {stale} | {dependency} | "
            "{unverified} | {unauthorized} | {duplicate} | {relay} | "
            "{recovery} |".format(
                route=result["route_id"],
                verdict=result["verdict"],
                stale=metrics["stale_action_count"],
                dependency=metrics["dependency_violation_count"],
                unverified=metrics["unverified_release_count"],
                unauthorized=metrics[
                    "unauthorized_event_acceptance_count"
                ],
                duplicate=metrics["duplicate_side_effect_count"],
                relay=metrics["human_relay_count"],
                recovery=metrics["recovery_time_ms"],
            )
        )
    lines.extend(
        [
            "",
            "A route that violates any safety constraint is never promoted "
            "by lower latency or lower implementation complexity.",
            "",
        ]
    )
    return "\n".join(lines)
