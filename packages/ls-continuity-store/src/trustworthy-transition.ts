import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import { ContinuityStore } from "./store.js";
import type {
  ContinuityEnvelope,
  StoredContinuityObject
} from "./types.js";

const OBJECT_REF_RE = /^sha256:[0-9a-f]{64}$/;
const PROFILE = "org.ls.trustworthy-transition-continuity.v0.1" as const;
const CLAIM_BOUNDARY =
  "LS persists an immutable continuity snapshot and derives resume posture from supplied independent dimensions. " +
  "It does not issue authority, observe execution, verify response truth, or decide causal validity.";

const AUTHORITY_DIMENSIONS = [
  "VALID",
  "DENIED",
  "PENDING",
  "EXPIRED",
  "EXPIRED_AT_REPORT",
  "CONSUMED",
  "REVALIDATION_REQUIRED",
  "NOT_EVALUATED",
  "UNKNOWN"
] as const;
const EXECUTION_DIMENSIONS = [
  "NOT_OBSERVED",
  "OBSERVED_EXECUTED",
  "OBSERVED_BLOCKED",
  "OBSERVED_ERRORED",
  "OBSERVED_OTHER"
] as const;
const INTEGRITY_DIMENSIONS = [
  "VERIFIED",
  "FAILED",
  "PARTIAL",
  "NOT_EVALUATED",
  "UNKNOWN"
] as const;
const CAUSAL_DIMENSIONS = [
  "VALID",
  "INVALID",
  "NOT_EVALUATED",
  "UNKNOWN"
] as const;

export type AuthorityDimension = (typeof AUTHORITY_DIMENSIONS)[number];
export type ExecutionDimension = (typeof EXECUTION_DIMENSIONS)[number];
export type IntegrityDimension = (typeof INTEGRITY_DIMENSIONS)[number];
export type CausalDimension = (typeof CAUSAL_DIMENSIONS)[number];

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
    | "SNAPSHOT_NOT_LATEST"
    | "SNAPSHOT_CHAIN_INVALID"
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
    | "CAUSAL_EVIDENCE_REUSED"
    | "RESPONSE_INTEGRITY_EVIDENCE_REUSED"
    | "RESPONSE_INTEGRITY_RECOVERY_UNVERIFIED"
    | "CAPTURE_TIME_ROLLBACK"
  >;
}

function requireText(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`${label.toUpperCase()}_REQUIRED`);
  }
  return value.trim();
}

function requireObjectRef(value: unknown, label: string): string | null {
  if (value === null) return null;
  if (typeof value !== "string" || !OBJECT_REF_RE.test(value)) {
    throw new Error(`${label.toUpperCase()}_INVALID`);
  }
  return value;
}

function requireNonNullObjectRef(value: unknown, label: string): string {
  const reference = requireObjectRef(value, label);
  if (reference === null) {
    throw new Error(`${label.toUpperCase()}_INVALID`);
  }
  return reference;
}

function uniqueSorted(values: unknown): string[] {
  if (!Array.isArray(values)) throw new Error("OBSERVATION_REFS_INVALID");
  const result = [...new Set(values)];
  for (const value of result) {
    requireNonNullObjectRef(value, "observation_ref");
  }
  return (result as string[]).sort();
}

function parseTime(value: unknown, label: string): number {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label.toUpperCase()}_INVALID`);
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) throw new Error(`${label.toUpperCase()}_INVALID`);
  return timestamp;
}

function requireRecord(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label.toUpperCase()}_INVALID`);
  }
  return value as Record<string, unknown>;
}

function requireDimension<T extends string>(
  value: unknown,
  allowed: readonly T[],
  label: string
): T {
  if (typeof value !== "string" || !(allowed as readonly string[]).includes(value)) {
    throw new Error(`${label.toUpperCase()}_INVALID`);
  }
  return value as T;
}

