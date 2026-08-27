#!/usr/bin/env node

import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import {
  CANONICAL_PROFILE,
  CanonicalizationError,
  canonicalBytes,
  strictParse,
} from './canonical-runtime-v0.12.mjs';
import {
  AUTHORITY_FIELDS,
  BUNDLE_FIELDS,
  CHECKPOINT_FIELDS,
  ED25519,
  FIXTURE_SCHEMA_VERSION,
  KEY_FIELDS,
  MAX_PROOF_NODES,
  PROFILE_ID,
  PUBLIC_KEY_BYTES,
  SIGNATURE_BYTES,
  TARGET_FIELDS,
  VERIFIER_CHECKPOINT_FIELDS,
  authorityShapeReasons,
  checkpointDigest,
  checkpointShapeReasons,
  computeCheckpointId,
  decodeBase64,
  entryValid,
  exactObject,
  hex64,
  integer,
  isObject,
  merkleLeafHash,
  nonEmptyString,
  positiveInteger,
  signedCheckpointPayload,
  targetValid,
  timestamp,
  verifyCheckpoint,
} from './transparency-log-v0.14.mjs';
import {verifyTransparencyLogStrict} from './transparency-log-strict-v0.14.mjs';

const FIXTURE_FIELDS = new Set([
  'profile_id',
  'schema_version',
  'canonical_profile',
  'base_now_ms',
  'base_bundle',
  'checkpoint_variants',
  'verifier_checkpoint_variants',
  'inclusion_path_variants',
  'consistency_path_variants',
  'expected_base_entry_canonical_base64',
  'expected_base_leaf_hash',
  'expected_base_checkpoint_signed_payload_base64',
  'expected_base_checkpoint_signature_base64',
  'expected_base_checkpoint_digest',
  'expected_base_root_hash',
  'cases',
]);
const CASE_REQUIRED_FIELDS = new Set(['id', 'expected']);
const CASE_OPTIONAL_FIELDS = new Set([
  'checkpoint_ref',
  'verifier_checkpoint_ref',
  'inclusion_path_ref',
  'consistency_path_ref',
  'peer_checkpoint_refs',
  'mutations',
]);
const CASE_FIELDS = new Set([...CASE_REQUIRED_FIELDS, ...CASE_OPTIONAL_FIELDS]);
const EXPECTED_FIELDS = new Set([
  'valid',
  'local_witnessed_freshness_valid',
  'entry_integrity_valid',
  'log_checkpoint_integrity_valid',
  'log_checkpoint_signature_valid',
  'log_checkpoint_authority_valid',
  'log_checkpoint_freshness_valid',
  'inclusion_valid',
  'consistency_valid',
  'view_consistency_valid',
  'log_equivocation_detected',
  'accepted_tree_size',
  'accepted_root_hash',
  'reason_codes',
]);
const MUTATION_FIELDS = new Set(['path', 'value']);
const DANGEROUS_PATH_PARTS = new Set(['__proto__', 'prototype', 'constructor']);
const PATH_PART_RE = /^(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)$/u;

function fixtureError() {
  throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID');
}

function canonicalEqual(left, right) {
  try {
    return canonicalBytes(left).equals(canonicalBytes(right));
  } catch {
    return false;
  }
}

function canonicalBase64(value, length = null) {
  const decoded = decodeBase64(value);
  return decoded !== null && (length === null || decoded.length === length);
}

function hashPath(value) {
  return Array.isArray(value)
    && value.length <= MAX_PROOF_NODES
    && value.every(hex64);
}

function checkpointFixtureShape(checkpoint) {
  if (!exactObject(checkpoint, CHECKPOINT_FIELDS)) return false;
  const specs = new Map([
    ['checkpoint_id', nonEmptyString],
    ['profile_id', nonEmptyString],
    ['schema_version', nonEmptyString],
    ['canonical_profile', nonEmptyString],
    ['log_id', nonEmptyString],
    ['tree_size', positiveInteger],
    ['root_hash', hex64],
    ['issued_at_ms', timestamp],
    ['not_before_ms', timestamp],
    ['not_after_ms', timestamp],
    ['issuer_id', nonEmptyString],
    ['log_authority_id', nonEmptyString],
    ['log_key_id', nonEmptyString],
    ['signature_algorithm', nonEmptyString],
    ['signature', (value) => canonicalBase64(value, SIGNATURE_BYTES)],
  ]);
  if (![...specs].every(([field, predicate]) => predicate(checkpoint[field]))) {
    return false;
  }
  try {
    return checkpoint.checkpoint_id === computeCheckpointId(checkpoint);
  } catch {
    return false;
  }
}

