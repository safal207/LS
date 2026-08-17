#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';
import {
  CANONICAL_PROFILE,
  canonicalBytes,
  canonicalSha256,
  strictParse,
} from './canonical-runtime-v0.12.mjs';

const PROFILE_ID = 'vtl-canonical-trust-root-snapshot-v0.12';
const SCHEMA_VERSION = 'vtl.canonical-trust-root-snapshot/v0.12';
const FIXTURE_SCHEMA_VERSION = 'vtl.canonical-trust-root-snapshot-fixture/v0.12';
const BOOTSTRAP_PROFILE_ID = 'vtl-canonical-bootstrap-authority/v0.12';
const CHECKPOINT_PROFILE_ID = 'vtl-canonical-trust-checkpoint/v0.12';
const TRUST_ROOT_PROFILE_ID = 'vtl-canonical-trust-root/v0.11';
const ED25519 = 'ED25519';

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
function nonEmptyString(value) { return typeof value === 'string' && value.length > 0; }
function integer(value) { return Number.isSafeInteger(value); }
function positiveInteger(value) { return integer(value) && value >= 1; }
function hex64(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
function nullableHex64(value) { return value === null || hex64(value); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }

function decodeBase64(value) {
  try {
    if (typeof value !== 'string') return null;
    const decoded = Buffer.from(value, 'base64');
    return decoded.toString('base64') === value ? decoded : null;
  } catch {
    return null;
  }
}

const STATEMENT_FIELDS = [
  'profile_id',
  'schema_version',
  'canonical_profile',
  'trust_root_id',
  'policy_version',
  'generation',
  'previous_snapshot_digest',
  'trust_root_digest',
  'issued_at_ms',
  'not_before_ms',
  'not_after_ms',
  'issuer_id',
  'bootstrap_authority_id',
  'bootstrap_key_id',
  'signature_algorithm',
];

function snapshotStatement(snapshot) {
  const result = {};
  for (const field of STATEMENT_FIELDS) result[field] = snapshot?.[field];
  return result;
}
function computeSnapshotId(snapshot) {
  return `snapshot_${canonicalSha256(snapshotStatement(snapshot)).slice(0, 24)}`;
}
function signedSnapshotPayload(snapshot) {
  return canonicalBytes({snapshot_id: snapshot?.snapshot_id, ...snapshotStatement(snapshot)});
}
function trustRootDigest(root) { return canonicalSha256(root); }
function snapshotDigest(snapshot) { return canonicalSha256(snapshot); }

function invalidResult(reasonCodes) {
  return {
    valid: false,
    snapshot_integrity_valid: false,
    canonical_profile_valid: false,
    bootstrap_signature_valid: false,
    bootstrap_authority_valid: false,
    freshness_valid: false,
    continuity_valid: false,
    signed_payload_base64: '',
    snapshot_digest: null,
    reason_codes: reasonCodes,
  };
}

function validateSnapshotShape(snapshot) {
  if (!isObject(snapshot)) return ['SNAPSHOT_ROOT_INVALID'];
  const reasons = [];
  const required = {
    snapshot_id: nonEmptyString,
    profile_id: nonEmptyString,
    schema_version: nonEmptyString,
    canonical_profile: nonEmptyString,
    trust_root_id: nonEmptyString,
    policy_version: nonEmptyString,
    generation: positiveInteger,
    previous_snapshot_digest: nullableHex64,
    trust_root_digest: hex64,
    issued_at_ms: integer,
    not_before_ms: integer,
    not_after_ms: integer,
    issuer_id: nonEmptyString,
    bootstrap_authority_id: nonEmptyString,
    bootstrap_key_id: nonEmptyString,
    signature_algorithm: nonEmptyString,
    signature: nonEmptyString,
  };
  for (const [field, predicate] of Object.entries(required)) {
    if (!(field in snapshot) || !predicate(snapshot[field])) add(reasons, `SNAPSHOT_SCHEMA_INVALID:${field}`, true);
  }
  const root = snapshot.trust_root;
  if (!isObject(root)) {
    add(reasons, 'SNAPSHOT_SCHEMA_INVALID:trust_root', true);
  } else {
    add(reasons, 'SNAPSHOT_TRUST_ROOT_PROFILE_INVALID', root.profile_id !== TRUST_ROOT_PROFILE_ID);
    add(reasons, 'SNAPSHOT_TRUST_ROOT_ID_INVALID', !nonEmptyString(root.trust_root_id));
    add(reasons, 'SNAPSHOT_TRUST_POLICY_INVALID', !nonEmptyString(root.policy_version));
    add(
      reasons,
      'SNAPSHOT_TRUST_ALGORITHMS_INVALID',
      !Array.isArray(root.allowed_algorithms)
        || root.allowed_algorithms.length === 0
        || !root.allowed_algorithms.every(nonEmptyString),
    );
    add(reasons, 'SNAPSHOT_TRUST_KEYS_INVALID', !Array.isArray(root.keys));
  }
  return reasons;
}

function validateBootstrapAuthorityShape(authority) {
  if (!isObject(authority)) return ['BOOTSTRAP_AUTHORITY_INVALID'];
  const reasons = [];
  add(reasons, 'BOOTSTRAP_PROFILE_INVALID', authority.profile_id !== BOOTSTRAP_PROFILE_ID);
  add(reasons, 'BOOTSTRAP_AUTHORITY_ID_INVALID', !nonEmptyString(authority.bootstrap_authority_id));
  add(
    reasons,
    'BOOTSTRAP_ALLOWED_ALGORITHMS_INVALID',
    !Array.isArray(authority.allowed_algorithms)
      || authority.allowed_algorithms.length === 0
      || !authority.allowed_algorithms.every(nonEmptyString),
  );
  const keys = authority.keys;
  if (!Array.isArray(keys) || keys.length === 0) {
    add(reasons, 'BOOTSTRAP_KEYS_INVALID', true);
    return reasons;
  }
  keys.forEach((key, index) => {
    if (!isObject(key)) {
      add(reasons, `BOOTSTRAP_KEY_INVALID:${index}`, true);
      return;
    }
    const specs = {
      bootstrap_key_id: nonEmptyString,
      issuer_id: nonEmptyString,
      algorithm: nonEmptyString,
      public_key_base64: nonEmptyString,
      not_before_ms: integer,
      not_after_ms: integer,
      revoked: (value) => typeof value === 'boolean',
    };
    for (const [field, predicate] of Object.entries(specs)) {
      if (!(field in key) || !predicate(key[field])) add(reasons, `BOOTSTRAP_KEY_SCHEMA_INVALID:${index}.${field}`, true);
    }
  });
  return reasons;
}

function validateCheckpointShape(checkpoint) {
  if (!isObject(checkpoint)) return ['CHECKPOINT_INVALID'];
  const reasons = [];
  add(reasons, 'CHECKPOINT_PROFILE_INVALID', checkpoint.profile_id !== CHECKPOINT_PROFILE_ID);
  add(reasons, 'CHECKPOINT_TRUST_ROOT_ID_INVALID', !nonEmptyString(checkpoint.trust_root_id));
  add(reasons, 'CHECKPOINT_MINIMUM_GENERATION_INVALID', !positiveInteger(checkpoint.minimum_generation));
  add(reasons, 'CHECKPOINT_TIME_INVALID', !integer(checkpoint.checkpointed_at_ms));
  const knownGeneration = checkpoint.known_generation;
  const knownDigest = checkpoint.known_snapshot_digest;
  if ((knownGeneration === null || knownGeneration === undefined) !== (knownDigest === null || knownDigest === undefined)) {
    add(reasons, 'CHECKPOINT_KNOWN_STATE_INCOMPLETE', true);
  } else if (knownGeneration !== null && knownGeneration !== undefined) {
    add(reasons, 'CHECKPOINT_KNOWN_GENERATION_INVALID', !positiveInteger(knownGeneration));
    add(reasons, 'CHECKPOINT_KNOWN_DIGEST_INVALID', !hex64(knownDigest));
  }
  return reasons;
}

function verifyCanonicalTrustSnapshot(snapshot, bootstrapAuthority, checkpoint, nowMs) {
  const reasons = validateSnapshotShape(snapshot);
  for (const reason of validateBootstrapAuthorityShape(bootstrapAuthority)) add(reasons, reason, true);
  for (const reason of validateCheckpointShape(checkpoint)) add(reasons, reason, true);
  add(reasons, 'NOW_MS_INVALID', !integer(nowMs));
  if (reasons.length > 0) return invalidResult(reasons);

  let currentSnapshotDigest;
  let currentRootDigest;
  let expectedSnapshotId;
  let signed;
  try {
    currentSnapshotDigest = snapshotDigest(snapshot);
    currentRootDigest = trustRootDigest(snapshot.trust_root);
    expectedSnapshotId = computeSnapshotId(snapshot);
    signed = signedSnapshotPayload(snapshot);
  } catch (error) {
    return invalidResult([`CANONICALIZATION_ERROR:${error.code ?? 'UNKNOWN'}`]);
  }

  const signedPayloadBase64 = signed.toString('base64');
  const canonicalProfileValid = snapshot.canonical_profile === CANONICAL_PROFILE;

  const integrityReasons = [];
  add(integrityReasons, 'CANONICAL_PROFILE_MISMATCH', !canonicalProfileValid);
  add(integrityReasons, 'TRUST_ROOT_DIGEST_MISMATCH', snapshot.trust_root_digest !== currentRootDigest);
  add(integrityReasons, 'TRUST_ROOT_ID_MISMATCH', snapshot.trust_root_id !== snapshot.trust_root.trust_root_id);
  add(integrityReasons, 'TRUST_POLICY_VERSION_MISMATCH', snapshot.policy_version !== snapshot.trust_root.policy_version);
  add(integrityReasons, 'SNAPSHOT_ID_INVALID', snapshot.snapshot_id !== expectedSnapshotId);
  for (const reason of integrityReasons) add(reasons, reason, true);
  const snapshotIntegrityValid = integrityReasons.length === 0;

  const authorityReasons = [];
  add(
    authorityReasons,
    'BOOTSTRAP_AUTHORITY_MISMATCH',
    snapshot.bootstrap_authority_id !== bootstrapAuthority.bootstrap_authority_id,
  );
  const algorithm = snapshot.signature_algorithm;
  const algorithmAllowed = algorithm === ED25519 && bootstrapAuthority.allowed_algorithms.includes(algorithm);
  add(authorityReasons, 'BOOTSTRAP_ALGORITHM_NOT_ALLOWED', !algorithmAllowed);

  const matchingKeys = bootstrapAuthority.keys.filter(
    (key) => isObject(key) && key.bootstrap_key_id === snapshot.bootstrap_key_id,
  );
  add(authorityReasons, 'BOOTSTRAP_KEY_NOT_TRUSTED', matchingKeys.length === 0);
  add(authorityReasons, 'BOOTSTRAP_KEY_AMBIGUOUS', matchingKeys.length > 1);
  const key = matchingKeys.length === 1 ? matchingKeys[0] : null;

  let bootstrapSignatureValid = false;
  if (key) {
    add(authorityReasons, 'BOOTSTRAP_ISSUER_MISMATCH', key.issuer_id !== snapshot.issuer_id);
    add(authorityReasons, 'BOOTSTRAP_KEY_ALGORITHM_MISMATCH', key.algorithm !== algorithm);
    add(authorityReasons, 'BOOTSTRAP_KEY_REVOKED', key.revoked === true);
    const keyIntervalValid = integer(key.not_before_ms)
      && integer(key.not_after_ms)
      && key.not_after_ms >= key.not_before_ms;
    add(authorityReasons, 'BOOTSTRAP_KEY_VALIDITY_INVALID', !keyIntervalValid);
    add(
      authorityReasons,
      'BOOTSTRAP_KEY_NOT_CURRENT',
      keyIntervalValid && (nowMs < key.not_before_ms || nowMs > key.not_after_ms),
    );
    const publicKey = decodeBase64(key.public_key_base64);
    const signature = decodeBase64(snapshot.signature);
    const keyMaterialValid = publicKey !== null && publicKey.length === 32;
    add(authorityReasons, 'BOOTSTRAP_KEY_MATERIAL_INVALID', !keyMaterialValid);

    if (algorithmAllowed && key.algorithm === ED25519 && keyMaterialValid && signature !== null) {
      try {
        const spki = Buffer.concat([
          Buffer.from('302a300506032b6570032100', 'hex'),
          publicKey,
        ]);
        const publicKeyObject = crypto.createPublicKey({key: spki, format: 'der', type: 'spki'});
        bootstrapSignatureValid = crypto.verify(null, signed, publicKeyObject, signature);
      } catch {
        bootstrapSignatureValid = false;
      }
    }
    add(
      reasons,
      'SNAPSHOT_SIGNATURE_INVALID',
      !bootstrapSignatureValid && algorithmAllowed && keyMaterialValid,
    );
  }
  for (const reason of authorityReasons) add(reasons, reason, true);
  const bootstrapAuthorityValid = authorityReasons.length === 0;

  const freshnessReasons = [];
  const validityIntervalValid = snapshot.not_after_ms >= snapshot.not_before_ms;
  add(freshnessReasons, 'SNAPSHOT_VALIDITY_INVALID', !validityIntervalValid);
  add(freshnessReasons, 'SNAPSHOT_NOT_YET_VALID', validityIntervalValid && nowMs < snapshot.not_before_ms);
  add(freshnessReasons, 'SNAPSHOT_EXPIRED', validityIntervalValid && nowMs > snapshot.not_after_ms);
  add(freshnessReasons, 'SNAPSHOT_ISSUED_IN_FUTURE', snapshot.issued_at_ms > nowMs);
  add(freshnessReasons, 'CHECKPOINT_FROM_FUTURE', checkpoint.checkpointed_at_ms > nowMs);
  add(freshnessReasons, 'SNAPSHOT_GENERATION_BELOW_FLOOR', snapshot.generation < checkpoint.minimum_generation);
  for (const reason of freshnessReasons) add(reasons, reason, true);
  const freshnessValid = freshnessReasons.length === 0;

  const continuityReasons = [];
  add(continuityReasons, 'CHECKPOINT_TRUST_ROOT_MISMATCH', checkpoint.trust_root_id !== snapshot.trust_root_id);
  const knownGeneration = checkpoint.known_generation;
  const knownDigest = checkpoint.known_snapshot_digest;
  if (knownGeneration !== null && knownGeneration !== undefined && knownDigest !== null && knownDigest !== undefined) {
    if (snapshot.generation < knownGeneration) {
      add(continuityReasons, 'SNAPSHOT_ROLLBACK', true);
    } else if (snapshot.generation === knownGeneration) {
      add(continuityReasons, 'SNAPSHOT_FORK_DETECTED', currentSnapshotDigest !== knownDigest);
    } else if (snapshot.generation === knownGeneration + 1) {
      add(
        continuityReasons,
        'PREVIOUS_SNAPSHOT_DIGEST_MISMATCH',
        snapshot.previous_snapshot_digest !== knownDigest,
      );
    } else {
      add(continuityReasons, 'SNAPSHOT_CONTINUITY_GAP', true);
    }
  }
  for (const reason of continuityReasons) add(reasons, reason, true);
  const continuityValid = continuityReasons.length === 0;

  const valid = snapshotIntegrityValid
    && canonicalProfileValid
    && bootstrapSignatureValid
    && bootstrapAuthorityValid
    && freshnessValid
    && continuityValid
    && reasons.length === 0;

  return {
    valid,
    snapshot_integrity_valid: snapshotIntegrityValid,
    canonical_profile_valid: canonicalProfileValid,
    bootstrap_signature_valid: bootstrapSignatureValid,
    bootstrap_authority_valid: bootstrapAuthorityValid,
    freshness_valid: freshnessValid,
    continuity_valid: continuityValid,
    signed_payload_base64: signedPayloadBase64,
    snapshot_digest: currentSnapshotDigest,
    reason_codes: reasons,
  };
}

function setPath(document, path, value) {
  const parts = path.split('.');
  let cursor = document;
  for (const part of parts.slice(0, -1)) cursor = Array.isArray(cursor) ? cursor[Number(part)] : cursor[part];
  const last = parts.at(-1);
  if (Array.isArray(cursor)) cursor[Number(last)] = structuredClone(value);
  else cursor[last] = structuredClone(value);
}

function applyVariant(baseSnapshot, variant) {
  const snapshot = structuredClone(baseSnapshot);
  if (variant) {
    for (const [key, value] of Object.entries(variant)) snapshot[key] = structuredClone(value);
  }
  return snapshot;
}

function runFixture(fixture) {
  const cases = fixture.cases.map((testCase) => {
    const variant = testCase.variant_ref === undefined
      ? null
      : fixture.snapshot_variants[testCase.variant_ref];
    const snapshot = applyVariant(fixture.base_snapshot, variant);
    const authority = structuredClone(fixture.bootstrap_authority);
    const checkpoint = structuredClone(fixture.checkpoints[testCase.checkpoint_ref]);

    for (const mutation of testCase.snapshot_mutations ?? []) setPath(snapshot, mutation.path, mutation.value);
    for (const mutation of testCase.bootstrap_mutations ?? []) setPath(authority, mutation.path, mutation.value);
    for (const mutation of testCase.checkpoint_mutations ?? []) setPath(checkpoint, mutation.path, mutation.value);

    const result = verifyCanonicalTrustSnapshot(snapshot, authority, checkpoint, fixture.base_now_ms);
    const actual = {
      valid: result.valid,
      snapshot_integrity_valid: result.snapshot_integrity_valid,
      canonical_profile_valid: result.canonical_profile_valid,
      bootstrap_signature_valid: result.bootstrap_signature_valid,
      bootstrap_authority_valid: result.bootstrap_authority_valid,
      freshness_valid: result.freshness_valid,
      continuity_valid: result.continuity_valid,
      reason_codes: result.reason_codes,
    };
    return {
      id: testCase.id,
      actual,
      expected: testCase.expected,
      passed: JSON.stringify(actual) === JSON.stringify(testCase.expected),
    };
  });

  const fresh = structuredClone(fixture.base_snapshot);
  const baseResult = verifyCanonicalTrustSnapshot(
    fresh,
    structuredClone(fixture.bootstrap_authority),
    structuredClone(fixture.checkpoints.base),
    fixture.base_now_ms,
  );
  const parity = {
    signed_payload_base64: baseResult.signed_payload_base64,
    signed_payload_matches_expected: baseResult.signed_payload_base64 === fixture.expected_fresh_signed_payload_base64,
    signature_base64: fresh.signature,
    signature_matches_expected: fresh.signature === fixture.expected_fresh_signature_base64,
    snapshot_digest: baseResult.snapshot_digest,
    snapshot_digest_matches_expected: baseResult.snapshot_digest === fixture.expected_fresh_snapshot_digest,
  };
  const passed = cases.filter((result) => result.passed).length;
  return {
    profile_id: PROFILE_ID,
    schema_version: FIXTURE_SCHEMA_VERSION,
    canonical_profile: CANONICAL_PROFILE,
    parity,
    cases,
    summary: {
      total: cases.length,
      passed,
      failed: cases.length - passed,
      all_passed: passed === cases.length
        && parity.signed_payload_matches_expected
        && parity.signature_matches_expected
        && parity.snapshot_digest_matches_expected,
    },
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: node reference/canonical-trust-root-snapshot-v0.12.mjs <fixture.json>');
  process.exit(2);
}
const fixture = strictParse(fs.readFileSync(fixturePath, 'utf8'));
const result = runFixture(fixture);
console.log(JSON.stringify(result, null, 2));
if (!result.summary.all_passed) process.exitCode = 1;
