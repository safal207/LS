import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import { ContinuityStore } from "./store.js";
import type {
  ContinuityEnvelope,
  StoredContinuityObject
} from "./types.js";

const OBJECT_REF_RE = /^sha256:[0-9a-f]{64}$/;
const PROFILE = "org.ls.trustworthy-transition-continuity.v0.1" as const;

export type AuthorityDimension =
  | "VALID"
  | "DENIED"
  | "PENDING"
  | "EXPIRED"
  | "EXPIRED_AT_REPORT"
  | "CONSUMED"
  | "REVALIDATION_REQUIRED"
  | "NOT_EVALUATED"
  | "UNKNOWN";

export type ExecutionDimension =
  | "NOT_OBSERVED"
  | "OBSERVED_EXECUTED"
  | "OBSERVED_BLOCKED"
  | "OBSERVED_ERRORED"
  | "OBSERVED_OTHER";

export type IntegrityDimension =
  | "VERIFIED"
  | "FAILED"
  | "PARTIAL"
  | "NOT_EVALUATED"
  | "UNKNOWN";

export type CausalDimension =
  | "VALID"
  | "INVALID"
  | "NOT_EVALUATED"
  | "UNKNOWN";

export type TransitionOperation =
  | "resume_side_effect"
  | "retry_side_effect"
  | "report_only"
  | "remediate_response";

export type TransitionContinuitySnapshotPayload = Record<string, unknown> & {
  profile: typeof PROFILE;
  transition_id: string;
  subject_id: string;
  action_identity_digest: string;
  binding_digest: string;
  record_refs: {
    authorization_ref: string | null;
    observation_refs: string[];
    response_integrity_ref: string | null;
    causal_audit_ref: string | null;
  };
  evidence_set_digest: string;
  dimensions: {
    authority: AuthorityDimension;
    execution: ExecutionDimension;
    response_integrity: IntegrityDimension;
    causal_validity: CausalDimension;
  };
  side_effect_committed: boolean;
  authority_expires_at: string | null;
  context_digest: string;
  retry: {
    retryable_after_error: boolean;
    idempotency_key: string | null;
  };
  reauthorization_ref: string | null;
  captured_at: string;
  claim_boundary: string;
};

export interface TransitionContinuitySnapshotInput {
  transition_id: string;
  subject_id: string;
  action_identity_digest: string;
  binding_digest: string;
  record_refs: TransitionContinuitySnapshotPayload["record_refs"];
  dimensions: TransitionContinuitySnapshotPayload["dimensions"];
  side_effect_committed: boolean;
  authority_expires_at?: string | null;
  context_digest: string;
  retry?: Partial<TransitionContinuitySnapshotPayload["retry"]>;
  reauthorization_ref?: string | null;
}

export interface TransitionResumeRequest {
  transition_id: string;
  subject_id: string;
  action_identity_digest: string;
  binding_digest: string;
  operation: TransitionOperation;
  current_evidence_set_digest: string;
  current_context_digest: string;
  now: string;
  idempotency_key?: string | null;
}

export interface TransitionResumeDecision {
  allowed: boolean;
  posture:
    | "CONTINUE_SIDE_EFFECT"
    | "RETRY_SIDE_EFFECT"
    | "REPORT_ONLY"
    | "REMEDIATE_RESPONSE"
    | "REVALIDATE"
    | "BLOCKED"
    | "ALREADY_CONSUMED";
  reason:
    | "OK"
    | "HISTORICAL_REPORT_ONLY"
    | "RESPONSE_REMEDIATION_ONLY"
    | "TRANSITION_MISMATCH"
    | "SUBJECT_MISMATCH"
    | "ACTION_BINDING_MISMATCH"
    | "SNAPSHOT_EVIDENCE_MISMATCH"
    | "EVIDENCE_DRIFT"
    | "CONTEXT_DRIFT"
    | "AUTHORITY_DENIED"
    | "AUTHORITY_PENDING"
    | "AUTHORITY_EXPIRED"
    | "AUTHORITY_CONSUMED"
    | "AUTHORITY_REVALIDATION_REQUIRED"
    | "AUTHORITY_NOT_EVALUATED"
    | "CAUSAL_LINEAGE_INVALID"
    | "CAUSAL_LINEAGE_NOT_EVALUATED"
    | "SIDE_EFFECT_ALREADY_COMMITTED"
    | "EXECUTION_ALREADY_OBSERVED"
    | "EXECUTION_BLOCKED"
    | "RETRY_NOT_PROVEN_SAFE"
    | "RESPONSE_INTEGRITY_FAILED"
    | "RESPONSE_INTEGRITY_PARTIAL"
    | "UNKNOWN_STATE";
  snapshot_ref: string;
  required_checks: string[];
  dimensions: TransitionContinuitySnapshotPayload["dimensions"];
}

