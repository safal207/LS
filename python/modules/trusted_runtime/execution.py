from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Protocol

from .authorization import (
    AuthorizationBundle,
    AuthorizationExpiredError,
    AuthorizationReplayError,
    InMemoryNonceStore,
    parse_datetime,
    verify_authorization_bundle_files,
)
from .contracts import CognitiveTrail, ReusableArtifact, TrailEvent, TrailEventType


EXECUTION_RECORD_VERSION = "trusted_runtime.execution_record.v0.1"


class ExecutionState(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    HELD = "HELD"
    ACCEPTED = "ACCEPTED"
    COMMITTED = "COMMITTED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class CaPUDecisionCode(str, Enum):
    PERMIT_OK = "PERMIT_OK"
    REJECT_INVALID_CAUSE = "REJECT_INVALID_CAUSE"
    REJECT_POLICY = "REJECT_POLICY"
    REJECT_CAPACITY_LIMIT = "REJECT_CAPACITY_LIMIT"
    REJECT_CAUSAL_ORDER = "REJECT_CAUSAL_ORDER"
    REJECT_STATE_CONFLICT = "REJECT_STATE_CONFLICT"
    DEFER_PENDING_CONTEXT = "DEFER_PENDING_CONTEXT"
    TTL_EXPIRED = "TTL_EXPIRED"
    ABORT_INTERNAL_ERROR = "ABORT_INTERNAL_ERROR"
    COMMIT_EXECUTED = "COMMIT_EXECUTED"
    COMMIT_NO_EFFECT = "COMMIT_NO_EFFECT"


class ExecutionControlError(RuntimeError):
    """Base error for commit-before-effect execution control."""


class ExecutionControlDisabledError(ExecutionControlError):
    """Raised when an optional execution-control adapter is disabled."""


class ExecutionControlUnavailableError(ExecutionControlError):
    """Raised when an execution-control backend is unavailable."""


class ExecutionAuthorizationError(ExecutionControlError):
    """Raised when a request lacks a valid authorization bundle."""


class ExecutionStateConflictError(ExecutionControlError):
    """Raised when an idempotency key is rebound to different inputs."""


class DurableCommitError(ExecutionControlError):
    """Raised when durable commit fails before an effect is invoked."""

    def __init__(self, message: str, record: "ExecutionRecord") -> None:
        super().__init__(message)
        self.record = record


class ExecutionInterrupted(ExecutionControlError):
    """Synthetic crash boundary used by deterministic recovery fixtures."""

    def __init__(self, boundary: str, record: "ExecutionRecord") -> None:
        super().__init__(f"execution interrupted at {boundary}")
        self.boundary = boundary
        self.record = record


class EffectExecutionError(ExecutionControlError):
    """Raised after a committed effect attempt fails."""

    def __init__(self, message: str, record: "ExecutionRecord") -> None:
        super().__init__(message)
        self.record = record


@dataclass(frozen=True)
class ProtectedAction:
    action_id: str
    action_ref: str
    scope: tuple[str, ...]
    payload: Mapping[str, Any]
    idempotency_key: str
    requested_at: str
    mature_after: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(
            (self.action_id, self.action_ref, self.idempotency_key, self.requested_at)
        ):
            raise ValueError("protected action identifiers must not be empty")
        if not self.scope:
            raise ValueError("protected action requires a non-empty scope")
        if len(self.scope) != len(set(self.scope)):
            raise ValueError("protected action scope must be unique")
        requested = parse_datetime(self.requested_at)
        if self.mature_after is not None:
            parse_datetime(self.mature_after)
        if self.expires_at is not None:
            expires = parse_datetime(self.expires_at)
            if expires <= requested:
                raise ValueError("protected action expires_at must follow requested_at")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ProtectedAction":
        return cls(
            action_id=str(payload["action_id"]),
            action_ref=str(payload["action_ref"]),
            scope=tuple(str(value) for value in payload["scope"]),
            payload=dict(payload.get("payload", {})),
            idempotency_key=str(payload["idempotency_key"]),
            requested_at=str(payload["requested_at"]),
            mature_after=(
                str(payload["mature_after"])
                if payload.get("mature_after") is not None
                else None
            ),
            expires_at=(
                str(payload["expires_at"])
                if payload.get("expires_at") is not None
                else None
            ),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_ref": self.action_ref,
            "scope": list(self.scope),
            "payload": dict(self.payload),
            "idempotency_key": self.idempotency_key,
            "requested_at": self.requested_at,
            "mature_after": self.mature_after,
            "expires_at": self.expires_at,
            "metadata": dict(self.metadata),
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            canonical_json(self.to_dict()).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class ExecutionTransition:
    sequence: int
    state: ExecutionState
    event_type: str
    decision_code: CaPUDecisionCode
    created_at: str
    actor: str
    detail: str
    effect_attempted: bool = False

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("execution transition sequence must be non-negative")
        if not all((self.event_type, self.created_at, self.actor, self.detail)):
            raise ValueError("execution transition fields must not be empty")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ExecutionTransition":
        return cls(
            sequence=int(payload["sequence"]),
            state=ExecutionState(payload["state"]),
            event_type=str(payload["event_type"]),
            decision_code=CaPUDecisionCode(payload["decision_code"]),
            created_at=str(payload["created_at"]),
            actor=str(payload["actor"]),
            detail=str(payload["detail"]),
            effect_attempted=bool(payload.get("effect_attempted", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "state": self.state.value,
            "event_type": self.event_type,
            "decision_code": self.decision_code.value,
            "created_at": self.created_at,
            "actor": self.actor,
            "detail": self.detail,
            "effect_attempted": self.effect_attempted,
        }


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    task_id: str
    trail_id: str
    action_id: str
    action_ref: str
    action_digest: str
    authorization_ref: str
    authorization_nonce: str
    state: ExecutionState
    decision_code: CaPUDecisionCode
    actor: str
    created_at: str
    updated_at: str
    committed_at: Optional[str]
    executed_at: Optional[str]
    effect_ref: Optional[str]
    effect_attempted: bool
    effect_succeeded: Optional[bool]
    transitions: tuple[ExecutionTransition, ...]
    error: Optional[str] = None
    schema_version: str = EXECUTION_RECORD_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTION_RECORD_VERSION:
            raise ValueError(f"unsupported execution record version: {self.schema_version}")
        required = (
            self.execution_id,
            self.task_id,
            self.trail_id,
            self.action_id,
            self.action_ref,
            self.action_digest,
            self.authorization_ref,
            self.authorization_nonce,
            self.actor,
            self.created_at,
            self.updated_at,
        )
        if not all(required):
            raise ValueError("execution record identifiers must not be empty")
        if not self.transitions:
            raise ValueError("execution record requires transitions")
        sequences = [transition.sequence for transition in self.transitions]
        if sequences != list(range(len(sequences))):
            raise ValueError("execution transition sequence must be contiguous")
        if self.transitions[-1].state is not self.state:
            raise ValueError("execution record state must match its final transition")
        if self.state is ExecutionState.COMMITTED and self.committed_at is None:
            raise ValueError("COMMITTED record requires committed_at")
        if self.state is ExecutionState.EXECUTED:
            if self.committed_at is None or self.executed_at is None:
                raise ValueError("EXECUTED record requires commit and execution timestamps")
            if not self.effect_attempted:
                raise ValueError("EXECUTED record must indicate an effect attempt")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ExecutionRecord":
        return cls(
            execution_id=str(payload["execution_id"]),
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            action_id=str(payload["action_id"]),
            action_ref=str(payload["action_ref"]),
            action_digest=str(payload["action_digest"]),
            authorization_ref=str(payload["authorization_ref"]),
            authorization_nonce=str(payload["authorization_nonce"]),
            state=ExecutionState(payload["state"]),
            decision_code=CaPUDecisionCode(payload["decision_code"]),
            actor=str(payload["actor"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            committed_at=payload.get("committed_at"),
            executed_at=payload.get("executed_at"),
            effect_ref=payload.get("effect_ref"),
            effect_attempted=bool(payload.get("effect_attempted", False)),
            effect_succeeded=payload.get("effect_succeeded"),
            transitions=tuple(
                ExecutionTransition.from_mapping(item)
                for item in payload["transitions"]
            ),
            error=payload.get("error"),
            schema_version=str(
                payload.get("schema_version", EXECUTION_RECORD_VERSION)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "action_id": self.action_id,
            "action_ref": self.action_ref,
            "action_digest": self.action_digest,
            "authorization_ref": self.authorization_ref,
            "authorization_nonce": self.authorization_nonce,
            "state": self.state.value,
            "decision_code": self.decision_code.value,
            "actor": self.actor,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "committed_at": self.committed_at,
            "executed_at": self.executed_at,
            "effect_ref": self.effect_ref,
            "effect_attempted": self.effect_attempted,
            "effect_succeeded": self.effect_succeeded,
            "transitions": [transition.to_dict() for transition in self.transitions],
            "error": self.error,
        }


@dataclass(frozen=True)
class EffectReceipt:
    effect_ref: str
    effect_digest: str
    created_at: str
    no_effect: bool = False

    def __post_init__(self) -> None:
        if not all((self.effect_ref, self.effect_digest, self.created_at)):
            raise ValueError("effect receipt fields must not be empty")


class ExecutionJournal(Protocol):
    def load(self, execution_id: str) -> Optional[ExecutionRecord]:
        ...

    def save(self, record: ExecutionRecord) -> None:
        ...


class EffectExecutor(Protocol):
    def inspect(
        self,
        execution_id: str,
        action: ProtectedAction,
    ) -> Optional[EffectReceipt]:
        ...

    def execute(
        self,
        execution_id: str,
        action: ProtectedAction,
        now: str,
    ) -> EffectReceipt:
        ...


class InMemoryExecutionJournal:
    def __init__(self) -> None:
        self._records: MutableMapping[str, ExecutionRecord] = {}
        self.fail_next_save = False

    def load(self, execution_id: str) -> Optional[ExecutionRecord]:
        return self._records.get(execution_id)

    def save(self, record: ExecutionRecord) -> None:
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("simulated durable commit failure")
        self._records[record.execution_id] = record


class JsonFileExecutionJournal:
    """Atomic JSON journal used by local demos and crash fixtures."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, execution_id: str) -> Optional[ExecutionRecord]:
        payload = self._read_all().get(execution_id)
        return ExecutionRecord.from_mapping(payload) if payload is not None else None

    def save(self, record: ExecutionRecord) -> None:
        records = self._read_all()
        records[record.execution_id] = record.to_dict()
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(pretty_json(records), encoding="utf-8")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        temporary.replace(self.path)

    def _read_all(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("execution journal root must be an object")
        return payload


class ReviewResultFileExecutor:
    """Idempotent harmless effect: write one review-result JSON file."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.execute_calls = 0

    def inspect(
        self,
        execution_id: str,
        action: ProtectedAction,
    ) -> Optional[EffectReceipt]:
        target = self._target(execution_id)
        if not target.exists():
            return None
        content = target.read_text(encoding="utf-8")
        payload = json.loads(content)
        if payload.get("action_digest") != action.digest:
            raise ExecutionStateConflictError(
                "existing effect belongs to a different action digest"
            )
        return EffectReceipt(
            effect_ref=f"file:{target}",
            effect_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            created_at=str(payload["created_at"]),
        )

    def execute(
        self,
        execution_id: str,
        action: ProtectedAction,
        now: str,
    ) -> EffectReceipt:
        existing = self.inspect(execution_id, action)
        if existing is not None:
            return existing
        self.execute_calls += 1
        target = self._target(execution_id)
        content = pretty_json(
            {
                "execution_id": execution_id,
                "action_id": action.action_id,
                "action_ref": action.action_ref,
                "action_digest": action.digest,
                "created_at": now,
                "review_result": dict(action.payload),
            }
        )
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            recovered = self.inspect(execution_id, action)
            if recovered is None:
                raise ExecutionStateConflictError("effect file exists but is unreadable")
            return recovered
        return EffectReceipt(
            effect_ref=f"file:{target}",
            effect_digest=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            created_at=now,
        )

    def _target(self, execution_id: str) -> Path:
        return self.root / f"{execution_id.replace(':', '-')}.review.json"


class DeterministicExecutionController:
    """Reference CaPU state machine with durable commit before every effect."""

    def __init__(
        self,
        journal: ExecutionJournal,
        executor: EffectExecutor,
        *,
        actor: str = "adapter:deterministic-capu",
        nonce_store: Optional[InMemoryNonceStore] = None,
    ) -> None:
        if not actor:
            raise ValueError("execution controller actor must not be empty")
        self.journal = journal
        self.executor = executor
        self.actor = actor
        self.nonce_store = nonce_store or InMemoryNonceStore()
        self._lock = threading.RLock()

    def run(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
        interrupt_after_commit: bool = False,
        interrupt_after_effect: bool = False,
    ) -> ExecutionRecord:
        with self._lock:
            execution_id = execution_ref(bundle, action)
            existing = self.journal.load(execution_id)
            if existing is not None:
                self._validate_existing(existing, bundle, action)
                return self._resume(
                    existing,
                    bundle,
                    action,
                    now=now,
                    preconditions_met=preconditions_met,
                    interrupt_after_effect=interrupt_after_effect,
                )

            record = self._new_record(execution_id, bundle, action, now)
            record = self._transition(
                record,
                ExecutionState.VALIDATING,
                "gate.validating",
                CaPUDecisionCode.PERMIT_OK,
                now,
                "validating authorization bundle and action scope",
            )
            rejection = self._validate_new_request(record, bundle, action, now)
            if rejection is not None:
                self.journal.save(rejection)
                return rejection

            maturity = self._maturity_state(action, now, preconditions_met)
            if maturity is ExecutionState.EXPIRED:
                expired = self._transition(
                    record,
                    ExecutionState.EXPIRED,
                    "incubator.expire",
                    CaPUDecisionCode.TTL_EXPIRED,
                    now,
                    "action expired before commit",
                )
                self.journal.save(expired)
                return expired
            if maturity is ExecutionState.HELD:
                held = self._transition(
                    record,
                    ExecutionState.HELD,
                    "gate.hold",
                    CaPUDecisionCode.DEFER_PENDING_CONTEXT,
                    now,
                    "action is valid but maturity or preconditions are unresolved",
                )
                self.journal.save(held)
                return held

            accepted = self._transition(
                record,
                ExecutionState.ACCEPTED,
                "gate.accept",
                CaPUDecisionCode.PERMIT_OK,
                now,
                "authorization, scope, maturity, and preconditions accepted",
            )
            committed = self._commit(accepted, bundle, now)
            if interrupt_after_commit:
                raise ExecutionInterrupted("after_commit", committed)
            return self._complete_effect(
                committed,
                action,
                now=now,
                interrupt_after_effect=interrupt_after_effect,
            )

    def recover(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
    ) -> ExecutionRecord:
        return self.run(
            bundle,
            action,
            now=now,
            preconditions_met=preconditions_met,
        )

    def _resume(
        self,
        record: ExecutionRecord,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool,
        interrupt_after_effect: bool,
    ) -> ExecutionRecord:
        if record.state is ExecutionState.EXECUTED:
            return record
        if record.state in (ExecutionState.REJECTED, ExecutionState.EXPIRED):
            return record
        if record.state is ExecutionState.COMMITTED:
            return self._complete_effect(
                record,
                action,
                now=now,
                interrupt_after_effect=interrupt_after_effect,
            )
        if record.state is not ExecutionState.HELD:
            raise ExecutionStateConflictError(
                f"cannot resume execution from state {record.state.value}"
            )

        rejection = self._validate_new_request(record, bundle, action, now)
        if rejection is not None:
            self.journal.save(rejection)
            return rejection
        maturity = self._maturity_state(action, now, preconditions_met)
        if maturity is ExecutionState.HELD:
            return record
        if maturity is ExecutionState.EXPIRED:
            expired = self._transition(
                record,
                ExecutionState.EXPIRED,
                "incubator.expire",
                CaPUDecisionCode.TTL_EXPIRED,
                now,
                "held action expired",
            )
            self.journal.save(expired)
            return expired
        accepted = self._transition(
            record,
            ExecutionState.ACCEPTED,
            "incubator.release",
            CaPUDecisionCode.PERMIT_OK,
            now,
            "maturity and preconditions satisfied",
        )
        committed = self._commit(accepted, bundle, now)
        return self._complete_effect(
            committed,
            action,
            now=now,
            interrupt_after_effect=interrupt_after_effect,
        )

    def _validate_new_request(
        self,
        record: ExecutionRecord,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        now: str,
    ) -> Optional[ExecutionRecord]:
        try:
            verify_authorization_bundle_files(
                bundle.to_files(),
                now=now,
                nonce_store=self.nonce_store,
                consume_nonce=False,
            )
        except (AuthorizationExpiredError, AuthorizationReplayError) as error:
            return self._transition(
                record,
                ExecutionState.REJECTED,
                "gate.reject",
                CaPUDecisionCode.REJECT_POLICY,
                now,
                str(error),
                error=str(error),
            )
        except Exception as error:
            return self._transition(
                record,
                ExecutionState.REJECTED,
                "gate.reject",
                CaPUDecisionCode.REJECT_INVALID_CAUSE,
                now,
                str(error),
                error=str(error),
            )
        if not set(action.scope).issubset(set(bundle.scope)):
            message = "protected action scope exceeds authorization scope"
            return self._transition(
                record,
                ExecutionState.REJECTED,
                "gate.reject",
                CaPUDecisionCode.REJECT_POLICY,
                now,
                message,
                error=message,
            )
        return None

    def _commit(
        self,
        record: ExecutionRecord,
        bundle: AuthorizationBundle,
        now: str,
    ) -> ExecutionRecord:
        if self.nonce_store.is_consumed(bundle.nonce):
            raise ExecutionAuthorizationError("authorization nonce already consumed")
        committed = self._transition(
            record,
            ExecutionState.COMMITTED,
            "commit.ok",
            CaPUDecisionCode.PERMIT_OK,
            now,
            "durable execution authorization committed before effect",
            committed_at=now,
        )
        try:
            self.journal.save(committed)
        except Exception as error:
            failed = self._transition(
                record,
                ExecutionState.REJECTED,
                "commit.fail",
                CaPUDecisionCode.ABORT_INTERNAL_ERROR,
                now,
                str(error),
                error=str(error),
            )
            raise DurableCommitError("durable commit failed", failed) from error
        self.nonce_store.consume(bundle.nonce)
        return committed

    def _complete_effect(
        self,
        record: ExecutionRecord,
        action: ProtectedAction,
        *,
        now: str,
        interrupt_after_effect: bool,
    ) -> ExecutionRecord:
        if record.state is not ExecutionState.COMMITTED:
            raise ExecutionStateConflictError("effect requires a COMMITTED record")
        recovered = self.executor.inspect(record.execution_id, action)
        try:
            receipt = recovered or self.executor.execute(
                record.execution_id,
                action,
                now,
            )
        except Exception as error:
            failed = self._transition(
                record,
                ExecutionState.EXECUTED,
                "execute.fail",
                CaPUDecisionCode.ABORT_INTERNAL_ERROR,
                now,
                str(error),
                effect_attempted=True,
                effect_succeeded=False,
                executed_at=now,
                error=str(error),
            )
            self.journal.save(failed)
            raise EffectExecutionError("effect execution failed", failed) from error
        if interrupt_after_effect and recovered is None:
            raise ExecutionInterrupted("after_effect_before_receipt", record)
        code = (
            CaPUDecisionCode.COMMIT_NO_EFFECT
            if receipt.no_effect
            else CaPUDecisionCode.COMMIT_EXECUTED
        )
        executed = self._transition(
            record,
            ExecutionState.EXECUTED,
            "execute.ok",
            code,
            now,
            "existing effect recovered" if recovered else "effect executed",
            effect_attempted=True,
            effect_succeeded=True,
            effect_ref=receipt.effect_ref,
            executed_at=receipt.created_at,
        )
        self.journal.save(executed)
        return executed

    def _new_record(
        self,
        execution_id: str,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        now: str,
    ) -> ExecutionRecord:
        transition = ExecutionTransition(
            sequence=0,
            state=ExecutionState.RECEIVED,
            event_type="cause.received",
            decision_code=CaPUDecisionCode.PERMIT_OK,
            created_at=now,
            actor=self.actor,
            detail="protected action received",
        )
        return ExecutionRecord(
            execution_id=execution_id,
            task_id=bundle.task_id,
            trail_id=bundle.trail_id,
            action_id=action.action_id,
            action_ref=action.action_ref,
            action_digest=action.digest,
            authorization_ref=bundle.authorization_ref,
            authorization_nonce=bundle.nonce,
            state=ExecutionState.RECEIVED,
            decision_code=CaPUDecisionCode.PERMIT_OK,
            actor=self.actor,
            created_at=now,
            updated_at=now,
            committed_at=None,
            executed_at=None,
            effect_ref=None,
            effect_attempted=False,
            effect_succeeded=None,
            transitions=(transition,),
        )

    def _transition(
        self,
        record: ExecutionRecord,
        state: ExecutionState,
        event_type: str,
        code: CaPUDecisionCode,
        now: str,
        detail: str,
        *,
        committed_at: Optional[str] = None,
        executed_at: Optional[str] = None,
        effect_ref: Optional[str] = None,
        effect_attempted: Optional[bool] = None,
        effect_succeeded: Optional[bool] = None,
        error: Optional[str] = None,
    ) -> ExecutionRecord:
        attempted = (
            record.effect_attempted
            if effect_attempted is None
            else effect_attempted
        )
        transition = ExecutionTransition(
            sequence=len(record.transitions),
            state=state,
            event_type=event_type,
            decision_code=code,
            created_at=now,
            actor=self.actor,
            detail=detail,
            effect_attempted=attempted,
        )
        return replace(
            record,
            state=state,
            decision_code=code,
            updated_at=now,
            committed_at=committed_at or record.committed_at,
            executed_at=executed_at or record.executed_at,
            effect_ref=effect_ref or record.effect_ref,
            effect_attempted=attempted,
            effect_succeeded=(
                record.effect_succeeded
                if effect_succeeded is None
                else effect_succeeded
            ),
            error=error,
            transitions=(*record.transitions, transition),
        )

    @staticmethod
    def _maturity_state(
        action: ProtectedAction,
        now: str,
        preconditions_met: bool,
    ) -> ExecutionState:
        now_dt = parse_datetime(now)
        if action.expires_at is not None and now_dt >= parse_datetime(action.expires_at):
            return ExecutionState.EXPIRED
        if not preconditions_met:
            return ExecutionState.HELD
        if action.mature_after is not None and now_dt < parse_datetime(action.mature_after):
            return ExecutionState.HELD
        return ExecutionState.ACCEPTED

    @staticmethod
    def _validate_existing(
        record: ExecutionRecord,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
    ) -> None:
        if record.authorization_ref != bundle.authorization_ref:
            raise ExecutionStateConflictError(
                "execution id is already bound to another authorization"
            )
        if record.authorization_nonce != bundle.nonce:
            raise ExecutionStateConflictError(
                "execution id is already bound to another authorization nonce"
            )
        if record.action_digest != action.digest:
            raise ExecutionStateConflictError(
                "execution id is already bound to another action digest"
            )


def execution_ref(bundle: AuthorizationBundle, action: ProtectedAction) -> str:
    payload = {
        "authorization_ref": bundle.authorization_ref,
        "action_digest": action.digest,
        "idempotency_key": action.idempotency_key,
    }
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"execution:sha256:{digest}"


def execution_record_ref(record: ExecutionRecord) -> str:
    digest = hashlib.sha256(
        canonical_json(record.to_dict()).encode("utf-8")
    ).hexdigest()
    return f"execution-record:sha256:{digest}"


def execution_transition_events(
    record: ExecutionRecord,
    *,
    parent_event_id: str,
) -> tuple[TrailEvent, ...]:
    events: list[TrailEvent] = []
    parent = parent_event_id
    suffix = record.execution_id.split(":")[-1][:12]
    for transition in record.transitions:
        event_id = f"event-execution-{suffix}-{transition.sequence}"
        event = TrailEvent(
            event_id=event_id,
            task_id=record.task_id,
            trail_id=record.trail_id,
            event_type=_trail_event_type(transition),
            actor=transition.actor,
            created_at=transition.created_at,
            parent_cause=parent,
            evidence_refs=(record.authorization_ref,),
            payload={
                "execution_id": record.execution_id,
                "action_ref": record.action_ref,
                "state": transition.state.value,
                "capu_event_type": transition.event_type,
                "decision_code": transition.decision_code.value,
                "detail": transition.detail,
                "effect_attempted": transition.effect_attempted,
                "execution_record_ref": execution_record_ref(record),
            },
        )
        events.append(event)
        parent = event_id
    return tuple(events)


def append_execution_record(
    trail: CognitiveTrail,
    record: ExecutionRecord,
    *,
    parent_event_id: str,
) -> CognitiveTrail:
    if trail.task_id != record.task_id or trail.trail_id != record.trail_id:
        raise ExecutionStateConflictError(
            "execution record belongs to another task or trail"
        )
    if parent_event_id not in {event.event_id for event in trail.events}:
        raise ExecutionStateConflictError(
            "execution parent event is not present in the cognitive trail"
        )
    return replace(
        trail,
        events=(
            *trail.events,
            *execution_transition_events(record, parent_event_id=parent_event_id),
        ),
    )


def attach_execution_record(
    artifact: ReusableArtifact,
    record: ExecutionRecord,
) -> ReusableArtifact:
    if artifact.task_id != record.task_id or artifact.trail_id != record.trail_id:
        raise ExecutionStateConflictError(
            "execution record belongs to another reusable artifact"
        )
    return replace(artifact, execution_ref=execution_record_ref(record))


def _trail_event_type(transition: ExecutionTransition) -> TrailEventType:
    if transition.state is ExecutionState.COMMITTED:
        return TrailEventType.EXECUTION_COMMITTED
    if transition.state is ExecutionState.EXECUTED:
        return TrailEventType.EXECUTION_COMPLETED
    return TrailEventType.WORK_COMPLETED


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def pretty_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
