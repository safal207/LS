#!/usr/bin/env python3
"""Validate LS replay and append-only persistence contract v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "replay-persistence" / "manifest-v0.1.json"
OUTPUT = ROOT / "artifacts" / "replay-persistence-v0.1-result.json"
VERSION = "ls.replay_persistence.v0.1"
EVENT_VERSION = "ls.durable_event.v0.1"
REPORT_VERSION = "ls.replay_conformance_report.v0.1"
CHECKPOINT_VERSION = "ls.resume_checkpoint.v0.1"
REDACTED = "[REDACTED]"
EXPECTED_STAGES = [
    "TASK_ACCEPTED",
    "ORIENTATION_COORDINATED",
    "RECOGNITION_ALLOWED",
    "EVIDENCE_ALLOWED",
    "AUTHORIZATION_VERIFIED",
    "EXECUTION_COMMITTED",
    "EXECUTION_COMPLETED",
    "ARTIFACT_EXPORTED",
]


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON object required")
    return value


def text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_object(value: object) -> str:
    return "sha256:" + sha256(canonical(value))


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: dict[str, Any] = target
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def redact(value: Any, sensitive_keys: set[str]) -> tuple[Any, int]:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            if key.lower() in sensitive_keys:
                output[key] = REDACTED
                count += 1
            else:
                redacted_item, child_count = redact(item, sensitive_keys)
                output[key] = redacted_item
                count += child_count
        return output, count
    if isinstance(value, list):
        output_list = []
        count = 0
        for item in value:
            redacted_item, child_count = redact(item, sensitive_keys)
            output_list.append(redacted_item)
            count += child_count
        return output_list, count
    return copy.deepcopy(value), 0


def sensitive_values(value: Any, sensitive_keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in sensitive_keys:
                if isinstance(item, str):
                    found.append(item)
                else:
                    found.append(canonical(item))
            else:
                found.extend(sensitive_values(item, sensitive_keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(sensitive_values(item, sensitive_keys))
    return found


@dataclass(frozen=True)
class IntegrityScan:
    valid: bool
    reason_code: str
    valid_events: tuple[dict[str, Any], ...]
    parsed_events: int
    chain_head: str | None


class EventIdConflict(RuntimeError):
    pass


class JsonlEventStore:
    """Local fsync-backed append-only event stream with per-trail hash chaining."""

    def __init__(self, path: Path, trail_id: str, sensitive_keys: set[str]) -> None:
        self.path = path
        self.trail_id = trail_id
        self.sensitive_keys = sensitive_keys
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redactions_applied = 0

    def _parsed_lines(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                break
            if not isinstance(value, dict):
                break
            events.append(value)
        return events

    def append(self, template: Mapping[str, Any]) -> str:
        event_id = text(template.get("event_id"))
        event_type = text(template.get("event_type"))
        created_at = text(template.get("created_at"))
        payload = template.get("payload")
        if event_id is None or event_type is None or created_at is None or not isinstance(payload, dict):
            raise ValueError("event template is incomplete")

        source_payload_digest = digest_object(payload)
        existing = self._parsed_lines()
        for event in existing:
            if event.get("event_id") != event_id:
                continue
            same = (
                event.get("event_type") == event_type
                and event.get("created_at") == created_at
                and event.get("source_payload_digest") == source_payload_digest
            )
            if same:
                return "IDEMPOTENT"
            raise EventIdConflict(event_id)

        redacted_payload, redaction_count = redact(payload, self.sensitive_keys)
        previous = existing[-1] if existing else None
        event = {
            "schema_version": EVENT_VERSION,
            "trail_id": self.trail_id,
            "event_id": event_id,
            "sequence": len(existing),
            "event_type": event_type,
            "created_at": created_at,
            "parent_event_id": previous.get("event_id") if previous else None,
            "source_payload_digest": source_payload_digest,
            "payload_digest": digest_object(redacted_payload),
            "payload": redacted_payload,
            "previous_event_digest": previous.get("event_digest") if previous else None,
        }
        event["event_digest"] = digest_object(event)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.redactions_applied += redaction_count
        return "APPENDED"

    def rewrite_lines(self, lines: Sequence[str]) -> None:
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.path.open("rb") as stream:
            os.fsync(stream.fileno())

    def raw_text(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""


def recompute_event_digest(event: Mapping[str, Any]) -> str:
    payload = {key: copy.deepcopy(value) for key, value in event.items() if key != "event_digest"}
    return digest_object(payload)


def scan_integrity(path: Path, trail_id: str) -> IntegrityScan:
    if not path.exists():
        return IntegrityScan(False, "STREAM_MISSING", (), 0, None)
    valid: list[dict[str, Any]] = []
    parsed_events = 0
    previous_digest: str | None = None
    previous_event_id: str | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_index, raw in enumerate(lines):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return IntegrityScan(False, "CORRUPTED_TAIL", tuple(valid), parsed_events, previous_digest)
        if not isinstance(event, dict):
            return IntegrityScan(False, "EVENT_MALFORMED", tuple(valid), parsed_events, previous_digest)
        parsed_events += 1
        if event.get("schema_version") != EVENT_VERSION:
            return IntegrityScan(False, "EVENT_SCHEMA_INVALID", tuple(valid), parsed_events, previous_digest)
        if event.get("trail_id") != trail_id:
            return IntegrityScan(False, "TRAIL_BINDING_MISMATCH", tuple(valid), parsed_events, previous_digest)
        if event.get("sequence") != len(valid):
            return IntegrityScan(False, "SEQUENCE_MISMATCH", tuple(valid), parsed_events, previous_digest)
        if event.get("previous_event_digest") != previous_digest:
            return IntegrityScan(False, "HASH_CHAIN_MISMATCH", tuple(valid), parsed_events, previous_digest)
        if event.get("parent_event_id") != previous_event_id:
            return IntegrityScan(False, "PARENT_EVENT_MISMATCH", tuple(valid), parsed_events, previous_digest)
        if event.get("event_digest") != recompute_event_digest(event):
            return IntegrityScan(False, "EVENT_DIGEST_MISMATCH", tuple(valid), parsed_events, previous_digest)
        if event.get("payload_digest") != digest_object(event.get("payload")):
            return IntegrityScan(False, "PAYLOAD_DIGEST_MISMATCH", tuple(valid), parsed_events, previous_digest)
        valid.append(event)
        previous_digest = text(event.get("event_digest"))
        previous_event_id = text(event.get("event_id"))
    return IntegrityScan(True, "INTEGRITY_VALID", tuple(valid), parsed_events, previous_digest)


def next_stage(valid_events: Sequence[Mapping[str, Any]]) -> str | None:
    index = len(valid_events)
    return EXPECTED_STAGES[index] if index < len(EXPECTED_STAGES) else None


def make_checkpoint(
    trail_id: str,
    valid_events: Sequence[Mapping[str, Any]],
    chain_head: str | None,
    *,
    resume_allowed: bool,
) -> dict[str, Any] | None:
    stage = next_stage(valid_events)
    if stage is None:
        return None
    last = valid_events[-1] if valid_events else None
    payload = {
        "schema_version": CHECKPOINT_VERSION,
        "trail_id": trail_id,
        "last_valid_event_id": last.get("event_id") if last else None,
        "last_valid_sequence": last.get("sequence") if last else None,
        "next_expected_stage": stage,
        "source_chain_head": chain_head,
        "resume_allowed": resume_allowed,
    }
    payload["checkpoint_ref"] = "resume-checkpoint:" + sha256(canonical(payload))
    return payload


def semantic_replay(
    trail_id: str,
    scan: IntegrityScan,
    baseline: Mapping[str, str],
    *,
    append_conflict: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    valid_events = list(scan.valid_events)
    if append_conflict:
        checkpoint = make_checkpoint(trail_id, valid_events, scan.chain_head, resume_allowed=False)
        return {
            "classification": "REJECTED",
            "reason_code": "EVENT_ID_CONFLICT",
            "completion_state": "INVALID",
            "resume_allowed": False,
        }, checkpoint

    if not scan.valid:
        checkpoint = make_checkpoint(trail_id, valid_events, scan.chain_head, resume_allowed=False)
        return {
            "classification": "REJECTED",
            "reason_code": scan.reason_code,
            "completion_state": "INVALID",
            "resume_allowed": False,
        }, checkpoint

    event_types = [event.get("event_type") for event in valid_events]
    if event_types != EXPECTED_STAGES[: len(event_types)]:
        checkpoint = make_checkpoint(trail_id, valid_events, scan.chain_head, resume_allowed=False)
        return {
            "classification": "REJECTED",
            "reason_code": "STAGE_ORDER_INVALID",
            "completion_state": "INVALID",
            "resume_allowed": False,
        }, checkpoint

    non_allow_index: int | None = None
    for index, event in enumerate(valid_events):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            non_allow_index = index
            break
        event_type = event.get("event_type")
        allowed = True
        if event_type == "ORIENTATION_COORDINATED":
            allowed = payload.get("verdict") == "COORDINATED_ACTION_CANDIDATE"
        elif event_type == "RECOGNITION_ALLOWED":
            allowed = payload.get("decision") == "ALLOW"
        elif event_type == "EVIDENCE_ALLOWED":
            allowed = payload.get("decision") == "ALLOW"
        elif event_type == "AUTHORIZATION_VERIFIED":
            allowed = payload.get("valid") is True
        if not allowed:
            non_allow_index = index
            break

    if non_allow_index is not None and len(valid_events) > non_allow_index + 1:
        return {
            "classification": "REJECTED",
            "reason_code": "ACTION_AFTER_NON_ALLOW",
            "completion_state": "INVALID",
            "resume_allowed": False,
        }, None

    for event in valid_events:
        event_id = str(event.get("event_id"))
        expected_digest = baseline.get(event_id)
        if expected_digest is not None and event.get("source_payload_digest") != expected_digest:
            return {
                "classification": "DRIFTED",
                "reason_code": "BASELINE_PAYLOAD_DRIFT",
                "completion_state": "COMPLETE" if len(valid_events) == len(EXPECTED_STAGES) else "PARTIAL",
                "resume_allowed": False,
            }, None

    if len(valid_events) == len(EXPECTED_STAGES):
        return {
            "classification": "ADMISSIBLE",
            "reason_code": "PATH_ADMISSIBLE",
            "completion_state": "COMPLETE",
            "resume_allowed": False,
        }, None

    checkpoint = make_checkpoint(trail_id, valid_events, scan.chain_head, resume_allowed=True)
    return {
        "classification": "ADMISSIBLE",
        "reason_code": "PARTIAL_PATH_ADMISSIBLE",
        "completion_state": "PARTIAL",
        "resume_allowed": True,
    }, checkpoint


def effective_templates(
    base_events: Sequence[Mapping[str, Any]],
    overrides: Mapping[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for base_event in base_events:
        event_id = str(base_event.get("event_id"))
        override = overrides.get(event_id, {})
        if not isinstance(override, Mapping):
            raise ValueError(f"override for {event_id} must be an object")
        output.append(deep_merge(base_event, override))
    return output


def build_baseline(
    templates: Sequence[Mapping[str, Any]],
    overrides: Mapping[str, Any],
) -> dict[str, str]:
    baseline: dict[str, str] = {}
    for template in templates:
        event_id = text(template.get("event_id"))
        payload = template.get("payload")
        if event_id is None or not isinstance(payload, dict):
            raise ValueError("event template is incomplete")
        baseline[event_id] = digest_object(payload)
    for event_id, value in overrides.items():
        if not isinstance(event_id, str) or not isinstance(value, str):
            raise ValueError("baseline overrides must be string mappings")
        baseline[event_id] = value
    return baseline


def apply_reorder(path: Path, order: Sequence[int]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if sorted(order) != list(range(len(lines))):
        raise ValueError("reorder must be a complete permutation")
    path.write_text("\n".join(lines[index] for index in order) + "\n", encoding="utf-8")


def apply_tamper(path: Path, instruction: Mapping[str, Any]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    line_index = instruction.get("line_index")
    field_path = text(instruction.get("field_path"))
    if not isinstance(line_index, int) or not 0 <= line_index < len(lines) or field_path is None:
        raise ValueError("invalid tamper instruction")
    event = json.loads(lines[line_index])
    if not isinstance(event, dict):
        raise ValueError("tamper target must be an event object")
    set_path(event, field_path, instruction.get("value"))
    lines[line_index] = canonical(event)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_ref(report: Mapping[str, Any]) -> str:
    return "replay-report:" + sha256(canonical(report))


def run_case(
    manifest: Mapping[str, Any],
    case: Mapping[str, Any],
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    trail_id = text(manifest.get("trail_id"))
    base_events = manifest.get("events")
    sensitive = manifest.get("sensitive_keys")
    if trail_id is None or not isinstance(base_events, list) or not isinstance(sensitive, list):
        raise ValueError("manifest is incomplete")
    sensitive_keys = {str(item).lower() for item in sensitive}

    event_overrides = case.get("event_overrides", {})
    baseline_overrides = case.get("baseline_overrides", {})
    if not isinstance(event_overrides, Mapping) or not isinstance(baseline_overrides, Mapping):
        raise ValueError("case overrides must be objects")
    templates = effective_templates(base_events, event_overrides)
    baseline = build_baseline(templates, baseline_overrides)

    truncate_after = case.get("truncate_after")
    if truncate_after is not None:
        if not isinstance(truncate_after, int) or not 0 <= truncate_after <= len(templates):
            raise ValueError("truncate_after is invalid")
        templates = templates[:truncate_after]

    store = JsonlEventStore(root / "events.jsonl", trail_id, sensitive_keys)
    append_outcome = "APPENDED"
    for template in templates:
        append_outcome = store.append(template)

    duplicate_mode = case.get("append_duplicate")
    append_conflict = False
    if duplicate_mode == "same" and templates:
        append_outcome = store.append(templates[-1])
    elif duplicate_mode == "conflict" and templates:
        conflict = copy.deepcopy(templates[-1])
        payload = conflict.get("payload")
        if not isinstance(payload, dict):
            raise ValueError("duplicate conflict payload missing")
        payload["conflict_marker"] = "different-event-bytes"
        try:
            store.append(conflict)
        except EventIdConflict:
            append_outcome = "CONFLICT"
            append_conflict = True
        else:
            raise AssertionError("conflicting duplicate was accepted")
    elif duplicate_mode not in {"none", "same", "conflict"}:
        raise ValueError("unsupported append_duplicate mode")

    reorder = case.get("reorder")
    if reorder is not None:
        if not isinstance(reorder, list) or any(not isinstance(item, int) for item in reorder):
            raise ValueError("reorder must be an integer list")
        apply_reorder(store.path, reorder)

    tamper = case.get("tamper")
    if tamper is not None:
        if not isinstance(tamper, Mapping):
            raise ValueError("tamper must be an object")
        apply_tamper(store.path, tamper)

    corrupt_tail = case.get("corrupt_tail")
    if corrupt_tail is not None:
        if not isinstance(corrupt_tail, str):
            raise ValueError("corrupt_tail must be a string")
        with store.path.open("a", encoding="utf-8") as stream:
            stream.write(corrupt_tail + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    scan = scan_integrity(store.path, trail_id)
    semantic, checkpoint = semantic_replay(
        trail_id,
        scan,
        baseline,
        append_conflict=append_conflict,
    )

    raw_stream = store.raw_text()
    secrets: list[str] = []
    for template in templates:
        secrets.extend(sensitive_values(template.get("payload"), sensitive_keys))
    raw_sensitive_present = any(secret and secret in raw_stream for secret in secrets)

    conformance = {
        "schema_version": REPORT_VERSION,
        "trail_id": trail_id,
        "classification": semantic["classification"],
        "reason_code": semantic["reason_code"],
        "completion_state": semantic["completion_state"],
        "integrity_valid": scan.valid,
        "valid_prefix_events": len(scan.valid_events),
        "parsed_events": scan.parsed_events,
        "chain_head": scan.chain_head,
        "checkpoint_ref": checkpoint.get("checkpoint_ref") if checkpoint else None,
        "resume_allowed": semantic["resume_allowed"],
        "append_outcome": append_outcome,
        "persisted_events": len(store._parsed_lines()),
        "redactions_applied": store.redactions_applied,
        "privacy_status": "pass" if not raw_sensitive_present else "fail",
        "model_calls": 0,
        "tool_calls": 0,
        "effect_calls": 0,
    }
    conformance["report_ref"] = report_ref(conformance)

    observed = {
        "classification": semantic["classification"],
        "reason_code": semantic["reason_code"],
        "integrity_valid": scan.valid,
        "valid_prefix_events": len(scan.valid_events),
        "completion_state": semantic["completion_state"],
        "checkpoint_stage": checkpoint.get("next_expected_stage") if checkpoint else None,
        "resume_allowed": semantic["resume_allowed"],
        "persisted_events": len(store._parsed_lines()),
        "append_outcome": append_outcome,
        "redactions_applied": store.redactions_applied,
        "raw_sensitive_values_present": raw_sensitive_present,
        "model_calls": 0,
        "tool_calls": 0,
        "effect_calls": 0,
    }
    return observed, conformance, checkpoint


def validate(manifest_path: Path) -> dict[str, Any]:
    manifest = load(manifest_path)
    if manifest.get("contract_version") != VERSION:
        raise ValueError("manifest contract version mismatch")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) != len(set(cases)):
        raise ValueError("manifest cases must be a unique non-empty list")

    expected_cases = {
        "clean_replay",
        "drifted_baseline",
        "rejected_after_non_allow",
        "partial_resume",
        "reordered_stream",
        "tampered_event",
        "corrupted_tail",
        "redacted_sensitive_fields",
        "idempotent_duplicate_append",
        "conflicting_duplicate_event",
    }
    seen: set[str] = set()
    classifications: set[str] = set()
    reasons: set[str] = set()
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="ls-replay-persistence-") as temporary:
        root = Path(temporary)
        for index, filename in enumerate(cases):
            if not isinstance(filename, str) or not filename.endswith(".json"):
                raise ValueError(f"invalid case filename: {filename!r}")
            case = load(manifest_path.parent / filename)
            name = text(case.get("case"))
            expected = case.get("expected")
            if name is None or name in seen or not isinstance(expected, dict):
                raise ValueError(f"{filename}: invalid case metadata")
            seen.add(name)
            case_root = root / f"{index:02d}-{name}"
            case_root.mkdir(parents=True, exist_ok=True)
            observed, conformance, checkpoint = run_case(manifest, case, case_root)
            errors: list[str] = []
            if observed != expected:
                errors.append("observed result differs from expected")
            if observed["model_calls"] or observed["tool_calls"] or observed["effect_calls"]:
                errors.append("replay reran a model, tool, or effect")
            if observed["raw_sensitive_values_present"]:
                errors.append("raw sensitive value reached durable replay data")
            if observed["resume_allowed"] and observed["completion_state"] != "PARTIAL":
                errors.append("non-partial result became resumable")
            if observed["classification"] == "ADMISSIBLE" and not observed["integrity_valid"]:
                errors.append("integrity-invalid stream became admissible")
            classifications.add(observed["classification"])
            reasons.add(observed["reason_code"])
            results.append(
                {
                    "case": name,
                    "file": filename,
                    "passed": not errors,
                    "errors": errors,
                    "observed": observed,
                    "expected": expected,
                    "conformance_report": conformance,
                    "resume_checkpoint": checkpoint,
                }
            )

    if seen != expected_cases:
        raise ValueError(f"case set mismatch: {sorted(expected_cases - seen)}")
    required_reasons = {
        "PATH_ADMISSIBLE",
        "BASELINE_PAYLOAD_DRIFT",
        "ACTION_AFTER_NON_ALLOW",
        "PARTIAL_PATH_ADMISSIBLE",
        "SEQUENCE_MISMATCH",
        "EVENT_DIGEST_MISMATCH",
        "CORRUPTED_TAIL",
        "EVENT_ID_CONFLICT",
    }
    report = {
        "contract_version": VERSION,
        "event_version": EVENT_VERSION,
        "report_version": REPORT_VERSION,
        "checkpoint_version": CHECKPOINT_VERSION,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "classifications_covered": sorted(classifications),
        "reason_codes_covered": sorted(reasons),
        "boundary": {
            "replay_reruns_models": False,
            "replay_reruns_tools": False,
            "replay_reruns_effects": False,
            "corrupted_stream_can_be_admissible": False,
            "raw_sensitive_values_are_persisted": False,
            "distributed_transactional_storage_claimed": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and {"ADMISSIBLE", "DRIFTED", "REJECTED"}.issubset(classifications)
        and required_reasons.issubset(reasons)
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = validate(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(pretty(report), encoding="utf-8")
    print(pretty(report), end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
