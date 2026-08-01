from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


class TrustViolation(ValueError):
    """Raised when a dispatch, result, approval, or ledger rule is violated."""


@dataclass(frozen=True)
class DispatchReceipt:
    receipt_id: str
    parent_agent: str
    child_agent: str
    task: str
    constraints: tuple[str, ...]
    authority_scope: tuple[str, ...]
    sequence: int
    supersedes: str | None = None


@dataclass(frozen=True)
class ResultReceipt:
    receipt_id: str
    dispatch_id: str
    agent: str
    status: str
    summary_digest: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class ApprovalReceipt:
    receipt_id: str
    dispatch_id: str
    result_receipt_id: str
    effect: str
    approver: str
    reason: str


@dataclass(frozen=True)
class EffectDecision:
    allowed: bool
    reason: str
    dispatch_id: str
    effect: str


class TrustRuntime:
    """Small append-only trust layer for multi-agent work.

    The runtime does not execute external effects. It records who delegated work,
    validates who returned it, preserves recovery lineage, and decides whether an
    effect is admissible under the declared authority scope and human approvals.
    """

    DEFAULT_PROTECTED_EFFECTS = frozenset(
        {
            "deploy",
            "merge",
            "send_message",
            "purchase",
            "payment",
            "delete",
            "change_permissions",
        }
    )

    def __init__(self, protected_effects: Iterable[str] | None = None) -> None:
        configured_effects = (
            self.DEFAULT_PROTECTED_EFFECTS
            if protected_effects is None
            else protected_effects
        )
        self.protected_effects = frozenset(
            self._clean_identifier(effect, "protected_effect")
            for effect in configured_effects
        )
        self._dispatches: dict[str, DispatchReceipt] = {}
        self._results: dict[str, ResultReceipt] = {}
        self._result_by_dispatch: dict[str, str] = {}
        self._approvals: dict[tuple[str, str, str], ApprovalReceipt] = {}
        self._superseded_by: dict[str, str] = {}
        self._ledger: list[dict[str, Any]] = []

    @staticmethod
    def _canonical(value: Mapping[str, Any]) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @classmethod
    def _digest(cls, value: Mapping[str, Any]) -> str:
        return hashlib.sha256(cls._canonical(value)).hexdigest()

    @staticmethod
    def _clean_text(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise TrustViolation(f"{field} must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise TrustViolation(f"{field} must not be empty")
        return cleaned

    @classmethod
    def _clean_identifier(cls, value: str, field: str) -> str:
        """Normalize policy identifiers so casing cannot bypass a gate."""

        return cls._clean_text(value, field).casefold()

    @classmethod
    def _normalize_identifiers(
        cls,
        values: Sequence[str],
        field: str,
    ) -> tuple[str, ...]:
        normalized: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                raise TrustViolation(f"{field} entries must be strings")
            if value.strip():
                normalized.add(cls._clean_identifier(value, field))
        return tuple(sorted(normalized))

    def _append(self, event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        previous_hash = self._ledger[-1]["record_hash"] if self._ledger else "GENESIS"
        unsigned = {
            "offset": len(self._ledger) + 1,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_hash": previous_hash,
        }
        record = {**unsigned, "record_hash": self._digest(unsigned)}
        self._ledger.append(record)
        return dict(record)

    def issue_dispatch(
        self,
        *,
        parent_agent: str,
        child_agent: str,
        task: str,
        constraints: Sequence[str] = (),
        authority_scope: Sequence[str] = (),
        supersedes: str | None = None,
    ) -> DispatchReceipt:
        parent = self._clean_text(parent_agent, "parent_agent")
        child = self._clean_text(child_agent, "child_agent")
        normalized_task = self._clean_text(task, "task")
        normalized_constraints = tuple(
            sorted({item.strip() for item in constraints if item.strip()})
        )
        normalized_scope = self._normalize_identifiers(
            authority_scope,
            "authority_scope",
        )

        if supersedes is not None:
            previous = self._dispatches.get(supersedes)
            if previous is None:
                raise TrustViolation("superseded dispatch does not exist")
            if supersedes in self._superseded_by:
                raise TrustViolation("dispatch is already superseded")
            if supersedes in self._result_by_dispatch:
                raise TrustViolation("terminal dispatch cannot be superseded")
            if previous.task != normalized_task:
                raise TrustViolation("recovery must preserve the original task")
            if previous.constraints != normalized_constraints:
                raise TrustViolation("recovery must preserve the original constraints")
            if previous.authority_scope != normalized_scope:
                raise TrustViolation("recovery must preserve the original authority scope")

        payload: dict[str, Any] = {
            "parent_agent": parent,
            "child_agent": child,
            "task": normalized_task,
            "constraints": normalized_constraints,
            "authority_scope": normalized_scope,
            "sequence": len(self._dispatches) + 1,
            "supersedes": supersedes,
        }
        receipt_id = self._digest(payload)
        receipt = DispatchReceipt(receipt_id=receipt_id, **payload)
        self._dispatches[receipt_id] = receipt
        if supersedes is not None:
            self._superseded_by[supersedes] = receipt_id
        self._append("DISPATCH_ISSUED", asdict(receipt))
        return receipt

    def recover_dispatch(
        self,
        dispatch_id: str,
        *,
        replacement_agent: str,
        parent_agent: str = "Recovery coordinator",
    ) -> DispatchReceipt:
        original = self._dispatches.get(dispatch_id)
        if original is None:
            raise TrustViolation("dispatch does not exist")
        return self.issue_dispatch(
            parent_agent=parent_agent,
            child_agent=replacement_agent,
            task=original.task,
            constraints=original.constraints,
            authority_scope=original.authority_scope,
            supersedes=dispatch_id,
        )

    def submit_result(
        self,
        *,
        dispatch_id: str,
        agent: str,
        status: str,
        summary: str,
        evidence: Sequence[str] = (),
    ) -> ResultReceipt:
        dispatch = self._dispatches.get(dispatch_id)
        if dispatch is None:
            raise TrustViolation("dispatch does not exist")
        if dispatch_id in self._superseded_by:
            raise TrustViolation("superseded dispatch cannot accept a result")
        normalized_agent = self._clean_text(agent, "agent")
        if normalized_agent != dispatch.child_agent:
            raise TrustViolation("only the dispatched child agent may submit the result")
        if dispatch_id in self._result_by_dispatch:
            raise TrustViolation("dispatch already has a terminal result")

        normalized_status = status.strip().upper()
        if normalized_status not in {"COMPLETED", "FAILED", "BLOCKED"}:
            raise TrustViolation("status must be COMPLETED, FAILED, or BLOCKED")
        normalized_summary = self._clean_text(summary, "summary")
        normalized_evidence = tuple(
            sorted({item.strip() for item in evidence if item.strip()})
        )
        if normalized_status == "COMPLETED" and not normalized_evidence:
            raise TrustViolation(
                "completed results require at least one evidence reference"
            )

        payload = {
            "dispatch_id": dispatch_id,
            "agent": normalized_agent,
            "status": normalized_status,
            "summary_digest": hashlib.sha256(
                normalized_summary.encode("utf-8")
            ).hexdigest(),
            "evidence": normalized_evidence,
        }
        receipt_id = self._digest(payload)
        receipt = ResultReceipt(receipt_id=receipt_id, **payload)
        self._results[receipt_id] = receipt
        self._result_by_dispatch[dispatch_id] = receipt_id
        self._append("RESULT_RECORDED", asdict(receipt))
        return receipt

    def grant_human_approval(
        self,
        *,
        dispatch_id: str,
        effect: str,
        approver: str,
        reason: str,
    ) -> ApprovalReceipt:
        dispatch = self._dispatches.get(dispatch_id)
        if dispatch is None:
            raise TrustViolation("dispatch does not exist")
        if dispatch_id in self._superseded_by:
            raise TrustViolation("superseded dispatch cannot receive approval")

        result_receipt_id = self._result_by_dispatch.get(dispatch_id)
        result = self._results.get(result_receipt_id or "")
        if result is None or result.status != "COMPLETED":
            raise TrustViolation("human approval requires a completed result")

        normalized_effect = self._clean_identifier(effect, "effect")
        if normalized_effect not in dispatch.authority_scope:
            raise TrustViolation("approval effect is outside the delegated authority scope")

        payload = {
            "dispatch_id": dispatch_id,
            "result_receipt_id": result.receipt_id,
            "effect": normalized_effect,
            "approver": self._clean_text(approver, "approver"),
            "reason": self._clean_text(reason, "reason"),
        }
        receipt_id = self._digest(payload)
        receipt = ApprovalReceipt(receipt_id=receipt_id, **payload)
        self._approvals[
            (dispatch_id, result.receipt_id, normalized_effect)
        ] = receipt
        self._append("HUMAN_APPROVAL_RECORDED", asdict(receipt))
        return receipt

    def authorize_effect(
        self,
        *,
        dispatch_id: str,
        result_receipt_id: str,
        effect: str,
    ) -> EffectDecision:
        normalized_effect = self._clean_identifier(effect, "effect")
        dispatch = self._dispatches.get(dispatch_id)
        result = self._results.get(result_receipt_id)

        reason = "allowed"
        allowed = True
        if dispatch is None:
            allowed, reason = False, "unknown dispatch"
        elif dispatch_id in self._superseded_by:
            allowed, reason = False, "dispatch was superseded during recovery"
        elif result is None or result.dispatch_id != dispatch_id:
            allowed, reason = False, "result is not bound to this dispatch"
        elif result.status != "COMPLETED":
            allowed, reason = False, "result is not completed"
        elif normalized_effect not in dispatch.authority_scope:
            allowed, reason = False, "effect is outside the delegated authority scope"
        elif (
            normalized_effect in self.protected_effects
            and (
                dispatch_id,
                result_receipt_id,
                normalized_effect,
            )
            not in self._approvals
        ):
            allowed, reason = False, "protected effect requires human approval"

        decision = EffectDecision(
            allowed=allowed,
            reason=reason,
            dispatch_id=dispatch_id,
            effect=normalized_effect,
        )
        self._append(
            "EFFECT_ALLOWED" if allowed else "EFFECT_BLOCKED",
            asdict(decision),
        )
        return decision

    @property
    def dispatches(self) -> tuple[DispatchReceipt, ...]:
        return tuple(self._dispatches.values())

    @property
    def results(self) -> tuple[ResultReceipt, ...]:
        return tuple(self._results.values())

    @property
    def ledger(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(json.dumps(record)) for record in self._ledger)

    @classmethod
    def verify_records(cls, records: Sequence[Mapping[str, Any]]) -> bool:
        previous_hash = "GENESIS"
        for expected_offset, record in enumerate(records, start=1):
            unsigned = {
                "offset": record.get("offset"),
                "event_type": record.get("event_type"),
                "payload": record.get("payload"),
                "previous_hash": record.get("previous_hash"),
            }
            if unsigned["offset"] != expected_offset:
                return False
            if unsigned["previous_hash"] != previous_hash:
                return False
            if record.get("record_hash") != cls._digest(unsigned):
                return False
            previous_hash = str(record["record_hash"])
        return True

    def verify_ledger(self) -> bool:
        return self.verify_records(self._ledger)
