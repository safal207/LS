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
const TRUST_ROOT_PROFILE_ID = 'vtl-canonical-trust-root/v0.12';
const ED25519 = 'ED25519';
const PUBLIC_KEY_BYTES = 32;
const SIGNATURE_BYTES = 64;

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
function nonEmptyString(value) { return typeof value === 'string' && value.length > 0; }
function integer(value) { return Number.isSafeInteger(value); }
function timestamp(value) { return integer(value) && value >= 0; }
function positiveInteger(value) { return integer(value) && value >= 1; }
function hex64(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
function nullableHex64(value) { return value === null || hex64(value); }
function isObject(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function exactObject(value, fields) {
  if (!isObject(value)) return false;
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}

function decodeBase64(value) {
  try {
    if (typeof value !== 'string') return null;
    const decoded = Buffer.from(value, 'base64');
    return decoded.toString('base64') === value ? decoded : null;
  } catch {
    return null;
  }
}

function canonicalBase64(value, length = null) {
  if (!nonEmptyString(value)) return false;
  const decoded = decodeBase64(value);
  return decoded !== null && (length === null || decoded.length === length);
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

const SNAPSHOT_FIELDS = new Set([
  ...STATEMENT_FIELDS, 'snapshot_id', 'signature', 'trust_root',
]);
const TRUST_ROOT_FIELDS = new Set([
  'profile_id', 'trust_root_id', 'policy_version', 'allowed_algorithms', 'keys',
]);
const TRUST_ROOT_KEY_FIELDS = new Set([
  'signer_key_id', 'issuer_id', 'algorithm', 'public_key_base64',
  'not_before_ms', 'not_after_ms', 'revoked',
]);
const BOOTSTRAP_AUTHORITY_FIELDS = new Set([
  'profile_id', 'bootstrap_authority_id', 'allowed_algorithms', 'keys',
]);
const BOOTSTRAP_KEY_FIELDS = new Set([
  'bootstrap_key_id', 'issuer_id', 'algorithm', 'public_key_base64',
  'not_before_ms', 'not_after_ms', 'revoked',
]);
const CHECKPOINT_FIELDS = new Set([
  'profile_id', 'trust_root_id', 'minimum_generation', 'known_generation',
  'known_snapshot_digest', 'checkpointed_at_ms',
]);
const FIXTURE_FIELDS = new Set([
  'profile_id', 'schema_version', 'canonical_profile', 'base_now_ms',
  'bootstrap_authority', 'base_snapshot', 'snapshot_variants', 'checkpoints',
  'expected_fresh_signed_payload_base64', 'expected_fresh_signature_base64',
  'expected_fresh_snapshot_digest', 'cases',
]);
const CASE_REQUIRED_FIELDS = new Set(['id', 'checkpoint_ref', 'expected']);
const CASE_ALLOWED_FIELDS = new Set([
  ...CASE_REQUIRED_FIELDS, 'variant_ref', 'snapshot_mutations',
  'bootstrap_mutations', 'checkpoint_mutations',
]);
const EXPECTED_FIELDS = new Set([
  'valid', 'snapshot_integrity_valid', 'canonical_profile_valid',
  'bootstrap_signature_valid', 'bootstrap_authority_valid', 'freshness_valid',
  'continuity_valid', 'reason_codes',
]);
const MUTATION_FIELDS = new Set(['path', 'value']);
const DANGEROUS_PATH_PARTS = new Set(['__proto__', 'prototype', 'constructor']);
const PATH_PART_RE = /^(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)$/;

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
  add(reasons, 'SNAPSHOT_FIELDS_INVALID', !exactObject(snapshot, SNAPSHOT_FIELDS));
  const required = {
    snapshot_id: nonEmptyString,
    profile_id: (value) => value === PROFILE_ID,
    schema_version: (value) => value === SCHEMA_VERSION,
    canonical_profile: nonEmptyString,
    trust_root_id: nonEmptyString,
    policy_version: nonEmptyString,
    generation: positiveInteger,
    previous_snapshot_digest: nullableHex64,
    trust_root_digest: hex64,
    issued_at_ms: timestamp,
    not_before_ms: timestamp,
    not_after_ms: timestamp,
    issuer_id: nonEmptyString,
    bootstrap_authority_id: nonEmptyString,
    bootstrap_key_id: nonEmptyString,
    signature_algorithm: nonEmptyString,
    signature: (value) => canonicalBase64(value, SIGNATURE_BYTES),
  };
  for (const [field, predicate] of Object.entries(required)) {
    if (!(field in snapshot) || !predicate(snapshot[field])) add(reasons, `SNAPSHOT_SCHEMA_INVALID:${field}`, true);
  }
  const root = snapshot.trust_root;
  if (!isObject(root)) {
    add(reasons, 'SNAPSHOT_SCHEMA_INVALID:trust_root', true);
  } else {
    add(reasons, 'SNAPSHOT_TRUST_ROOT_FIELDS_INVALID', !exactObject(root, TRUST_ROOT_FIELDS));
    add(reasons, 'SNAPSHOT_TRUST_ROOT_PROFILE_INVALID', root.profile_id !== TRUST_ROOT_PROFILE_ID);
    add(reasons, 'SNAPSHOT_TRUST_ROOT_ID_INVALID', !nonEmptyString(root.trust_root_id));
    add(reasons, 'SNAPSHOT_TRUST_POLICY_INVALID', !nonEmptyString(root.policy_version));
    add(
      reasons,
      'SNAPSHOT_TRUST_ALGORITHMS_INVALID',
      !Array.isArray(root.allowed_algorithms)
        || root.allowed_algorithms.length === 0
        || !root.allowed_algorithms.every(nonEmptyString)
        || new Set(root.allowed_algorithms).size !== root.allowed_algorithms.length,
    );
    if (!Array.isArray(root.keys) || root.keys.length === 0) {
      add(reasons, 'SNAPSHOT_TRUST_KEYS_INVALID', true);
    } else {
      root.keys.forEach((key, index) => {
        if (!isObject(key)) {
          add(reasons, `SNAPSHOT_TRUST_KEY_INVALID:${index}`, true);
          return;
        }
        add(
          reasons,
          `SNAPSHOT_TRUST_KEY_FIELDS_INVALID:${index}`,
          !exactObject(key, TRUST_ROOT_KEY_FIELDS),
        );
        const specs = {
          signer_key_id: nonEmptyString,
          issuer_id: nonEmptyString,
          algorithm: nonEmptyString,
          public_key_base64: (value) => canonicalBase64(value, PUBLIC_KEY_BYTES),
          not_before_ms: timestamp,
          not_after_ms: timestamp,
          revoked: (value) => typeof value === 'boolean',
        };
        for (const [field, predicate] of Object.entries(specs)) {
          if (!(field in key) || !predicate(key[field])) {
            add(reasons, `SNAPSHOT_TRUST_KEY_SCHEMA_INVALID:${index}.${field}`, true);
          }
        }
      });
    }
  }
  return reasons;
}

function validateBootstrapAuthorityShape(authority) {
  if (!isObject(authority)) return ['BOOTSTRAP_AUTHORITY_INVALID'];
  const reasons = [];
  add(
    reasons,
    'BOOTSTRAP_AUTHORITY_FIELDS_INVALID',
    !exactObject(authority, BOOTSTRAP_AUTHORITY_FIELDS),
  );
  add(reasons, 'BOOTSTRAP_PROFILE_INVALID', authority.profile_id !== BOOTSTRAP_PROFILE_ID);
  add(reasons, 'BOOTSTRAP_AUTHORITY_ID_INVALID', !nonEmptyString(authority.bootstrap_authority_id));
  add(
    reasons,
    'BOOTSTRAP_ALLOWED_ALGORITHMS_INVALID',
      !Array.isArray(authority.allowed_algorithms)
        || authority.allowed_algorithms.length === 0
        || !authority.allowed_algorithms.every(nonEmptyString)
        || new Set(authority.allowed_algorithms).size !== authority.allowed_algorithms.length,
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
    add(
      reasons,
      `BOOTSTRAP_KEY_FIELDS_INVALID:${index}`,
      !exactObject(key, BOOTSTRAP_KEY_FIELDS),
    );
    const specs = {
      bootstrap_key_id: nonEmptyString,
      issuer_id: nonEmptyString,
      algorithm: nonEmptyString,
      public_key_base64: nonEmptyString,
      not_before_ms: timestamp,
      not_after_ms: timestamp,
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
  add(reasons, 'CHECKPOINT_FIELDS_INVALID', !exactObject(checkpoint, CHECKPOINT_FIELDS));
  add(reasons, 'CHECKPOINT_PROFILE_INVALID', checkpoint.profile_id !== CHECKPOINT_PROFILE_ID);
  add(reasons, 'CHECKPOINT_TRUST_ROOT_ID_INVALID', !nonEmptyString(checkpoint.trust_root_id));
  add(reasons, 'CHECKPOINT_MINIMUM_GENERATION_INVALID', !positiveInteger(checkpoint.minimum_generation));
  add(reasons, 'CHECKPOINT_TIME_INVALID', !timestamp(checkpoint.checkpointed_at_ms));
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
  try {
    snapshot = structuredClone(snapshot);
    bootstrapAuthority = structuredClone(bootstrapAuthority);
    checkpoint = structuredClone(checkpoint);
  } catch {
    return invalidResult(['INPUT_SNAPSHOT_FAILED']);
  }
  const reasons = validateSnapshotShape(snapshot);
  for (const reason of validateBootstrapAuthorityShape(bootstrapAuthority)) add(reasons, reason, true);
  for (const reason of validateCheckpointShape(checkpoint)) add(reasons, reason, true);
  add(reasons, 'NOW_MS_INVALID', !timestamp(nowMs));
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
    const keyIntervalValid = timestamp(key.not_before_ms)
      && timestamp(key.not_after_ms)
      && key.not_after_ms >= key.not_before_ms;
    add(authorityReasons, 'BOOTSTRAP_KEY_VALIDITY_INVALID', !keyIntervalValid);
    add(
      authorityReasons,
      'BOOTSTRAP_KEY_NOT_CURRENT',
      keyIntervalValid && (nowMs < key.not_before_ms || nowMs > key.not_after_ms),
    );
    const publicKey = decodeBase64(key.public_key_base64);
    const signature = decodeBase64(snapshot.signature);
    const keyMaterialValid = publicKey !== null && publicKey.length === PUBLIC_KEY_BYTES;
    const signatureMaterialValid = signature !== null && signature.length === SIGNATURE_BYTES;
    add(authorityReasons, 'BOOTSTRAP_KEY_MATERIAL_INVALID', !keyMaterialValid);

    if (algorithmAllowed && key.algorithm === ED25519 && keyMaterialValid && signatureMaterialValid) {
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
  const fail = () => { throw new Error('FIXTURE_SCHEMA_INVALID'); };
  if (!nonEmptyString(path)) fail();
  const parts = path.split('.');
  if (parts.some((part) => DANGEROUS_PATH_PARTS.has(part) || !PATH_PART_RE.test(part))) fail();
  let cursor = document;
  for (const part of parts.slice(0, -1)) {
    if (Array.isArray(cursor)) {
      const index = Number(part);
      if (!/^\d+$/.test(part) || index >= cursor.length) fail();
      cursor = cursor[index];
    } else if (isObject(cursor) && Object.hasOwn(cursor, part)) {
      cursor = cursor[part];
    } else {
      fail();
    }
  }
  const last = parts.at(-1);
  let previous;
  if (Array.isArray(cursor)) {
    const index = Number(last);
    if (!/^\d+$/.test(last) || index >= cursor.length) fail();
    previous = cursor[index];
  } else if (isObject(cursor) && Object.hasOwn(cursor, last)) {
    previous = cursor[last];
  } else {
    fail();
  }
  try {
    if (canonicalBytes(previous).equals(canonicalBytes(value))) fail();
  } catch {
    fail();
  }
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

function validateFixtureShape(fixture) {
  const fail = () => { throw new Error('FIXTURE_SCHEMA_INVALID'); };
  if (!exactObject(fixture, FIXTURE_FIELDS)) fail();
  if (fixture.profile_id !== PROFILE_ID) fail();
  if (fixture.schema_version !== FIXTURE_SCHEMA_VERSION) fail();
  if (fixture.canonical_profile !== CANONICAL_PROFILE) fail();
  if (!timestamp(fixture.base_now_ms)) fail();

  if (validateSnapshotShape(fixture.base_snapshot).length > 0) fail();
  if (validateBootstrapAuthorityShape(fixture.bootstrap_authority).length > 0) fail();

  const variants = fixture.snapshot_variants;
  if (!isObject(variants)) fail();
  for (const [name, variant] of Object.entries(variants)) {
    if (!nonEmptyString(name) || !isObject(variant) || Object.keys(variant).length === 0) fail();
    for (const [field, value] of Object.entries(variant)) {
      if (!Object.hasOwn(fixture.base_snapshot, field)) fail();
      try {
        if (canonicalBytes(value).equals(canonicalBytes(fixture.base_snapshot[field]))) fail();
      } catch {
        fail();
      }
    }
    if (validateSnapshotShape(applyVariant(fixture.base_snapshot, variant)).length > 0) fail();
  }

  const checkpoints = fixture.checkpoints;
  if (!isObject(checkpoints) || Object.keys(checkpoints).length === 0) fail();
  for (const [name, checkpoint] of Object.entries(checkpoints)) {
    if (!nonEmptyString(name) || validateCheckpointShape(checkpoint).length > 0) fail();
  }

  if (!canonicalBase64(fixture.expected_fresh_signed_payload_base64)) fail();
  if (!canonicalBase64(fixture.expected_fresh_signature_base64, SIGNATURE_BYTES)) fail();
  if (!hex64(fixture.expected_fresh_snapshot_digest)) fail();
  if (!Array.isArray(fixture.cases) || fixture.cases.length === 0) fail();

  const identifiers = new Set();
  const referencedVariants = new Set();
  const referencedCheckpoints = new Set();
  for (const testCase of fixture.cases) {
    if (!isObject(testCase)) fail();
    const caseFields = Object.keys(testCase);
    if (
      ![...CASE_REQUIRED_FIELDS].every((field) => Object.hasOwn(testCase, field))
      || !caseFields.every((field) => CASE_ALLOWED_FIELDS.has(field))
    ) fail();
    if (!nonEmptyString(testCase.id) || identifiers.has(testCase.id)) fail();
    identifiers.add(testCase.id);

    if (
      !nonEmptyString(testCase.checkpoint_ref)
      || !Object.hasOwn(checkpoints, testCase.checkpoint_ref)
    ) fail();
    referencedCheckpoints.add(testCase.checkpoint_ref);

    let variant = null;
    if (Object.hasOwn(testCase, 'variant_ref')) {
      if (!nonEmptyString(testCase.variant_ref) || !Object.hasOwn(variants, testCase.variant_ref)) fail();
      referencedVariants.add(testCase.variant_ref);
      variant = variants[testCase.variant_ref];
    }

    if (!exactObject(testCase.expected, EXPECTED_FIELDS)) fail();
    for (const field of EXPECTED_FIELDS) {
      if (field !== 'reason_codes' && typeof testCase.expected[field] !== 'boolean') fail();
    }
    const reasonCodes = testCase.expected.reason_codes;
    if (
      !Array.isArray(reasonCodes)
      || !reasonCodes.every(nonEmptyString)
      || new Set(reasonCodes).size !== reasonCodes.length
    ) fail();

    const documents = new Map([
      ['snapshot_mutations', applyVariant(fixture.base_snapshot, variant)],
      ['bootstrap_mutations', structuredClone(fixture.bootstrap_authority)],
      ['checkpoint_mutations', structuredClone(checkpoints[testCase.checkpoint_ref])],
    ]);
    for (const [groupName, document] of documents) {
      const mutations = testCase[groupName] ?? [];
      if (!Array.isArray(mutations)) fail();
      for (const mutation of mutations) {
        if (!exactObject(mutation, MUTATION_FIELDS)) fail();
        setPath(document, mutation.path, mutation.value);
      }
    }
  }
  if (
    referencedVariants.size !== Object.keys(variants).length
    || !Object.keys(variants).every((name) => referencedVariants.has(name))
  ) fail();
  if (
    referencedCheckpoints.size !== Object.keys(checkpoints).length
    || !Object.keys(checkpoints).every((name) => referencedCheckpoints.has(name))
  ) fail();
}

function runFixture(fixture) {
  if (!isObject(fixture)) throw new Error('FIXTURE_SCHEMA_INVALID');
  try { fixture = structuredClone(fixture); } catch { throw new Error('FIXTURE_SCHEMA_INVALID'); }
  validateFixtureShape(fixture);
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
      passed: canonicalSha256(actual) === canonicalSha256(testCase.expected),
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
        && baseResult.valid
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
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (!result.summary.all_passed) process.exitCode = 1;