export interface SnapshotChainAssessment {
  valid: boolean;
  reason_codes: Array<
    | "OK"
    | "PREVIOUS_REF_MISMATCH"
    | "TRANSITION_MISMATCH"
    | "SUBJECT_MISMATCH"
    | "ACTION_BINDING_MISMATCH"
    | "EVIDENCE_DIGEST_INVALID"
    | "OBSERVATION_ROLLBACK"
    | "SIDE_EFFECT_ROLLBACK"
    | "EXECUTION_ROLLBACK"
    | "AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION"
    | "CAPTURE_TIME_ROLLBACK"
  >;
}

function requireText(value: string, label: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${label.toUpperCase()}_REQUIRED`);
  }
  return value.trim();
}

function requireObjectRef(value: string | null, label: string): string | null {
  if (value === null) return null;
  if (!OBJECT_REF_RE.test(value)) throw new Error(`${label.toUpperCase()}_INVALID`);
  return value;
}

function uniqueSorted(values: readonly string[]): string[] {
  const result = [...new Set(values)];
  for (const value of result) requireObjectRef(value, "observation_ref");
  return result.sort();
}

function parseTime(value: string, label: string): number {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) throw new Error(`${label.toUpperCase()}_INVALID`);
  return timestamp;
}

export function computeEvidenceSetDigest(input: {
  transition_id: string;
  subject_id: string;
  action_identity_digest: string;
  binding_digest: string;
  record_refs: TransitionContinuitySnapshotPayload["record_refs"];
}): string {
  const canonicalSet = {
    profile: "org.ls.trustworthy-transition-evidence-set.v0.1",
    transition_id: requireText(input.transition_id, "transition_id"),
    subject_id: requireText(input.subject_id, "subject_id"),
    action_identity_digest: requireObjectRef(
      input.action_identity_digest,
      "action_identity_digest"
    ),
    binding_digest: requireObjectRef(input.binding_digest, "binding_digest"),
    record_refs: {
      authorization_ref: requireObjectRef(
        input.record_refs.authorization_ref,
        "authorization_ref"
      ),
      observation_refs: uniqueSorted(input.record_refs.observation_refs),
      response_integrity_ref: requireObjectRef(
        input.record_refs.response_integrity_ref,
        "response_integrity_ref"
      ),
      causal_audit_ref: requireObjectRef(
        input.record_refs.causal_audit_ref,
        "causal_audit_ref"
      )
    }
  };
  return sha256Ref(canonicalBytes(canonicalSet));
}

export function createTransitionSnapshotEnvelope(
  input: TransitionContinuitySnapshotInput,
  createdAt: string,
  previousRef: string | null = null
): ContinuityEnvelope<TransitionContinuitySnapshotPayload> {
  parseTime(createdAt, "created_at");
  requireObjectRef(previousRef, "previous_ref");
  requireObjectRef(input.context_digest, "context_digest");
  requireObjectRef(input.reauthorization_ref ?? null, "reauthorization_ref");
  if (input.authority_expires_at) parseTime(input.authority_expires_at, "authority_expires_at");

  const recordRefs = {
    authorization_ref: requireObjectRef(
      input.record_refs.authorization_ref,
      "authorization_ref"
    ),
    observation_refs: uniqueSorted(input.record_refs.observation_refs),
    response_integrity_ref: requireObjectRef(
      input.record_refs.response_integrity_ref,
      "response_integrity_ref"
    ),
    causal_audit_ref: requireObjectRef(
      input.record_refs.causal_audit_ref,
      "causal_audit_ref"
    )
  };
  const transitionId = requireText(input.transition_id, "transition_id");
  const subjectId = requireText(input.subject_id, "subject_id");
  const actionIdentityDigest = requireObjectRef(
    input.action_identity_digest,
    "action_identity_digest"
  ) as string;
  const bindingDigest = requireObjectRef(input.binding_digest, "binding_digest") as string;

  const payload: TransitionContinuitySnapshotPayload = {
    profile: PROFILE,
    transition_id: transitionId,
    subject_id: subjectId,
    action_identity_digest: actionIdentityDigest,
    binding_digest: bindingDigest,
    record_refs: recordRefs,
    evidence_set_digest: computeEvidenceSetDigest({
      transition_id: transitionId,
      subject_id: subjectId,
      action_identity_digest: actionIdentityDigest,
      binding_digest: bindingDigest,
      record_refs: recordRefs
    }),
    dimensions: { ...input.dimensions },
    side_effect_committed: input.side_effect_committed,
    authority_expires_at: input.authority_expires_at ?? null,
    context_digest: input.context_digest,
    retry: {
      retryable_after_error: input.retry?.retryable_after_error ?? false,
      idempotency_key: input.retry?.idempotency_key ?? null
    },
    reauthorization_ref: input.reauthorization_ref ?? null,
    captured_at: createdAt,
    claim_boundary:
      "LS persists an immutable continuity snapshot and derives resume posture from supplied independent dimensions. " +
      "It does not issue authority, observe execution, verify response truth, or decide causal validity."
  };

  return {
    schema: "ls.continuity.v1",
    object_type: "verification_receipt",
    subject_id: subjectId,
    previous_ref: previousRef,
    created_at: createdAt,
    payload,
    extensions: {
      interoperability_profile: PROFILE,
      transition_id: transitionId
    }
  };
}

export function persistTransitionSnapshot(
  store: ContinuityStore,
  input: TransitionContinuitySnapshotInput,
  createdAt: string,
  previousRef: string | null = null
): StoredContinuityObject<TransitionContinuitySnapshotPayload> {
  return store.persist(createTransitionSnapshotEnvelope(input, createdAt, previousRef));
}

function verifyStoredSnapshot(
  snapshot: StoredContinuityObject<TransitionContinuitySnapshotPayload>
): void {
  if (snapshot.object_type !== "verification_receipt") {
    throw new Error("TRANSITION_SNAPSHOT_TYPE_MISMATCH");
  }
  if (snapshot.payload.profile !== PROFILE) {
    throw new Error("TRANSITION_SNAPSHOT_PROFILE_MISMATCH");
  }
  if (snapshot.subject_id !== snapshot.payload.subject_id) {
    throw new Error("TRANSITION_SNAPSHOT_SUBJECT_MISMATCH");
  }
  const expected = computeEvidenceSetDigest(snapshot.payload);
  if (snapshot.payload.evidence_set_digest !== expected) {
    throw new Error("TRANSITION_SNAPSHOT_EVIDENCE_MISMATCH");
  }
}

function decision(
  snapshot: StoredContinuityObject<TransitionContinuitySnapshotPayload>,
  allowed: boolean,
  posture: TransitionResumeDecision["posture"],
  reason: TransitionResumeDecision["reason"],
  requiredChecks: string[] = []
): TransitionResumeDecision {
  return {
    allowed,
    posture,
    reason,
    snapshot_ref: snapshot.object_id,
    required_checks: [...new Set(requiredChecks)].sort(),
    dimensions: { ...snapshot.payload.dimensions }
  };
}

export function evaluateTransitionResume(
  snapshot: StoredContinuityObject<TransitionContinuitySnapshotPayload>,
  request: TransitionResumeRequest
): TransitionResumeDecision {
  verifyStoredSnapshot(snapshot);
  const payload = snapshot.payload;

  if (request.transition_id !== payload.transition_id) {
    return decision(snapshot, false, "BLOCKED", "TRANSITION_MISMATCH");
  }
  if (request.subject_id !== payload.subject_id) {
    return decision(snapshot, false, "BLOCKED", "SUBJECT_MISMATCH");
  }
  if (
    request.action_identity_digest !== payload.action_identity_digest ||
    request.binding_digest !== payload.binding_digest
  ) {
    return decision(snapshot, false, "BLOCKED", "ACTION_BINDING_MISMATCH");
  }

  if (request.operation === "report_only") {
    const checks: string[] = [];
    if (request.current_evidence_set_digest !== payload.evidence_set_digest) {
      checks.push("evidence_set_changed_since_snapshot");
    }
    if (request.current_context_digest !== payload.context_digest) {
      checks.push("context_changed_since_snapshot");
    }
    return decision(
      snapshot,
      true,
      "REPORT_ONLY",
      "HISTORICAL_REPORT_ONLY",
      checks
    );
  }

  if (request.current_evidence_set_digest !== payload.evidence_set_digest) {
    return decision(snapshot, false, "REVALIDATE", "EVIDENCE_DRIFT", [
      "rebuild_transition_snapshot"
    ]);
  }
  if (request.current_context_digest !== payload.context_digest) {
    return decision(snapshot, false, "REVALIDATE", "CONTEXT_DRIFT", [
      "revalidate_runtime_context"
    ]);
  }

  if (payload.dimensions.causal_validity === "INVALID") {
    return decision(snapshot, false, "BLOCKED", "CAUSAL_LINEAGE_INVALID", [
      "repair_causal_lineage"
    ]);
  }
  if (
    payload.dimensions.causal_validity === "UNKNOWN" ||
    payload.dimensions.causal_validity === "NOT_EVALUATED"
  ) {
    return decision(
      snapshot,
      false,
      "REVALIDATE",
      "CAUSAL_LINEAGE_NOT_EVALUATED",
      ["evaluate_causal_lineage"]
    );
  }

  if (request.operation === "remediate_response") {
    if (
      payload.dimensions.response_integrity === "FAILED" ||
      payload.dimensions.response_integrity === "PARTIAL"
    ) {
      return decision(
        snapshot,
        true,
        "REMEDIATE_RESPONSE",
        "RESPONSE_REMEDIATION_ONLY"
      );
    }
    return decision(snapshot, false, "BLOCKED", "UNKNOWN_STATE", [
      "no_response_remediation_required"
    ]);
  }

  if (
    payload.authority_expires_at !== null &&
    parseTime(request.now, "now") >= parseTime(payload.authority_expires_at, "authority_expires_at")
  ) {
    return decision(snapshot, false, "BLOCKED", "AUTHORITY_EXPIRED", [
      "obtain_fresh_authorization"
    ]);
  }

  switch (payload.dimensions.authority) {
    case "DENIED":
      return decision(snapshot, false, "BLOCKED", "AUTHORITY_DENIED");
    case "PENDING":
      return decision(snapshot, false, "BLOCKED", "AUTHORITY_PENDING", [
        "resolve_pending_approval"
      ]);
    case "EXPIRED":
    case "EXPIRED_AT_REPORT":
      return decision(snapshot, false, "BLOCKED", "AUTHORITY_EXPIRED", [
        "obtain_fresh_authorization"
      ]);
    case "CONSUMED":
      return decision(snapshot, false, "ALREADY_CONSUMED", "AUTHORITY_CONSUMED");
    case "REVALIDATION_REQUIRED":
      return decision(
        snapshot,
        false,
        "REVALIDATE",
        "AUTHORITY_REVALIDATION_REQUIRED",
        ["revalidate_authority"]
      );
    case "NOT_EVALUATED":
    case "UNKNOWN":
      return decision(
        snapshot,
        false,
        "REVALIDATE",
        "AUTHORITY_NOT_EVALUATED",
        ["evaluate_authority"]
      );
    case "VALID":
      break;
  }

  if (
    payload.side_effect_committed ||
    payload.dimensions.execution === "OBSERVED_EXECUTED"
  ) {
    return decision(
      snapshot,
      false,
      "ALREADY_CONSUMED",
      payload.side_effect_committed
        ? "SIDE_EFFECT_ALREADY_COMMITTED"
        : "EXECUTION_ALREADY_OBSERVED"
    );
  }

  if (payload.dimensions.execution === "OBSERVED_BLOCKED") {
    return decision(snapshot, false, "BLOCKED", "EXECUTION_BLOCKED", [
      "obtain_new_authorization"
    ]);
  }

  if (payload.dimensions.response_integrity === "FAILED") {
    return decision(
      snapshot,
      false,
      "REMEDIATE_RESPONSE",
      "RESPONSE_INTEGRITY_FAILED",
      ["remediate_response_before_continuation"]
    );
  }
  if (payload.dimensions.response_integrity === "PARTIAL") {
    return decision(
      snapshot,
      false,
      "REVALIDATE",
      "RESPONSE_INTEGRITY_PARTIAL",
      ["resolve_unverifiable_claims"]
    );
  }

  if (payload.dimensions.execution === "OBSERVED_ERRORED") {
    if (
      request.operation === "retry_side_effect" &&
      payload.retry.retryable_after_error &&
      payload.retry.idempotency_key !== null &&
      request.idempotency_key === payload.retry.idempotency_key
    ) {
      return decision(snapshot, true, "RETRY_SIDE_EFFECT", "OK");
    }
    return decision(snapshot, false, "REVALIDATE", "RETRY_NOT_PROVEN_SAFE", [
      "prove_idempotent_retry"
    ]);
  }

  if (
    request.operation === "resume_side_effect" &&
    payload.dimensions.execution === "NOT_OBSERVED"
  ) {
    return decision(snapshot, true, "CONTINUE_SIDE_EFFECT", "OK");
  }

  return decision(snapshot, false, "BLOCKED", "UNKNOWN_STATE");
}

const TERMINAL_AUTHORITY = new Set<AuthorityDimension>([
  "DENIED",
  "EXPIRED",
  "EXPIRED_AT_REPORT",
  "CONSUMED",
  "REVALIDATION_REQUIRED"
]);

export function assessSnapshotChain(
  previous: StoredContinuityObject<TransitionContinuitySnapshotPayload>,
  current: StoredContinuityObject<TransitionContinuitySnapshotPayload>
): SnapshotChainAssessment {
  verifyStoredSnapshot(previous);
  verifyStoredSnapshot(current);
  const reasons: SnapshotChainAssessment["reason_codes"] = [];

  if (current.previous_ref !== previous.object_id) reasons.push("PREVIOUS_REF_MISMATCH");
  if (current.payload.transition_id !== previous.payload.transition_id) {
    reasons.push("TRANSITION_MISMATCH");
  }
  if (current.payload.subject_id !== previous.payload.subject_id) {
    reasons.push("SUBJECT_MISMATCH");
  }
  if (
    current.payload.action_identity_digest !== previous.payload.action_identity_digest ||
    current.payload.binding_digest !== previous.payload.binding_digest
  ) {
    reasons.push("ACTION_BINDING_MISMATCH");
  }

  const previousObservations = new Set(previous.payload.record_refs.observation_refs);
  const currentObservations = new Set(current.payload.record_refs.observation_refs);
  if ([...previousObservations].some((reference) => !currentObservations.has(reference))) {
    reasons.push("OBSERVATION_ROLLBACK");
  }
  if (previous.payload.side_effect_committed && !current.payload.side_effect_committed) {
    reasons.push("SIDE_EFFECT_ROLLBACK");
  }
  if (
    previous.payload.dimensions.execution === "OBSERVED_EXECUTED" &&
    current.payload.dimensions.execution !== "OBSERVED_EXECUTED"
  ) {
    reasons.push("EXECUTION_ROLLBACK");
  }

  if (
    TERMINAL_AUTHORITY.has(previous.payload.dimensions.authority) &&
    current.payload.dimensions.authority === "VALID"
  ) {
    const newAuthorization =
      current.payload.record_refs.authorization_ref !==
      previous.payload.record_refs.authorization_ref;
    const explicitReauthorization =
      current.payload.reauthorization_ref !== null &&
      current.payload.reauthorization_ref ===
        current.payload.record_refs.authorization_ref;
    if (!newAuthorization || !explicitReauthorization) {
      reasons.push("AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION");
    }
  }

  if (
    parseTime(current.payload.captured_at, "current_captured_at") <
    parseTime(previous.payload.captured_at, "previous_captured_at")
  ) {
    reasons.push("CAPTURE_TIME_ROLLBACK");
  }

  return {
    valid: reasons.length === 0,
    reason_codes: reasons.length === 0 ? ["OK"] : [...new Set(reasons)].sort()
  };
}
