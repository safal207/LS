#!/usr/bin/env node

import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {strictParse} from './canonical-runtime-v0.12.mjs';
import {
  CHECKPOINT_INTEGRITY_REASONS,
  isObject,
  timestamp,
  verifyTransparencyLog as verifyTransparencyLogRaw,
} from './transparency-log-v0.14.mjs';

export function verifyTransparencyLogStrict(bundle, nowMs) {
  const raw = verifyTransparencyLogRaw(bundle, nowMs);
  const reasonCodes = Array.isArray(raw.reason_codes)
    ? [...raw.reason_codes]
    : [];
  const checkpointIntegrityValid = !reasonCodes.some(
    (reason) => CHECKPOINT_INTEGRITY_REASONS.has(reason),
  );
  return {
    valid: raw.valid === true && checkpointIntegrityValid,
    local_witnessed_freshness_valid: raw.local_witnessed_freshness_valid,
    entry_integrity_valid: raw.entry_integrity_valid,
    log_checkpoint_integrity_valid: checkpointIntegrityValid,
    log_checkpoint_signature_valid: raw.log_checkpoint_signature_valid,
    log_checkpoint_authority_valid: raw.log_checkpoint_authority_valid,
    log_checkpoint_freshness_valid: raw.log_checkpoint_freshness_valid,
    inclusion_valid: raw.inclusion_valid,
    consistency_valid: raw.consistency_valid,
    view_consistency_valid: raw.view_consistency_valid,
    log_equivocation_detected: raw.log_equivocation_detected,
    accepted_tree_size: raw.accepted_tree_size,
    accepted_root_hash: raw.accepted_root_hash,
    reason_codes: reasonCodes,
  };
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const inputPath = process.argv[2];
  if (!inputPath) {
    process.stderr.write(
      'usage: node reference/transparency-log-strict-v0.14.mjs <bundle-or-fixture.json> [now_ms]\n',
    );
    process.exit(2);
  }
  const input = strictParse(fs.readFileSync(inputPath, 'utf8'));
  const bundle = isObject(input) && isObject(input.base_bundle)
    ? input.base_bundle
    : input;
  const nowMs = isObject(input) && timestamp(input.base_now_ms)
    ? input.base_now_ms
    : Number(process.argv[3]);
  const result = verifyTransparencyLogStrict(bundle, nowMs);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.valid) process.exitCode = 1;
}
