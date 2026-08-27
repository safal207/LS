import { z } from "zod";

export const OBJECT_REF_RE = /^sha256:[0-9a-f]{64}$/;

const objectRef = z.string().regex(OBJECT_REF_RE);
const baseFields = {
  schema: z.literal("ls.continuity.v1"),
  object_id: objectRef.optional(),
  subject_id: z.string().min(1),
  previous_ref: objectRef.nullable().optional(),
  created_at: z.string().datetime(),
  extensions: z.record(z.unknown()).optional()
};

const intentPayload = z.object({
  action: z.string().min(1),
  target: z.string().min(1).optional(),
  params_digest: objectRef
}).strict();

const governanceDecisionPayload = z.object({
  intent_ref: objectRef,
  decision: z.enum(["allow", "deny", "require_approval", "revise"]),
  validity_state: z.enum(["active", "expired", "superseded", "invalidated"]),
  resume_posture: z.enum([
    "retryable",
    "requires_revalidation",
    "consumed",
    "non_retryable",
    "pending_approval"
  ]),
  expires_at: z.string().datetime().nullable().optional(),
  revalidate_if: z.array(z.string().min(1)).optional(),
  continuation_id: z.string().min(1).nullable().optional()
}).strict().superRefine((payload, context) => {
  const expected =
    payload.decision === "require_approval"
      ? "pending_approval"
      : payload.decision === "deny"
        ? "non_retryable"
        : payload.decision === "revise"
          ? "requires_revalidation"
          : null;

  if (expected && payload.resume_posture !== expected) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["resume_posture"],
      message: `decision ${payload.decision} requires resume_posture ${expected}`
    });
  }

  if (payload.decision === "allow" && payload.resume_posture === "pending_approval") {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["resume_posture"],
      message: "allow decisions cannot remain pending approval"
    });
  }
});

const governanceOutcomePayload = z.object({
  decision_ref: objectRef,
  status: z.enum(["executed", "blocked", "errored", "refused"]),
  result_digest: objectRef.nullable().optional(),
  side_effect_committed: z.boolean()
}).strict();

const continuationCheckpointPayload = z.object({
  latest_decision_ref: objectRef.nullable().optional(),
  latest_outcome_ref: objectRef.nullable().optional(),
  pending_approval_ref: objectRef.nullable().optional(),
  validity_state: z.enum(["active", "expired", "superseded", "invalidated"]),
  resume_posture: z.enum([
    "retryable",
    "requires_revalidation",
    "consumed",
    "non_retryable",
    "pending_approval"
  ]),
  required_checks: z.array(z.string().min(1)).optional()
}).strict();

/** Runtime validator aligned with the JSON Schema envelope contract. */
export const envelopeSchema = z.discriminatedUnion("object_type", [
  z.object({ ...baseFields, object_type: z.literal("intent"), payload: intentPayload }).strict(),
  z.object({ ...baseFields, object_type: z.literal("governance_decision"), payload: governanceDecisionPayload }).strict(),
  z.object({ ...baseFields, object_type: z.literal("governance_outcome"), payload: governanceOutcomePayload }).strict(),
  z.object({ ...baseFields, object_type: z.literal("continuation_checkpoint"), payload: continuationCheckpointPayload }).strict(),
  z.object({ ...baseFields, object_type: z.literal("verification_receipt"), payload: z.record(z.unknown()) }).strict(),
  z.object({ ...baseFields, object_type: z.literal("remediation_receipt"), payload: z.record(z.unknown()) }).strict()
]);