function verifierCheckpointShape(checkpoint) {
  return exactObject(checkpoint, VERIFIER_CHECKPOINT_FIELDS)
    && checkpoint.profile_id === 'vtl-transparency-log-verifier-checkpoint/v0.14'
    && nonEmptyString(checkpoint.log_id)
    && positiveInteger(checkpoint.known_tree_size)
    && hex64(checkpoint.known_root_hash)
    && positiveInteger(checkpoint.minimum_tree_size)
    && timestamp(checkpoint.checkpointed_at_ms);
}

function own(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function clone(value) {
  try {
    return structuredClone(value);
  } catch {
    fixtureError();
  }
}

function setPath(document, path, value) {
  if (!nonEmptyString(path)) fixtureError();
  const parts = path.split('.');
  if (parts.some(
    (part) => DANGEROUS_PATH_PARTS.has(part) || !PATH_PART_RE.test(part),
  )) fixtureError();

  let cursor = document;
  for (const part of parts.slice(0, -1)) {
    if (Array.isArray(cursor)) {
      const index = Number(part);
      if (!/^(?:0|[1-9][0-9]*)$/u.test(part) || index >= cursor.length) {
        fixtureError();
      }
      cursor = cursor[index];
    } else if (isObject(cursor) && own(cursor, part)) {
      cursor = cursor[part];
    } else {
      fixtureError();
    }
  }

  const last = parts.at(-1);
  let previous;
  let index = null;
  if (Array.isArray(cursor)) {
    index = Number(last);
    if (!/^(?:0|[1-9][0-9]*)$/u.test(last) || index >= cursor.length) {
      fixtureError();
    }
    previous = cursor[index];
  } else if (isObject(cursor) && own(cursor, last)) {
    previous = cursor[last];
  } else {
    fixtureError();
  }

  if (canonicalEqual(previous, value)) fixtureError();
  const copied = clone(value);
  if (index === null) cursor[last] = copied;
  else cursor[index] = copied;
}

function caseBundle(fixture, testCase) {
  const bundle = clone(fixture.base_bundle);
  if (own(testCase, 'checkpoint_ref')) {
    bundle.checkpoint = clone(
      fixture.checkpoint_variants[testCase.checkpoint_ref],
    );
  }
  if (own(testCase, 'verifier_checkpoint_ref')) {
    bundle.verifier_checkpoint = clone(
      fixture.verifier_checkpoint_variants[testCase.verifier_checkpoint_ref],
    );
  }
  if (own(testCase, 'inclusion_path_ref')) {
    bundle.inclusion_path = clone(
      fixture.inclusion_path_variants[testCase.inclusion_path_ref],
    );
  }
  if (own(testCase, 'consistency_path_ref')) {
    bundle.consistency_path = clone(
      fixture.consistency_path_variants[testCase.consistency_path_ref],
    );
  }
  if (own(testCase, 'peer_checkpoint_refs')) {
    bundle.peer_checkpoints = testCase.peer_checkpoint_refs.map(
      (ref) => clone(fixture.checkpoint_variants[ref]),
    );
  }
  for (const mutation of testCase.mutations ?? []) {
    setPath(bundle, mutation.path, mutation.value);
  }
  return bundle;
}

function validateExpected(expected) {
  if (!exactObject(expected, EXPECTED_FIELDS)) fixtureError();
  const nonBoolean = new Set([
    'accepted_tree_size', 'accepted_root_hash', 'reason_codes',
  ]);
  for (const field of EXPECTED_FIELDS) {
    if (!nonBoolean.has(field) && typeof expected[field] !== 'boolean') {
      fixtureError();
    }
  }
  if (
    expected.accepted_tree_size !== null
    && !positiveInteger(expected.accepted_tree_size)
  ) fixtureError();
  if (
    expected.accepted_root_hash !== null
    && !hex64(expected.accepted_root_hash)
  ) fixtureError();
  const reasons = expected.reason_codes;
  if (
    !Array.isArray(reasons)
    || !reasons.every(nonEmptyString)
    || new Set(reasons).size !== reasons.length
  ) fixtureError();
}

export function validateTransparencyLogFixture(fixture) {
  if (!exactObject(fixture, FIXTURE_FIELDS)) fixtureError();
  if (fixture.profile_id !== PROFILE_ID) fixtureError();
  if (fixture.schema_version !== FIXTURE_SCHEMA_VERSION) fixtureError();
  if (fixture.canonical_profile !== CANONICAL_PROFILE) fixtureError();
  if (!timestamp(fixture.base_now_ms)) fixtureError();

  const bundle = fixture.base_bundle;
  if (!exactObject(bundle, BUNDLE_FIELDS)) fixtureError();
  if (typeof bundle.local_witnessed_freshness_valid !== 'boolean') fixtureError();
  if (!targetValid(bundle.target) || !entryValid(bundle.entry)) fixtureError();
  for (const field of TARGET_FIELDS) {
    if (bundle.target[field] !== bundle.entry[field]) fixtureError();
  }
  if (
    !integer(bundle.leaf_index)
    || bundle.leaf_index < 0
    || !hashPath(bundle.inclusion_path)
    || !hashPath(bundle.consistency_path)
    || !Array.isArray(bundle.peer_checkpoints)
  ) fixtureError();

  if (checkpointShapeReasons(bundle.checkpoint).length !== 0) fixtureError();
  if (authorityShapeReasons(bundle.log_authority).length !== 0) fixtureError();
  const authority = bundle.log_authority;
  if (!canonicalEqual(authority.allowed_algorithms, [ED25519])) fixtureError();
  authority.keys.forEach((key) => {
    const publicKey = decodeBase64(key.public_key_base64);
    if (
      !exactObject(key, KEY_FIELDS)
      || key.algorithm !== ED25519
      || publicKey === null
      || publicKey.length !== PUBLIC_KEY_BYTES
      || key.not_after_ms < key.not_before_ms
    ) fixtureError();
  });
  if (!verifyCheckpoint(
    bundle.checkpoint,
    authority,
    fixture.base_now_ms,
  ).slice(0, 4).every(Boolean)) fixtureError();
  if (!verifierCheckpointShape(bundle.verifier_checkpoint)) fixtureError();
  if (!bundle.peer_checkpoints.every(checkpointFixtureShape)) fixtureError();

  const groups = new Map([
    ['checkpoint_variants', checkpointFixtureShape],
    ['verifier_checkpoint_variants', verifierCheckpointShape],
    ['inclusion_path_variants', hashPath],
    ['consistency_path_variants', hashPath],
  ]);
  for (const [groupName, predicate] of groups) {
    const group = fixture[groupName];
    if (!isObject(group) || Object.keys(group).length === 0) fixtureError();
    for (const [name, value] of Object.entries(group)) {
      if (!nonEmptyString(name) || !predicate(value)) fixtureError();
    }
  }

  for (const [groupName, bundleField] of [
    ['checkpoint_variants', 'checkpoint'],
    ['verifier_checkpoint_variants', 'verifier_checkpoint'],
    ['inclusion_path_variants', 'inclusion_path'],
    ['consistency_path_variants', 'consistency_path'],
  ]) {
    if (!own(fixture[groupName], 'base')) fixtureError();
    if (!canonicalEqual(fixture[groupName].base, bundle[bundleField])) fixtureError();
  }

  const anchors = new Map([
    ['expected_base_entry_canonical_base64', (value) => canonicalBase64(value)],
    ['expected_base_leaf_hash', hex64],
    [
      'expected_base_checkpoint_signed_payload_base64',
      (value) => canonicalBase64(value),
    ],
    [
      'expected_base_checkpoint_signature_base64',
      (value) => canonicalBase64(value, SIGNATURE_BYTES),
    ],
    ['expected_base_checkpoint_digest', hex64],
    ['expected_base_root_hash', hex64],
  ]);
  for (const [field, predicate] of anchors) {
    if (!predicate(fixture[field])) fixtureError();
  }

  if (!Array.isArray(fixture.cases) || fixture.cases.length === 0) fixtureError();
  const caseIds = new Set();
  const verificationInputs = new Set();
  const referenced = {
    checkpoint_variants: new Set(['base']),
    verifier_checkpoint_variants: new Set(['base']),
    inclusion_path_variants: new Set(['base']),
    consistency_path_variants: new Set(['base']),
  };
  const refFields = new Map([
    ['checkpoint_ref', 'checkpoint_variants'],
    ['verifier_checkpoint_ref', 'verifier_checkpoint_variants'],
    ['inclusion_path_ref', 'inclusion_path_variants'],
    ['consistency_path_ref', 'consistency_path_variants'],
  ]);

  fixture.cases.forEach((testCase) => {
    if (
      !isObject(testCase)
      || ![...CASE_REQUIRED_FIELDS].every((field) => own(testCase, field))
      || Object.keys(testCase).some((field) => !CASE_FIELDS.has(field))
    ) fixtureError();
    if (!nonEmptyString(testCase.id) || caseIds.has(testCase.id)) fixtureError();
    caseIds.add(testCase.id);
    validateExpected(testCase.expected);

    for (const [refField, groupName] of refFields) {
      if (!own(testCase, refField)) continue;
      const ref = testCase[refField];
      if (!nonEmptyString(ref) || !own(fixture[groupName], ref)) fixtureError();
      referenced[groupName].add(ref);
    }

    if (own(testCase, 'peer_checkpoint_refs')) {
      const refs = testCase.peer_checkpoint_refs;
      if (
        !Array.isArray(refs)
        || refs.length === 0
        || !refs.every(
          (ref) => nonEmptyString(ref) && own(fixture.checkpoint_variants, ref),
        )
        || new Set(refs).size !== refs.length
      ) fixtureError();
      refs.forEach((ref) => referenced.checkpoint_variants.add(ref));
    }

    const mutations = testCase.mutations ?? [];
    if (!Array.isArray(mutations)) fixtureError();
    const mutationPaths = new Set();
    const caseWithoutMutations = Object.fromEntries(
      Object.entries(testCase).filter(([key]) => key !== 'mutations'),
    );
    const candidate = caseBundle(fixture, caseWithoutMutations);
    mutations.forEach((mutation) => {
      if (!exactObject(mutation, MUTATION_FIELDS)) fixtureError();
      if (mutationPaths.has(mutation.path)) fixtureError();
      mutationPaths.add(mutation.path);
      setPath(candidate, mutation.path, mutation.value);
    });
    const verificationInput = canonicalBytes({
      bundle: candidate,
      now_ms: fixture.base_now_ms,
    }).toString('base64');
    if (verificationInputs.has(verificationInput)) fixtureError();
    verificationInputs.add(verificationInput);
  });

  for (const [groupName, names] of Object.entries(referenced)) {
    const actualNames = Object.keys(fixture[groupName]);
    if (
      names.size !== actualNames.length
      || actualNames.some((name) => !names.has(name))
    ) fixtureError();
  }
}

export function loadTransparencyLogFixture(path) {
  const fixture = strictParse(fs.readFileSync(path, 'utf8'));
  if (!isObject(fixture)) fixtureError();
  return fixture;
}

export function runTransparencyLogFixture(inputFixture) {
  const fixture = clone(inputFixture);
  validateTransparencyLogFixture(fixture);

  const cases = fixture.cases.map((testCase) => {
    const actual = verifyTransparencyLogStrict(
      caseBundle(fixture, testCase),
      fixture.base_now_ms,
    );
    const expected = clone(testCase.expected);
    return {
      id: testCase.id,
      actual,
      expected,
      passed: canonicalEqual(actual, expected),
    };
  });

  const base = fixture.base_bundle;
  const entryBytes = canonicalBytes(base.entry);
  const checkpointPayload = signedCheckpointPayload(base.checkpoint);
  const entryBase64 = entryBytes.toString('base64');
  const checkpointPayloadBase64 = checkpointPayload.toString('base64');
  const leafHash = merkleLeafHash(base.entry);
  const digest = checkpointDigest(base.checkpoint);
  const parity = {
    entry_canonical_base64: entryBase64,
    entry_canonical_matches_expected: (
      entryBase64 === fixture.expected_base_entry_canonical_base64
    ),
    leaf_hash: leafHash,
    leaf_hash_matches_expected: leafHash === fixture.expected_base_leaf_hash,
    checkpoint_signed_payload_base64: checkpointPayloadBase64,
    checkpoint_signed_payload_matches_expected: (
      checkpointPayloadBase64
      === fixture.expected_base_checkpoint_signed_payload_base64
    ),
    checkpoint_signature_matches_expected: (
      base.checkpoint.signature
      === fixture.expected_base_checkpoint_signature_base64
    ),
    checkpoint_digest: digest,
    checkpoint_digest_matches_expected: (
      digest === fixture.expected_base_checkpoint_digest
    ),
    root_hash_matches_expected: (
      base.checkpoint.root_hash === fixture.expected_base_root_hash
    ),
  };

  const passed = cases.filter((testCase) => testCase.passed).length;
  const parityPassed = Object.entries(parity).every(
    ([key, value]) => !key.endsWith('_matches_expected') || value === true,
  );
  const allPassed = passed === cases.length
    && parityPassed
    && cases.some((testCase) => testCase.actual.valid === true);
  return {
    profile_id: PROFILE_ID,
    schema_version: FIXTURE_SCHEMA_VERSION,
    canonical_profile: CANONICAL_PROFILE,
    cases,
    parity,
    summary: {
      total: cases.length,
      passed,
      failed: cases.length - passed,
      all_passed: allPassed,
    },
  };
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const fixturePath = process.argv[2];
  if (!fixturePath) {
    process.stderr.write(
      'usage: node reference/transparency-log-conformance-v0.14.mjs <fixture.json>\n',
    );
    process.exit(2);
  }
  const result = runTransparencyLogFixture(
    loadTransparencyLogFixture(fixturePath),
  );
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.summary.all_passed) process.exitCode = 1;
}
