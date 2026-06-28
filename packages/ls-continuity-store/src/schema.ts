import { z } from "zod";

const objectType = z.enum([
  "intent",
  "governance_decision",
  "governance_outcome",
  "continuation_checkpoint",
  "verification_receipt",
  "remediation_receipt"
]);

export const envelopeSchema = z.object({
  schema: z.literal("ls.continuity.v1"),
  object_type: objectType,
  object_id: z.string().startsWith("sha256:").optional(),
  subject_id: z.string().min(1),
  previous_ref: z.string().startsWith("sha256:").nullable().optional(),
  created_at: z.string().datetime(),
  payload: z.record(z.unknown()),
  extensions: z.record(z.unknown()).optional()
});