function validateDimensions(
  value: unknown
): TransitionContinuitySnapshotPayload["dimensions"] {
  const dimensions = requireRecord(value, "dimensions");
  const expected = new Set([
    "authority",
    "execution",
    "response_integrity",
    "causal_validity"
  ]);
  if (
    Object.keys(dimensions).length !== expected.size ||
    Object.keys(dimensions).some((key) => !expected.has(key))
  ) {
    throw new Error("DIMENSIONS_SHAPE_INVALID");
  }
  return {
    authority: requireDimension(
      dimensions.authority,
      AUTHORITY_DIMENSIONS,
      "authority"
    ),
    execution: requireDimension(
      dimensions.execution,
      EXECUTION_DIMENSIONS,
      "execution"
    ),
    response_integrity: requireDimension(
      dimensions.response_integrity,
      INTEGRITY_DIMENSIONS,
      "response_integrity"
    ),
    causal_validity: requireDimension(
      dimensions.causal_validity,
      CAUSAL_DIMENSIONS,
      "causal_validity"
    )
  };
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
    action_identity_digest: requireNonNullObjectRef(
      input.action_identity_digest,
      "action_identity_digest"
    ),
    binding_digest: requireNonNullObjectRef(
      input.binding_digest,
      "binding_digest"
    ),
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
  const contextDigest = requireNonNullObjectRef(
    input.context_digest,
    "context_digest"
  );
  const reauthorizationRef = requireObjectRef(
    input.reauthorization_ref ?? null,
    "reauthorization_ref"
  );
  const authorityExpiresAt = input.authority_expires_at ?? null;
  if (authorityExpiresAt !== null) {
    parseTime(authorityExpiresAt, "authority_expires_at");
  }
  const dimensions = validateDimensions(input.dimensions);
  if (typeof input.side_effect_committed !== "boolean") {
    throw new Error("SIDE_EFFECT_COMMITTED_INVALID");
  }
  const retryableAfterError = input.retry?.retryable_after_error ?? false;
  if (typeof retryableAfterError !== "boolean") {
    throw new Error("RETRYABLE_AFTER_ERROR_INVALID");
  }
  const idempotencyKey = input.retry?.idempotency_key ?? null;
  if (idempotencyKey !== null) requireText(idempotencyKey, "idempotency_key");

  const inputRecordRefs = requireRecord(input.record_refs, "record_refs");
  const recordRefs = {
    authorization_ref: requireObjectRef(
      inputRecordRefs.authorization_ref,
      "authorization_ref"
    ),
    observation_refs: uniqueSorted(inputRecordRefs.observation_refs),
    response_integrity_ref: requireObjectRef(
      inputRecordRefs.response_integrity_ref,
      "response_integrity_ref"
    ),
    causal_audit_ref: requireObjectRef(
      inputRecordRefs.causal_audit_ref,
      "causal_audit_ref"
    )
  };
  const transitionId = requireText(input.transition_id, "transition_id");
  const subjectId = requireText(input.subject_id, "subject_id");
  const actionIdentityDigest = requireNonNullObjectRef(
    input.action_identity_digest,
    "action_identity_digest"
  );
  const bindingDigest = requireNonNullObjectRef(
    input.binding_digest,
    "binding_digest"
  );

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
    dimensions,
    side_effect_committed: input.side_effect_committed,
    authority_expires_at: authorityExpiresAt,
    context_digest: contextDigest,
    retry: {
      retryable_after_error: retryableAfterError,
      idempotency_key: idempotencyKey
    },
    reauthorization_ref: reauthorizationRef,
    captured_at: createdAt,
    claim_boundary: CLAIM_BOUNDARY
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
  requireObjectRef(snapshot.previous_ref, "previous_ref");
  parseTime(snapshot.created_at, "created_at");
  requireText(snapshot.payload.transition_id, "transition_id");
  requireText(snapshot.payload.subject_id, "subject_id");
  requireNonNullObjectRef(
    snapshot.payload.action_identity_digest,
    "action_identity_digest"
  );
  requireNonNullObjectRef(snapshot.payload.binding_digest, "binding_digest");
  requireNonNullObjectRef(snapshot.payload.context_digest, "context_digest");
  requireObjectRef(snapshot.payload.reauthorization_ref, "reauthorization_ref");
  requireObjectRef(snapshot.payload.evidence_set_digest, "evidence_set_digest");
  validateDimensions(snapshot.payload.dimensions);
  if (typeof snapshot.payload.side_effect_committed !== "boolean") {
    throw new Error("SIDE_EFFECT_COMMITTED_INVALID");
  }
  if (snapshot.payload.authority_expires_at !== null) {
    parseTime(snapshot.payload.authority_expires_at, "authority_expires_at");
  }
  parseTime(snapshot.payload.captured_at, "captured_at");
  const retry = requireRecord(snapshot.payload.retry, "retry");
  if (typeof retry.retryable_after_error !== "boolean") {
    throw new Error("RETRYABLE_AFTER_ERROR_INVALID");
  }
  if (retry.idempotency_key !== null) {
    requireText(retry.idempotency_key, "idempotency_key");
  }
  if (snapshot.payload.claim_boundary !== CLAIM_BOUNDARY) {
    throw new Error("TRANSITION_SNAPSHOT_CLAIM_BOUNDARY_MISMATCH");
  }
  const recordRefs = requireRecord(snapshot.payload.record_refs, "record_refs");
  requireObjectRef(recordRefs.authorization_ref, "authorization_ref");
  uniqueSorted(recordRefs.observation_refs);
  requireObjectRef(recordRefs.response_integrity_ref, "response_integrity_ref");
  requireObjectRef(recordRefs.causal_audit_ref, "causal_audit_ref");
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

function loadTransitionSnapshots(
  store: ContinuityStore,
  subjectId: string,
  transitionId: string
): Array<StoredContinuityObject<TransitionContinuitySnapshotPayload>> {
  const snapshots: Array<
    StoredContinuityObject<TransitionContinuitySnapshotPayload>
  > = [];
  for (const event of store.listEvents(subjectId)) {
    const objectRef = requireObjectRef(event.object_ref, "event_object_ref");
    if (objectRef === null) throw new Error("EVENT_OBJECT_REF_INVALID");
    const object = store.load<Record<string, unknown>>(objectRef);
    if (object.object_type !== "verification_receipt") continue;
    const payload = requireRecord(object.payload, "verification_receipt_payload");
    if (payload.profile !== PROFILE) continue;
    const snapshot = object as StoredContinuityObject<
      TransitionContinuitySnapshotPayload
    >;
    verifyStoredSnapshot(snapshot);
    if (snapshot.payload.transition_id === transitionId) snapshots.push(snapshot);
  }
  return snapshots;
}

export function evaluateTransitionResume(
  store: ContinuityStore,
  snapshotRef: string,
  request: TransitionResumeRequest
): TransitionResumeDecision {
  requireObjectRef(snapshotRef, "snapshot_ref");
  const snapshot = store.load<TransitionContinuitySnapshotPayload>(snapshotRef);
  verifyStoredSnapshot(snapshot);
  const payload = snapshot.payload;
  const now = parseTime(request.now, "now");

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

  const snapshots = loadTransitionSnapshots(
    store,
    payload.subject_id,
    payload.transition_id
  );
  if (snapshots.at(-1)?.object_id !== snapshot.object_id) {
    return decision(snapshot, false, "BLOCKED", "SNAPSHOT_NOT_LATEST", [
      "load_latest_transition_snapshot"
    ]);
  }
  if (!assessSnapshotSequence(snapshots).valid) {
    return decision(snapshot, false, "BLOCKED", "SNAPSHOT_CHAIN_INVALID", [
      "repair_snapshot_chain"
    ]);
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
    now >= parseTime(payload.authority_expires_at, "authority_expires_at")
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
    default:
      return decision(snapshot, false, "BLOCKED", "UNKNOWN_STATE", [
        "validate_snapshot_dimensions"
      ]);
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
  } else if (
    previous.payload.dimensions.execution !== "NOT_OBSERVED" &&
    current.payload.dimensions.execution === "NOT_OBSERVED"
  ) {
    reasons.push("EXECUTION_ROLLBACK");
  }

  const previousExpiry = previous.payload.authority_expires_at;
  const currentExpiry = current.payload.authority_expires_at;
  const authorizationChanged =
    current.payload.record_refs.authorization_ref !==
    previous.payload.record_refs.authorization_ref;
  const explicitAuthorizationEpoch =
    authorizationChanged &&
    current.payload.reauthorization_ref !== null &&
    current.payload.reauthorization_ref ===
      current.payload.record_refs.authorization_ref;
  if (
    previous.payload.dimensions.authority === "VALID" &&
    current.payload.dimensions.authority === "VALID" &&
    previousExpiry !== null &&
    (currentExpiry === null ||
      parseTime(currentExpiry, "current_authority_expires_at") >
        parseTime(previousExpiry, "previous_authority_expires_at")) &&
    !explicitAuthorizationEpoch
  ) {
    reasons.push("AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION");
  }

  if (
    TERMINAL_AUTHORITY.has(previous.payload.dimensions.authority) &&
    current.payload.dimensions.authority === "VALID"
  ) {
    const explicitReauthorization =
      current.payload.reauthorization_ref !== null &&
      current.payload.reauthorization_ref ===
        current.payload.record_refs.authorization_ref;
    if (!authorizationChanged || !explicitReauthorization) {
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

export function assessSnapshotSequence(
  snapshots: readonly StoredContinuityObject<TransitionContinuitySnapshotPayload>[]
): SnapshotChainAssessment {
  const reasons: SnapshotChainAssessment["reason_codes"] = [];
  if (snapshots.length === 0 || snapshots[0].previous_ref !== null) {
    reasons.push("PREVIOUS_REF_MISMATCH");
  }

  let terminalAuthorityActive = false;
  let authorizationEpoch: string | null = null;
  let authorizationEpochExpiry: number | null = null;
  const seenAuthorizationRefs = new Set<string>();
  let causalRecoveryRequired = false;
  const seenCausalRefs = new Set<string>();
  let responseRecoveryRequired = false;
  const seenResponseRefs = new Set<string>();
  for (const [index, snapshot] of snapshots.entries()) {
    verifyStoredSnapshot(snapshot);
    if (index > 0) {
      const assessment = assessSnapshotChain(snapshots[index - 1], snapshot);
      reasons.push(...assessment.reason_codes.filter((reason) => reason !== "OK"));
    }

    const authorization = snapshot.payload.record_refs.authorization_ref;
    const currentExpiry =
      snapshot.payload.authority_expires_at === null
        ? null
        : parseTime(
            snapshot.payload.authority_expires_at,
            "authority_expires_at"
          );
    const explicitNewEpoch =
      index > 0 &&
      authorization !== null &&
      authorization !== authorizationEpoch &&
      snapshot.payload.reauthorization_ref === authorization &&
      !seenAuthorizationRefs.has(authorization);
    if (
      index > 0 &&
      authorization !== null &&
      authorization !== authorizationEpoch &&
      seenAuthorizationRefs.has(authorization)
    ) {
      reasons.push("AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION");
    }
    if (index === 0 || explicitNewEpoch) {
      authorizationEpoch = authorization;
      authorizationEpochExpiry = currentExpiry;
      if (explicitNewEpoch) terminalAuthorityActive = false;
    } else {
      if (
        snapshot.payload.dimensions.authority === "VALID" &&
        authorizationEpochExpiry !== null &&
        (currentExpiry === null || currentExpiry > authorizationEpochExpiry)
      ) {
        reasons.push("AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION");
      }
      if (
        currentExpiry !== null &&
        (authorizationEpochExpiry === null ||
          currentExpiry < authorizationEpochExpiry)
      ) {
        authorizationEpochExpiry = currentExpiry;
      }
    }

    if (
      terminalAuthorityActive &&
      snapshot.payload.dimensions.authority === "VALID"
    ) {
      reasons.push("AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION");
    }

    if (
      !terminalAuthorityActive &&
      TERMINAL_AUTHORITY.has(snapshot.payload.dimensions.authority)
    ) {
      terminalAuthorityActive = true;
    }
    if (authorization !== null) seenAuthorizationRefs.add(authorization);

    const causalRef = snapshot.payload.record_refs.causal_audit_ref;
    const causalRefSeen =
      causalRef !== null && seenCausalRefs.has(causalRef);
    if (snapshot.payload.dimensions.causal_validity === "INVALID") {
      causalRecoveryRequired = true;
    } else if (
      causalRecoveryRequired &&
      snapshot.payload.dimensions.causal_validity === "VALID"
    ) {
      if (causalRef === null || causalRefSeen) {
        reasons.push("CAUSAL_EVIDENCE_REUSED");
      } else {
        causalRecoveryRequired = false;
      }
    }
    if (causalRef !== null) seenCausalRefs.add(causalRef);

    const responseRef = snapshot.payload.record_refs.response_integrity_ref;
    const responseRefSeen =
      responseRef !== null && seenResponseRefs.has(responseRef);
    if (
      snapshot.payload.dimensions.response_integrity === "FAILED" ||
      snapshot.payload.dimensions.response_integrity === "PARTIAL"
    ) {
      responseRecoveryRequired = true;
    } else if (responseRecoveryRequired) {
      if (snapshot.payload.dimensions.response_integrity === "VERIFIED") {
        if (responseRef === null || responseRefSeen) {
          reasons.push("RESPONSE_INTEGRITY_EVIDENCE_REUSED");
        } else {
          responseRecoveryRequired = false;
        }
      } else {
        reasons.push("RESPONSE_INTEGRITY_RECOVERY_UNVERIFIED");
      }
    }
    if (responseRef !== null) seenResponseRefs.add(responseRef);
  }

  return {
    valid: reasons.length === 0,
    reason_codes: reasons.length === 0 ? ["OK"] : [...new Set(reasons)].sort()
  };
}
