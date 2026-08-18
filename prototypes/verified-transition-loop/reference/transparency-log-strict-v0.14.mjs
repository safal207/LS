#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const CHECKPOINT_INTEGRITY_REASONS = new Set([
  'CHECKPOINT_INVALID',
  'CHECKPOINT_PROFILE_INVALID',
  'CHECKPOINT_SCHEMA_VERSION_INVALID',
  'CHECKPOINT_LOG_ID_INVALID',
  'CHECKPOINT_TREE_SIZE_INVALID',
  'CHECKPOINT_ROOT_HASH_INVALID',
  'CHECKPOINT_ISSUER_INVALID',
  'CHECKPOINT_AUTHORITY_ID_INVALID',
  'CHECKPOINT_KEY_ID_INVALID',
  'CHECKPOINT_ALGORITHM_INVALID',
  'CHECKPOINT_SIGNATURE_ENCODING_INVALID',
  'CHECKPOINT_ID_INVALID',
]);

function strictActual(actual) {
  const reasonCodes = Array.isArray(actual.reason_codes) ? actual.reason_codes : [];
  const integrityValid = !reasonCodes.some((reason) => CHECKPOINT_INTEGRITY_REASONS.has(reason));
  return {
    valid: actual.valid === true && integrityValid,
    local_witnessed_freshness_valid: actual.local_witnessed_freshness_valid,
    entry_integrity_valid: actual.entry_integrity_valid,
    log_checkpoint_integrity_valid: integrityValid,
    log_checkpoint_signature_valid: actual.log_checkpoint_signature_valid,
    log_checkpoint_authority_valid: actual.log_checkpoint_authority_valid,
    log_checkpoint_freshness_valid: actual.log_checkpoint_freshness_valid,
    inclusion_valid: actual.inclusion_valid,
    consistency_valid: actual.consistency_valid,
    view_consistency_valid: actual.view_consistency_valid,
    log_equivocation_detected: actual.log_equivocation_detected,
    accepted_tree_size: actual.accepted_tree_size,
    accepted_root_hash: actual.accepted_root_hash,
    reason_codes: reasonCodes,
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: transparency log fixture path required');
  process.exit(2);
}

const rawVerifierPath = fileURLToPath(new URL('./transparency-log-v0.14.mjs', import.meta.url));
const child = spawnSync(process.execPath, [rawVerifierPath, fixturePath], {
  encoding: 'utf8',
  maxBuffer: 16 * 1024 * 1024,
});
if (!child.stdout) {
  process.stderr.write(child.stderr ?? 'Node verifier produced no output\n');
  process.exit(1);
}

const result = JSON.parse(child.stdout);
for (const testCase of result.cases ?? []) {
  testCase.actual = strictActual(testCase.actual);
}
console.log(JSON.stringify(result, null, 2));
process.exit(0);
