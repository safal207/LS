#!/usr/bin/env python3
"""Deterministic commit-before-effect reference controller for LS v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "commit-before-effect" / "manifest-v0.1.json"
OUTPUT = ROOT / "artifacts" / "commit-before-effect-v0.1-result.json"
VERSION = "ls.commit_before_effect.v0.1"
RECORD_VERSION = "ls.execution_record.v0.1"
STATES = {
    "RECEIVED",
    "VALIDATING",
    "HELD",
    "ACCEPTED",
    "COMMITTED",
    "EXECUTED",
    "REJECTED",
    "EXPIRED",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON object required")
    return value


def text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def digest_payload(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def parse_time(value: object) -> datetime:
    raw = text(value)
    if raw is None:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def unique_nonempty(values: object) -> bool:
    return (
        isinstance(values, list)
        and bool(values)
        and all(text(item) is not None for item in values)
        and len(values) == len(set(values))
    )


class AtomicExecutionJournal:
    """Small atomic local journal used for deterministic conformance tests."""

    def __init__(self, path: Path, *, write_error_on_committed: bool = False) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.write_error_on_committed = write_error_on_committed

    def _read_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("journal root must be an object")
        return value

    def load(self, execution_id: str) -> dict[str, Any] | None:
        value = self._read_all().get(execution_id)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("journal record must be an object")
        return value

    def save(self, record: Mapping[str, Any]) -> None:
        if record.get("state") == "COMMITTED" and self.write_error_on_committed:
            self.write_error_on_committed = False
            raise OSError("simulated atomic journal write error")
        records = self._read_all()
        records[str(record["execution_id"])] = copy.deepcopy(dict(record))
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(pretty(records), encoding="utf-8")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary.replace(self.path)


class IdempotentReviewEffect:
    """Harmless inspectable effect: one deterministic review-result JSON file."""

    def __init__(self, root: Path, journal: AtomicExecutionJournal) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal = journal
        self.execute_calls = 0
        self.every_call_observed_commit = True

    def _target(self, execution_id: str) -> Path:
        return self.root / f"{execution_id}.effect.json"

    def inspect(self, execution_id: str, action_digest: str) -> dict[str, Any] | None:
        target = self._target(execution_id)
        if not target.exists():
            return None
        value = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("effect receipt must be an object")
        if value.get("action_digest") != action_digest:
            raise ValueError("existing effect belongs to different action bytes")
        return value

    def execute(
        self,
        execution_id: str,
        action: Mapping[str, Any],
        action_digest: str,
        now: str,
    ) -> dict[str, Any]:
        committed = self.journal.load(execution_id)
        saw_commit = committed is not None and committed.get("state") == "COMMITTED"
        self.every_call_observed_commit = self.every_call_observed_commit and saw_commit
        if not saw_commit:
            raise RuntimeError("effect attempted before durable COMMITTED record")

        existing = self.inspect(execution_id, action_digest)
        if existing is not None:
            return existing

        self.execute_calls += 1
        target = self._target(execution_id)
        receipt = {
            "schema_version": "ls.effect_receipt.v0.1",
            "effect_ref": f"file:{target.name}",
            "execution_id": execution_id,
            "action_digest": action_digest,
            "payload_digest": digest_payload(action.get("payload", {})),
            "created_at": now,
        }
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(pretty(receipt))
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            inspected = self.inspect(execution_id, action_digest)
            if inspected is None:
                raise
            return inspected
        return receipt

    @property
    def effect_files(self) -> int:
        return len(list(self.root.glob("*.effect.json")))


class CommitBeforeEffectController:
    def __init__(self, journal: AtomicExecutionJournal, effect: IdempotentReviewEffect) -> None:
        self.journal = journal
        self.effect = effect

    @staticmethod
    def _action_digest(action: Mapping[str, Any]) -> str:
        return digest_payload(action)

    @staticmethod
    def _execution_id(bundle: Mapping[str, Any], action: Mapping[str, Any]) -> str:
        seed = {
            "authorization_ref": bundle.get("authorization_ref"),
            "idempotency_key": action.get("idempotency_key"),
        }
        return "execution:sha256:" + digest_payload(seed)

    @staticmethod
    def _transition(
        record: dict[str, Any],
        state: str,
        code: str,
        now: str,
        detail: str,
        *,
        effect_attempted: bool = False,
    ) -> dict[str, Any]:
        if state not in STATES:
            raise ValueError(f"unsupported execution state: {state}")
        transitions = list(record.get("transitions", []))
        transitions.append(
            {
                "sequence": len(transitions),
                "state": state,
                "decision_code": code,
                "created_at": now,
                "detail": detail,
                "effect_attempted": effect_attempted,
            }
        )
        updated = copy.deepcopy(record)
        updated["state"] = state
        updated["decision_code"] = code
        updated["updated_at"] = now
        updated["transitions"] = transitions
        if state == "COMMITTED":
            updated["committed_at"] = now
            updated["execution_authorized"] = True
        if state == "EXECUTED":
            updated["executed_at"] = now
            updated["effect_attempted"] = True
            updated["effect_succeeded"] = True
            updated["execution_authorized"] = True
        return updated

    def _new_record(
        self,
        bundle: Mapping[str, Any],
        action: Mapping[str, Any],
        now: str,
    ) -> dict[str, Any]:
        action_digest = self._action_digest(action)
        execution_id = self._execution_id(bundle, action)
        record = {
            "schema_version": RECORD_VERSION,
            "execution_id": execution_id,
            "task_id": bundle.get("task_id"),
            "trail_id": bundle.get("trail_id"),
            "action_id": action.get("action_id"),
            "action_ref": action.get("action_ref"),
            "action_digest": action_digest,
            "authorization_ref": bundle.get("authorization_ref"),
            "authorization_nonce": bundle.get("nonce"),
            "verifier_result_ref": bundle.get("verifier_result_ref"),
            "state": "RECEIVED",
            "decision_code": "RECEIVED",
            "actor": "runtime:ls",
            "created_at": now,
            "updated_at": now,
            "committed_at": None,
            "executed_at": None,
            "effect_ref": None,
            "effect_attempted": False,
            "effect_succeeded": None,
            "execution_authorized": False,
            "transitions": [],
            "error": None,
        }
        return self._transition(record, "RECEIVED", "RECEIVED", now, "action received")

    @staticmethod
    def _validate_bundle_and_action(
        bundle: Mapping[str, Any],
        action: Mapping[str, Any],
        now: str,
    ) -> tuple[str | None, str | None]:
        if bundle.get("valid") is not True:
            return "REJECT_INVALID_AUTHORIZATION", "bundle verification is not valid"
        if bundle.get("commit_before_effect_eligible") is not True:
            return "REJECT_INVALID_AUTHORIZATION", "bundle is not commit eligible"
        if bundle.get("execution_authorized") is not False:
            return "REJECT_INVALID_AUTHORIZATION", "upstream bundle claimed execution authority"
        if text(bundle.get("verifier_result_ref")) is None:
            return "REJECT_INVALID_AUTHORIZATION", "verifier result reference is missing"
        if text(bundle.get("authorization_ref")) is None or text(bundle.get("nonce")) is None:
            return "REJECT_INVALID_AUTHORIZATION", "authorization identity is incomplete"
        if not unique_nonempty(bundle.get("scope")) or not unique_nonempty(action.get("scope")):
            return "REJECT_POLICY", "scope is incomplete"
        if action.get("action_ref") != bundle.get("action_ref"):
            return "REJECT_POLICY", "action reference does not match bundle"
        if action.get("candidate_digest") != bundle.get("candidate_digest"):
            return "REJECT_POLICY", "candidate binding does not match bundle"
        if action.get("scope") != bundle.get("scope"):
            return "REJECT_POLICY", "action scope does not match bundle"
        required_action = (
            "action_id",
            "action_ref",
            "candidate_digest",
            "idempotency_key",
            "requested_at",
            "expires_at",
        )
        if any(text(action.get(key)) is None for key in required_action):
            return "REJECT_POLICY", "protected action is incomplete"
        try:
            current = parse_time(now)
            bundle_expiry = parse_time(bundle.get("expires_at"))
            action_expiry = parse_time(action.get("expires_at"))
        except (TypeError, ValueError):
            return "REJECT_POLICY", "invalid expiry window"
        if current > bundle_expiry or current > action_expiry:
            return "TTL_EXPIRED", "bundle or action has expired"
        return None, None

    def run(
        self,
        bundle: Mapping[str, Any],
        action: Mapping[str, Any],
        *,
        now: str,
        preconditions_met: bool,
        interrupt_after_commit: bool = False,
        interrupt_after_effect: bool = False,
    ) -> tuple[dict[str, Any], bool, str | None]:
        execution_id = self._execution_id(bundle, action)
        action_digest = self._action_digest(action)
        prior = self.journal.load(execution_id)
        if prior is not None:
            if prior.get("action_digest") != action_digest:
                rejected_record = self._transition(
                    prior,
                    "REJECTED",
                    "REJECT_STATE_CONFLICT",
                    now,
                    "idempotency identity was rebound to different action bytes",
                )
                rejected_record["execution_authorized"] = False
                self.journal.save(rejected_record)
                return rejected_record, False, None
            if prior.get("state") == "EXECUTED":
                return prior, True, "completed_retry"
            if prior.get("state") == "COMMITTED":
                return self.recover(bundle, action, now=now)

        record = self._new_record(bundle, action, now)
        self.journal.save(record)
        record = self._transition(record, "VALIDATING", "VALIDATING", now, "validating bundle and action")
        self.journal.save(record)

        invalid_code, invalid_detail = self._validate_bundle_and_action(bundle, action, now)
        if invalid_code == "TTL_EXPIRED":
            record = self._transition(record, "EXPIRED", "TTL_EXPIRED", now, invalid_detail or "expired")
            record["execution_authorized"] = False
            self.journal.save(record)
            return record, False, None
        if invalid_code is not None:
            record = self._transition(record, "REJECTED", invalid_code, now, invalid_detail or "rejected")
            record["execution_authorized"] = False
            self.journal.save(record)
            return record, False, None

        mature_after = action.get("mature_after")
        mature = True
        if mature_after is not None:
            try:
                mature = parse_time(now) >= parse_time(mature_after)
            except (TypeError, ValueError):
                mature = False
        if not preconditions_met or not mature:
            record = self._transition(
                record,
                "HELD",
                "DEFER_PENDING_CONTEXT",
                now,
                "preconditions or maturity boundary not satisfied",
            )
            record["execution_authorized"] = False
            self.journal.save(record)
            return record, False, None

        record = self._transition(record, "ACCEPTED", "PERMIT_OK", now, "all pre-commit checks passed")
        self.journal.save(record)
        committed = self._transition(record, "COMMITTED", "COMMIT_READY", now, "durable execution permit committed")
        try:
            self.journal.save(committed)
        except OSError as exc:
            rejected = self._transition(
                record,
                "REJECTED",
                "COMMIT_WRITE_ERROR",
                now,
                "durable commit could not be persisted",
            )
            rejected["execution_authorized"] = False
            rejected["error"] = str(exc)
            self.journal.save(rejected)
            return rejected, False, None

        if interrupt_after_commit:
            return committed, False, "after_commit"

        receipt = self.effect.execute(execution_id, action, action_digest, now)
        if interrupt_after_effect:
            return committed, False, "after_effect"

        executed = self._transition(
            committed,
            "EXECUTED",
            "COMMIT_EXECUTED",
            now,
            "effect executed after durable commit",
            effect_attempted=True,
        )
        executed["effect_ref"] = receipt["effect_ref"]
        self.journal.save(executed)
        return executed, False, None

    def recover(
        self,
        bundle: Mapping[str, Any],
        action: Mapping[str, Any],
        *,
        now: str,
    ) -> tuple[dict[str, Any], bool, str | None]:
        execution_id = self._execution_id(bundle, action)
        action_digest = self._action_digest(action)
        record = self.journal.load(execution_id)
        if record is None:
            return self.run(bundle, action, now=now, preconditions_met=True)
        if record.get("action_digest") != action_digest:
            rejected = self._transition(
                record,
                "REJECTED",
                "REJECT_STATE_CONFLICT",
                now,
                "recovery action bytes differ from committed action",
            )
            rejected["execution_authorized"] = False
            self.journal.save(rejected)
            return rejected, False, None
        if record.get("state") == "EXECUTED":
            return record, True, "completed_retry"
        if record.get("state") != "COMMITTED":
            return self.run(bundle, action, now=now, preconditions_met=True)

        existing = self.effect.inspect(execution_id, action_digest)
        if existing is not None:
            executed = self._transition(
                record,
                "EXECUTED",
                "RECOVERED_EXISTING_EFFECT",
                now,
                "existing idempotent effect inspected after restart",
                effect_attempted=True,
            )
            executed["effect_ref"] = existing["effect_ref"]
            self.journal.save(executed)
            return executed, True, "after_effect"

        receipt = self.effect.execute(execution_id, action, action_digest, now)
        executed = self._transition(
            record,
            "EXECUTED",
            "RECOVERED_AFTER_COMMIT",
            now,
            "committed execution resumed and effect completed",
            effect_attempted=True,
        )
        executed["effect_ref"] = receipt["effect_ref"]
        self.journal.save(executed)
        return executed, False, "after_commit"


def summarize(
    record: Mapping[str, Any],
    effect: IdempotentReviewEffect,
    *,
    reused_receipt: bool,
    recovery_mode: str | None,
    reason_override: str | None = None,
) -> dict[str, Any]:
    transitions = [str(item.get("state")) for item in record.get("transitions", [])]
    committed = "COMMITTED" in transitions
    final_state = str(record.get("state"))
    reason = reason_override or str(record.get("decision_code"))
    return {
        "outcome": final_state,
        "reason_code": reason,
        "final_state": final_state,
        "transitions": transitions,
        "durable_commit_before_effect": (
            committed
            and effect.every_call_observed_commit
            and (effect.execute_calls > 0 or final_state == "EXECUTED")
        ),
        "effect_calls": effect.execute_calls,
        "effect_files": effect.effect_files,
        "execution_authorized": record.get("execution_authorized") is True,
        "reused_receipt": reused_receipt,
        "recovery_mode": recovery_mode,
    }


def run_case(base: Mapping[str, Any], case: Mapping[str, Any], root: Path) -> dict[str, Any]:
    overrides = case.get("overrides", {})
    if not isinstance(overrides, Mapping):
        raise ValueError("case overrides must be an object")
    payload = deep_merge(base, overrides)
    bundle = payload.get("verified_bundle")
    action = payload.get("action")
    now = text(payload.get("current_time"))
    if not isinstance(bundle, dict) or not isinstance(action, dict) or now is None:
        raise ValueError("case payload is incomplete")

    journal = AtomicExecutionJournal(
        root / "journal.json",
        write_error_on_committed=case.get("journal_write_error") is True,
    )
    effect = IdempotentReviewEffect(root / "effects", journal)
    controller = CommitBeforeEffectController(journal, effect)
    mode = case.get("mode")
    preconditions_met = case.get("preconditions_met") is True

    if mode == "run":
        record, reused, recovery = controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )
        return summarize(record, effect, reused_receipt=reused, recovery_mode=recovery)

    if mode == "run_twice":
        first, _, _ = controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )
        if first.get("state") != "EXECUTED":
            return summarize(first, effect, reused_receipt=False, recovery_mode=None)
        second, reused, recovery = controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )
        return summarize(
            second,
            effect,
            reused_receipt=reused,
            recovery_mode=recovery,
            reason_override="PRIOR_RECEIPT_REUSED",
        )

    if mode == "recover_after_commit":
        committed, _, _ = controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
            interrupt_after_commit=True,
        )
        if committed.get("state") != "COMMITTED":
            return summarize(committed, effect, reused_receipt=False, recovery_mode=None)
        recovered, reused, recovery = CommitBeforeEffectController(journal, effect).recover(
            bundle,
            action,
            now=now,
        )
        return summarize(recovered, effect, reused_receipt=reused, recovery_mode=recovery)

    if mode == "recover_after_effect":
        committed, _, _ = controller.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
            interrupt_after_effect=True,
        )
        if committed.get("state") != "COMMITTED":
            return summarize(committed, effect, reused_receipt=False, recovery_mode=None)
        recovered, reused, recovery = CommitBeforeEffectController(journal, effect).recover(
            bundle,
            action,
            now=now,
        )
        return summarize(recovered, effect, reused_receipt=reused, recovery_mode=recovery)

    raise ValueError(f"unsupported case mode: {mode!r}")


def validate_record(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != RECORD_VERSION:
        errors.append("execution record version mismatch")
    if record.get("state") not in STATES:
        errors.append("unsupported final state")
    transitions = record.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        errors.append("execution transitions missing")
        return errors
    sequences = [item.get("sequence") for item in transitions if isinstance(item, dict)]
    if sequences != list(range(len(transitions))):
        errors.append("transition sequence is not contiguous")
    if transitions[-1].get("state") != record.get("state"):
        errors.append("final transition does not match record state")
    states = [item.get("state") for item in transitions]
    if "EXECUTED" in states:
        if "COMMITTED" not in states or states.index("COMMITTED") > states.index("EXECUTED"):
            errors.append("EXECUTED appeared before COMMITTED")
        if record.get("committed_at") is None or record.get("executed_at") is None:
            errors.append("executed record lacks timestamps")
    if record.get("state") in {"HELD", "REJECTED", "EXPIRED"}:
        if record.get("effect_attempted") is True or record.get("execution_authorized") is True:
            errors.append("terminal pre-effect state attempted or authorized effect")
    return errors


def validate(manifest_path: Path) -> dict[str, Any]:
    fixture = load(manifest_path)
    if fixture.get("contract_version") != VERSION:
        raise ValueError("manifest contract version mismatch")
    base = fixture.get("base")
    names = fixture.get("cases")
    if not isinstance(base, dict):
        raise ValueError("manifest base must be an object")
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError("manifest cases must be a unique non-empty list")

    expected_cases = {
        "successful_execution",
        "hold_pending_preconditions",
        "expired_action",
        "scope_mismatch",
        "journal_error",
        "duplicate_retry",
        "interrupted_after_commit",
        "interrupted_after_effect",
    }
    seen: set[str] = set()
    reasons: set[str] = set()
    final_states: set[str] = set()
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="ls-commit-before-effect-") as temporary:
        temporary_root = Path(temporary)
        for index, filename in enumerate(names):
            if not isinstance(filename, str) or not filename.endswith(".json"):
                raise ValueError(f"invalid case filename: {filename!r}")
            case = load(manifest_path.parent / filename)
            name = text(case.get("case"))
            expected = case.get("expected")
            if name is None or name in seen or not isinstance(expected, dict):
                raise ValueError(f"{filename}: invalid case metadata")
            seen.add(name)
            case_root = temporary_root / f"{index:02d}-{name}"
            case_root.mkdir(parents=True, exist_ok=True)
            observed = run_case(base, case, case_root)
            errors = []
            if observed != expected:
                errors.append("observed result differs from expected")
            if observed["final_state"] in {"HELD", "REJECTED", "EXPIRED"}:
                if observed["effect_calls"] != 0 or observed["effect_files"] != 0:
                    errors.append("pre-effect terminal state produced an effect")
                if observed["execution_authorized"]:
                    errors.append("pre-effect terminal state authorized execution")
            if observed["final_state"] == "EXECUTED":
                if not observed["durable_commit_before_effect"]:
                    errors.append("effect was not proven after durable commit")
                if observed["effect_calls"] != 1 or observed["effect_files"] != 1:
                    errors.append("executed case did not produce exactly one local effect")
            reasons.add(observed["reason_code"])
            final_states.add(observed["final_state"])
            results.append(
                {
                    "case": name,
                    "file": filename,
                    "passed": not errors,
                    "errors": errors,
                    "observed": observed,
                    "expected": expected,
                }
            )

    if seen != expected_cases:
        raise ValueError(f"case set mismatch: {sorted(expected_cases - seen)}")
    required_reasons = {
        "COMMIT_EXECUTED",
        "DEFER_PENDING_CONTEXT",
        "TTL_EXPIRED",
        "REJECT_POLICY",
        "COMMIT_WRITE_ERROR",
        "PRIOR_RECEIPT_REUSED",
        "RECOVERED_AFTER_COMMIT",
        "RECOVERED_EXISTING_EFFECT",
    }
    report = {
        "contract_version": VERSION,
        "record_version": RECORD_VERSION,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "final_states_covered": sorted(final_states),
        "reason_codes_covered": sorted(reasons),
        "boundary": {
            "effect_before_durable_commit": False,
            "pre_effect_terminal_state_can_execute": False,
            "completed_retry_can_duplicate_effect": False,
            "recovery_executes_without_inspection": False,
            "universal_distributed_exactly_once_claimed": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and {"EXECUTED", "HELD", "REJECTED", "EXPIRED"}.issubset(final_states)
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
