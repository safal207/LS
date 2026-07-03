"""Deterministic Route Artifact v2 verification and registry projection."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

API_VERSION = "ls.route/v2"
KIND = "RouteArtifact"
STATUSES = {"draft", "experimental", "candidate", "validated", "deprecated", "revoked"}
TIERS = {"T0_deterministic_replay", "T1_artifact_attested", "T2_narrative_only"}
CAPABILITIES = {"frontier", "mid", "small", "open_weight", "human", "deterministic_tool"}
RISKS = {"low", "medium", "high", "critical"}
ROUTE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REF_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")


class RouteArtifactError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def fail(code: str, message: str) -> None:
    raise RouteArtifactError(code, message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def protected_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(artifact))
    if isinstance(payload.get("integrity"), dict):
        payload["integrity"]["content_digest"] = None
    return payload


def compute_content_digest(artifact: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(protected_payload(artifact)).encode()).hexdigest()


def artifact_ref(artifact: Mapping[str, Any]) -> str:
    return f"{artifact.get('route_id')}@{artifact.get('version')}"


def obj(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        fail("ROUTE-V2-TYPE", f"{path} must be an object")
    return value


def arr(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        fail("ROUTE-V2-TYPE", f"{path} must be an array")
    return value


def text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        fail("ROUTE-V2-TYPE", f"{path} must be a non-empty string")
    return value


def integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail("ROUTE-V2-TYPE", f"{path} must be an integer >= {minimum}")
    return value


def boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        fail("ROUTE-V2-TYPE", f"{path} must be a boolean")
    return value


def exact(value: Mapping[str, Any], path: str, keys: set[str]) -> None:
    missing, extra = keys - set(value), set(value) - keys
    if missing:
        fail("ROUTE-V2-SHAPE", f"{path} is missing keys: {sorted(missing)}")
    if extra:
        fail("ROUTE-V2-SHAPE", f"{path} contains unknown keys: {sorted(extra)}")


def metric(value: Any, path: str) -> None:
    value = obj(value, path)
    exact(value, path, {"point", "ci95"})
    point, ci = value["point"], value["ci95"]
    if point is not None and (isinstance(point, bool) or not isinstance(point, (int, float))):
        fail("ROUTE-V2-METRIC", f"{path}.point must be numeric or null")
    if ci is None:
        if point is not None:
            fail("ROUTE-V2-METRIC", f"{path}.ci95 is required when point is present")
        return
    ci = obj(ci, f"{path}.ci95")
    exact(ci, f"{path}.ci95", {"lower", "upper"})
    lower, upper = ci["lower"], ci["upper"]
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (lower, upper)):
        fail("ROUTE-V2-METRIC", f"{path}.ci95 bounds must be numeric")
    if lower > upper or (point is not None and not lower <= point <= upper):
        fail("ROUTE-V2-METRIC", f"{path} has inconsistent point/ci95")


def complete_metric(value: Mapping[str, Any]) -> bool:
    ci = value.get("ci95")
    return value.get("point") is not None and isinstance(ci, Mapping) and ci.get("lower") is not None and ci.get("upper") is not None


def verify_replay(value: Any) -> None:
    replay = obj(value, "verification.replay")
    exact(replay, "verification.replay", {"command", "expected_exit_code", "observed_exit_code", "assertions", "passed", "evidence_digest"})
    text(replay["command"], "verification.replay.command")
    expected = integer(replay["expected_exit_code"], "verification.replay.expected_exit_code")
    observed = integer(replay["observed_exit_code"], "verification.replay.observed_exit_code")
    if not boolean(replay["passed"], "verification.replay.passed") or observed != expected:
        fail("ROUTE-V2-REPLAY", "deterministic replay did not reproduce the expected result")
    digest = text(replay["evidence_digest"], "verification.replay.evidence_digest")
    if not SHA_RE.fullmatch(digest):
        fail("ROUTE-V2-DIGEST", "replay evidence_digest must be lowercase SHA-256")
    assertions = arr(replay["assertions"], "verification.replay.assertions")
    if not assertions:
        fail("ROUTE-V2-REPLAY", "replay assertions must not be empty")
    for index, raw in enumerate(assertions):
        assertion = obj(raw, f"verification.replay.assertions[{index}]")
        exact(assertion, f"verification.replay.assertions[{index}]", {"name", "passed"})
        text(assertion["name"], f"verification.replay.assertions[{index}].name")
        if not boolean(assertion["passed"], f"verification.replay.assertions[{index}].passed"):
            fail("ROUTE-V2-REPLAY", f"replay assertion failed: {assertion['name']}")


def verify_promotion(route: Mapping[str, Any]) -> None:
    if route["status"] not in {"candidate", "validated"}:
        return
    m, p = route["metrics"], route["promotion_policy"]
    failures = []
    for metric_key, policy_key in (
        ("t0_runs", "minimum_t0_runs"),
        ("repository_count", "minimum_repositories"),
        ("task_variant_count", "minimum_task_variants"),
        ("sealed_honeypot_runs", "minimum_sealed_honeypot_runs"),
    ):
        if m[metric_key] < p[policy_key]:
            failures.append(policy_key)
    if m["unresolved_critical_false_negatives"]:
        failures.append("unresolved_critical_false_negatives")
    if not complete_metric(m["confirmed_effectiveness"]):
        failures.append("confirmed_effectiveness_ci95")
    if not complete_metric(m["false_positive_rate"]):
        failures.append("false_positive_rate_ci95")
    if failures:
        fail("ROUTE-V2-PROMOTION", f"promotion gates failed: {', '.join(failures)}")
    if route["status"] == "validated" and p["requires_maintainer_approval"] and not m["maintainer_approved"]:
        fail("ROUTE-V2-PROMOTION", "validated route requires maintainer approval")


def verify_route_artifact(artifact: Any, *, canonical_store: bool = True) -> dict[str, Any]:
    route = obj(artifact, "route")
    exact(route, "route", {"api_version", "kind", "route_id", "version", "status", "integrity", "lineage", "task_profile", "executor_profile", "stages", "verification", "metrics", "promotion_policy", "training", "license", "publishability", "provenance"})
    if route["api_version"] != API_VERSION or route["kind"] != KIND:
        fail("ROUTE-V2-VERSION", "unsupported Route Artifact version or kind")
    route_id, version, status = text(route["route_id"], "route.route_id"), text(route["version"], "route.version"), text(route["status"], "route.status")
    if not ROUTE_RE.fullmatch(route_id) or not SEMVER_RE.fullmatch(version):
        fail("ROUTE-V2-ID", "route_id or version is invalid")
    if status not in STATUSES:
        fail("ROUTE-V2-STATUS", f"unsupported status: {status}")

    integrity = obj(route["integrity"], "route.integrity")
    exact(integrity, "route.integrity", {"digest_algorithm", "content_digest"})
    digest = text(integrity["content_digest"], "route.integrity.content_digest")
    if integrity["digest_algorithm"] != "sha256" or not SHA_RE.fullmatch(digest):
        fail("ROUTE-V2-DIGEST", "invalid content digest contract")
    expected = compute_content_digest(route)
    if digest != expected:
        fail("ROUTE-V2-DIGEST", f"content digest mismatch: expected {expected}")

    ref = artifact_ref(route)
    lineage = obj(route["lineage"], "route.lineage")
    exact(lineage, "route.lineage", {"supersedes"})
    parents = arr(lineage["supersedes"], "route.lineage.supersedes")
    seen = set()
    for parent in parents:
        parent = text(parent, "route.lineage.supersedes[]")
        if not REF_RE.fullmatch(parent) or parent == ref or parent in seen:
            fail("ROUTE-V2-LINEAGE", f"invalid supersession reference: {parent}")
        seen.add(parent)

    profile = obj(route["task_profile"], "route.task_profile")
    exact(profile, "route.task_profile", {"category", "subtype", "risk_level"})
    text(profile["category"], "route.task_profile.category")
    text(profile["subtype"], "route.task_profile.subtype")
    if profile["risk_level"] not in RISKS:
        fail("ROUTE-V2-RISK", "unsupported risk level")

    roles = {}
    for index, raw in enumerate(arr(route["executor_profile"], "route.executor_profile")):
        executor = obj(raw, f"route.executor_profile[{index}]")
        exact(executor, f"route.executor_profile[{index}]", {"role", "capability_class"})
        role, capability = text(executor["role"], "executor.role"), text(executor["capability_class"], "executor.capability_class")
        if not NAME_RE.fullmatch(role) or capability not in CAPABILITIES or role in roles:
            fail("ROUTE-V2-EXECUTOR", f"invalid or duplicate executor: {role}")
        roles[role] = capability
    if not roles:
        fail("ROUTE-V2-EXECUTOR", "executor_profile must not be empty")

    known = set()
    stages = arr(route["stages"], "route.stages")
    if not stages:
        fail("ROUTE-V2-STAGE", "stages must not be empty")
    for index, raw in enumerate(stages):
        stage = obj(raw, f"route.stages[{index}]")
        exact(stage, f"route.stages[{index}]", {"id", "role", "capability_class", "independent", "depends_on"})
        stage_id, role = text(stage["id"], "stage.id"), text(stage["role"], "stage.role")
        capability = text(stage["capability_class"], "stage.capability_class")
        boolean(stage["independent"], "stage.independent")
        if not NAME_RE.fullmatch(stage_id) or stage_id in known or role not in roles or capability != roles[role]:
            fail("ROUTE-V2-STAGE", f"invalid stage declaration: {stage_id}")
        deps = arr(stage["depends_on"], "stage.depends_on")
        if len(set(deps)) != len(deps) or any(not isinstance(dep, str) or dep not in known for dep in deps):
            fail("ROUTE-V2-STAGE", f"stage {stage_id} has missing, repeated, or non-prior dependency")
        known.add(stage_id)

    verification = obj(route["verification"], "route.verification")
    exact(verification, "route.verification", {"tier", "exact_head", "sandbox", "replay", "artifact_refs", "human_sign_off", "narrative"})
    tier = text(verification["tier"], "route.verification.tier")
    if tier not in TIERS:
        fail("ROUTE-V2-TIER", f"unsupported tier: {tier}")
    sandbox = boolean(verification["sandbox"], "route.verification.sandbox")
    artifact_refs = arr(verification["artifact_refs"], "route.verification.artifact_refs")
    for item in artifact_refs:
        text(item, "route.verification.artifact_refs[]")
    head = verification["exact_head"]
    if head is not None and (not isinstance(head, str) or not HEAD_RE.fullmatch(head)):
        fail("ROUTE-V2-HEAD", "exact_head must be a lowercase 40-character git SHA")
    sign_off = verification["human_sign_off"]
    if sign_off is not None:
        sign_off = obj(sign_off, "route.verification.human_sign_off")
        exact(sign_off, "route.verification.human_sign_off", {"actor", "signed_at", "decision"})
        text(sign_off["actor"], "human_sign_off.actor")
        text(sign_off["signed_at"], "human_sign_off.signed_at")
        if sign_off["decision"] != "attested":
            fail("ROUTE-V2-TIER", "human sign-off must be attested")
    narrative = verification["narrative"]
    if narrative is not None:
        text(narrative, "route.verification.narrative")

    if tier == "T0_deterministic_replay":
        if head is None or not sandbox:
            fail("ROUTE-V2-T0", "T0 requires exact_head and sandbox=true")
        verify_replay(verification["replay"])
    elif tier == "T1_artifact_attested":
        if not artifact_refs or sign_off is None or verification["replay"] is not None:
            fail("ROUTE-V2-T1", "T1 requires artifacts and sign-off without replay claim")
    elif canonical_store:
        fail("ROUTE-V2-T2", "narrative-only submissions are rejected from the canonical store")
    elif not narrative:
        fail("ROUTE-V2-T2", "T2 rejection audit requires a narrative")

    metrics = obj(route["metrics"], "route.metrics")
    exact(metrics, "route.metrics", {"sample_size", "t0_runs", "repository_count", "task_variant_count", "sealed_honeypot_runs", "unresolved_critical_false_negatives", "confirmed_effectiveness", "false_positive_rate", "reviewer_minutes_saved", "maintainer_approved"})
    for key in ("sample_size", "t0_runs", "repository_count", "task_variant_count", "sealed_honeypot_runs", "unresolved_critical_false_negatives"):
        integer(metrics[key], f"route.metrics.{key}")
    if metrics["t0_runs"] > metrics["sample_size"]:
        fail("ROUTE-V2-METRIC", "t0_runs cannot exceed sample_size")
    for key in ("confirmed_effectiveness", "false_positive_rate", "reviewer_minutes_saved"):
        metric(metrics[key], f"route.metrics.{key}")
    boolean(metrics["maintainer_approved"], "route.metrics.maintainer_approved")

    policy = obj(route["promotion_policy"], "route.promotion_policy")
    exact(policy, "route.promotion_policy", {"minimum_t0_runs", "minimum_repositories", "minimum_task_variants", "minimum_sealed_honeypot_runs", "requires_zero_unresolved_critical_false_negatives", "requires_confidence_intervals", "requires_maintainer_approval"})
    for key in ("minimum_t0_runs", "minimum_repositories", "minimum_task_variants", "minimum_sealed_honeypot_runs"):
        integer(policy[key], f"route.promotion_policy.{key}", 1)
    for key in ("requires_zero_unresolved_critical_false_negatives", "requires_confidence_intervals", "requires_maintainer_approval"):
        if not boolean(policy[key], f"route.promotion_policy.{key}"):
            fail("ROUTE-V2-POLICY", f"initial v2 policy requires {key}=true")

    training = obj(route["training"], "route.training")
    exact(training, "route.training", {"eligible", "corpus_scope"})
    eligible = boolean(training["eligible"], "route.training.eligible")
    if training["corpus_scope"] not in {"none", "research", "distillation"}:
        fail("ROUTE-V2-TRAINING", "unsupported corpus scope")

    license_value = obj(route["license"], "route.license")
    exact(license_value, "route.license", {"artifact_license", "training_permission", "redistribution_permission", "commercial_use"})
    text(license_value["artifact_license"], "route.license.artifact_license")
    if license_value["training_permission"] not in {"none", "open_weight_only_v1", "any_with_attribution_v1"}:
        fail("ROUTE-V2-LICENSE", "unsupported training permission")
    if license_value["redistribution_permission"] not in {"prohibited", "allowed_with_attribution", "allowed"}:
        fail("ROUTE-V2-LICENSE", "unsupported redistribution permission")
    if license_value["commercial_use"] not in {"prohibited", "restricted", "allowed"}:
        fail("ROUTE-V2-LICENSE", "unsupported commercial-use policy")

    publish = obj(route["publishability"], "route.publishability")
    exact(publish, "route.publishability", {"level"})
    if publish["level"] not in {"private", "community", "public"}:
        fail("ROUTE-V2-PUBLISH", "unsupported publishability level")

    provenance = obj(route["provenance"], "route.provenance")
    exact(provenance, "route.provenance", {"contributors", "source_runs", "created_at"})
    for value in arr(provenance["contributors"], "route.provenance.contributors"):
        text(value, "route.provenance.contributors[]")
    for value in arr(provenance["source_runs"], "route.provenance.source_runs"):
        text(value, "route.provenance.source_runs[]")
    text(provenance["created_at"], "route.provenance.created_at")

    if tier != "T0_deterministic_replay":
        if eligible or training["corpus_scope"] != "none":
            fail("ROUTE-V2-TRAINING", "only T0 routes may be training-corpus eligible")
        if metrics["confirmed_effectiveness"]["point"] is not None:
            fail("ROUTE-V2-METRIC", "non-T0 routes cannot claim confirmed effectiveness")
    elif eligible and license_value["training_permission"] == "none":
        fail("ROUTE-V2-TRAINING", "training eligibility requires explicit permission")

    verify_promotion(route)
    return {"route_ref": ref, "content_digest": digest, "tier": tier, "status": status, "canonical_store_eligible": tier != "T2_narrative_only", "training_eligible": eligible}


def verify_immutable_update(existing_digests: Mapping[str, str], artifact: Mapping[str, Any]) -> None:
    summary = verify_route_artifact(artifact)
    previous = existing_digests.get(summary["route_ref"])
    if previous is not None and previous != summary["content_digest"]:
        fail("ROUTE-V2-IMMUTABLE", f"immutable route version was modified: {summary['route_ref']}")


def build_registry_projection(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    records = {}
    for artifact in artifacts:
        summary = verify_route_artifact(artifact)
        ref = summary["route_ref"]
        if ref in records:
            fail("ROUTE-V2-REGISTRY", f"duplicate route version: {ref}")
        records[ref] = {"route_ref": ref, "content_digest": summary["content_digest"], "status": summary["status"], "tier": summary["tier"], "supersedes": list(artifact["lineage"]["supersedes"]), "superseded_by": []}
    for ref, record in records.items():
        for parent in record["supersedes"]:
            if parent not in records:
                fail("ROUTE-V2-REGISTRY", f"{ref} supersedes missing route version {parent}")
            records[parent]["superseded_by"].append(ref)
    state = {}
    def visit(ref: str, trail: list[str]) -> None:
        if state.get(ref) == 1:
            fail("ROUTE-V2-REGISTRY", f"supersession cycle detected: {' -> '.join(trail + [ref])}")
        if state.get(ref) == 2:
            return
        state[ref] = 1
        for parent in records[ref]["supersedes"]:
            visit(parent, trail + [ref])
        state[ref] = 2
    for ref in sorted(records):
        visit(ref, [])
    for record in records.values():
        record["superseded_by"].sort()
    return {"routes": [records[ref] for ref in sorted(records)]}
