export type ObjectType =
  | "intent"
  | "governance_decision"
  | "governance_outcome"
  | "continuation_checkpoint"
  | "verification_receipt"
  | "remediation_receipt";

export type DecisionState = "allow" | "deny" | "require_approval" | "revise";
export type ValidityState = "active" | "expired" | "superseded" | "invalidated";
export type ResumePosture =
  | "retryable"
  | "requires_revalidation"
  | "consumed"
  | "non_retryable"
  | "pending_approval";

export interface ContinuityEnvelope<TPayload = Record<string, unknown>> {
  schema: "ls.continuity.v1";
  object_type: ObjectType;
  object_id?: string;
  subject_id: string;
  previous_ref?: string | null;
  created_at: string;
  payload: TPayload;
  extensions?: Record<string, unknown>;
}

export interface StoredContinuityObject<TPayload = Record<string, unknown>>
  extends ContinuityEnvelope<TPayload> {
  object_id: string;
}

export interface GovernanceDecisionPayload {
  intent_ref: string;
  decision: DecisionState;
  validity_state: ValidityState;
  resume_posture: ResumePosture;
  expires_at?: string | null;
  revalidate_if?: string[];
  continuation_id?: string | null;
}

export interface GovernanceOutcomePayload {
  decision_ref: string;
  status: "executed" | "blocked" | "errored" | "refused";
  result_digest?: string | null;
  side_effect_committed: boolean;
}

export interface ContinuationCheckpointPayload {
  latest_decision_ref?: string | null;
  latest_outcome_ref?: string | null;
  pending_approval_ref?: string | null;
  validity_state: ValidityState;
  resume_posture: ResumePosture;
  required_checks?: string[];
}

export interface ContinuationState {
  subject_id: string;
  checkpoint_ref: string | null;
  decision_ref: string | null;
  outcome_ref: string | null;
  validity_state: ValidityState;
  resume_posture: ResumePosture;
  pending_approval_ref: string | null;
  updated_at: string;
}

export interface ResumeDecision {
  allowed: boolean;
  reason:
    | "OK"
    | "NO_STATE"
    | "PENDING_APPROVAL"
    | "REVALIDATION_REQUIRED"
    | "AUTHORITY_CONSUMED"
    | "AUTHORITY_EXPIRED"
    | "AUTHORITY_INVALIDATED"
    | "NON_RETRYABLE";
  checkpoint_ref: string | null;
  required_checks: string[];
}
