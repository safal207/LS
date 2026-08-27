#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';
import {
  CANONICAL_PROFILE,
  canonicalBytes,
  canonicalSha256,
  strictParse,
} from './canonical-runtime-v0.12.mjs';

const PROFILE_ID = 'vtl-witnessed-freshness-v0.13';
const FIXTURE_PROFILE_ID = 'vtl-witnessed-freshness-fixture/v0.13';
const FIXTURE_SCHEMA_VERSION = 'vtl.witnessed-freshness-fixture/v0.13';
const STATEMENT_PROFILE_ID = 'vtl-witness-statement/v0.13';
const STATEMENT_SCHEMA_VERSION = 'vtl.witness-statement/v0.13';
const AUTHORITY_PROFILE_ID = 'vtl-witness-authority/v0.13';
const ED25519 = 'ED25519';
const PUBLIC_KEY_BYTES = 32;
const SIGNATURE_BYTES = 64;

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
function nonEmptyString(value) {
  if (typeof value !== 'string' || value.length === 0) return false;
  try { canonicalBytes(value); } catch { return false; }
  return true;
}
function integer(value) { return Number.isSafeInteger(value); }
function timestamp(value) { return integer(value) && value >= 0; }
function positiveInteger(value) { return integer(value) && value >= 1; }
function hex64(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
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
function canonicalBase64(value, length) {
  const decoded = decodeBase64(value);
  return decoded !== null && decoded.length === length;
}

const STATEMENT_FIELDS = [
  'profile_id', 'schema_version', 'canonical_profile', 'trust_root_id',
  'generation', 'snapshot_digest', 'observed_at_ms', 'witness_id',
  'witness_key_id', 'signature_algorithm',
];
const STATEMENT_OBJECT_FIELDS = new Set([...STATEMENT_FIELDS, 'statement_id', 'signature']);
const VIEW_FIELDS = new Set(['trust_root_id', 'generation', 'snapshot_digest']);
const AUTHORITY_FIELDS = new Set([
  'profile_id', 'quorum', 'max_statement_age_ms', 'allowed_algorithms', 'keys',
]);
const KEY_FIELDS = new Set([
  'witness_id', 'witness_key_id', 'algorithm', 'public_key_base64',
  'not_before_ms', 'not_after_ms', 'revoked',
]);
const FIXTURE_FIELDS = new Set([
  'profile_id', 'schema_version', 'canonical_profile', 'base_now_ms',
  'snapshot_view', 'local_snapshot_valid', 'witness_authority', 'statements', 'cases',
]);
const CASE_REQUIRED_FIELDS = new Set(['id', 'statement_refs', 'expected']);
const CASE_ALLOWED_FIELDS = new Set([
  ...CASE_REQUIRED_FIELDS, 'local_snapshot_valid', 'authority_mutations', 'statement_mutations',
]);
const EXPECTED_FIELDS = new Set([
  'valid', 'local_snapshot_valid', 'witness_statement_integrity_valid',
  'witness_signature_valid', 'witness_authority_valid', 'witness_freshness_valid',
  'witness_quorum_valid', 'view_consistency_valid', 'equivocation_detected',
  'accepted_witness_ids', 'reason_codes',
]);
const MUTATION_FIELDS = new Set(['path', 'value']);
const STATEMENT_MUTATION_FIELDS = new Set(['index', 'path', 'value']);
const DANGEROUS_PATH_PARTS = new Set(['__proto__', 'prototype', 'constructor']);
const PATH_PART_RE = /^(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)$/;

function witnessStatement(statement) {
  const result = {};
  for (const field of STATEMENT_FIELDS) result[field] = statement?.[field];
  return result;
}
function computeWitnessStatementId(statement) {
  return `witness_${canonicalSha256(witnessStatement(statement)).slice(0, 24)}`;
}
function signedWitnessPayload(statement) {
  return canonicalBytes({statement_id: statement?.statement_id, ...witnessStatement(statement)});
}

function validateStatement(statement) {
  if (!isObject(statement)) return ['WITNESS_STATEMENT_INVALID'];
  const reasons = [];
  add(reasons, 'WITNESS_STATEMENT_FIELDS_INVALID', !exactObject(statement, STATEMENT_OBJECT_FIELDS));
  const required = {
    statement_id: nonEmptyString,
    profile_id: nonEmptyString,
    schema_version: nonEmptyString,
    canonical_profile: nonEmptyString,
    trust_root_id: nonEmptyString,
    generation: positiveInteger,
    snapshot_digest: hex64,
    observed_at_ms: timestamp,
    witness_id: nonEmptyString,
    witness_key_id: nonEmptyString,
    signature_algorithm: nonEmptyString,
    signature: (value) => canonicalBase64(value, SIGNATURE_BYTES),
  };
  for (const [field, predicate] of Object.entries(required)) {
    if (!(field in statement) || !predicate(statement[field])) {
      add(reasons, `WITNESS_STATEMENT_SCHEMA_INVALID:${field}`, true);
    }
  }
  return reasons;
}

function validateAuthority(authority) {
  if (!isObject(authority)) return ['WITNESS_AUTHORITY_INVALID'];
  const reasons = [];
  add(reasons, 'WITNESS_AUTHORITY_FIELDS_INVALID', !exactObject(authority, AUTHORITY_FIELDS));
  add(reasons, 'WITNESS_AUTHORITY_PROFILE_INVALID', authority.profile_id !== AUTHORITY_PROFILE_ID);
  add(reasons, 'WITNESS_QUORUM_CONFIG_INVALID', !positiveInteger(authority.quorum));
  add(reasons, 'WITNESS_MAX_AGE_INVALID', !positiveInteger(authority.max_statement_age_ms));
  add(
    reasons,
    'WITNESS_ALLOWED_ALGORITHMS_INVALID',
    !Array.isArray(authority.allowed_algorithms)
      || authority.allowed_algorithms.length === 0
      || !authority.allowed_algorithms.every(nonEmptyString)
      || new Set(authority.allowed_algorithms).size !== authority.allowed_algorithms.length,
  );
  if (!Array.isArray(authority.keys) || authority.keys.length === 0) {
    add(reasons, 'WITNESS_KEYS_INVALID', true);
    return reasons;
  }
  authority.keys.forEach((key, index) => {
    if (!isObject(key)) {
      add(reasons, `WITNESS_KEY_INVALID:${index}`, true);
      return;
    }
    add(reasons, `WITNESS_KEY_FIELDS_INVALID:${index}`, !exactObject(key, KEY_FIELDS));
    const specs = {
      witness_id: nonEmptyString,
      witness_key_id: nonEmptyString,
      algorithm: nonEmptyString,
      public_key_base64: nonEmptyString,
      not_before_ms: timestamp,
      not_after_ms: timestamp,
      revoked: (value) => typeof value === 'boolean',
    };
    for (const [field, predicate] of Object.entries(specs)) {
      if (!(field in key) || !predicate(key[field])) {
        add(reasons, `WITNESS_KEY_SCHEMA_INVALID:${index}.${field}`, true);
      }
    }
  });
  return reasons;
}

function invalidResult(localSnapshotValid, reasons) {
  return {
    valid: false,
    local_snapshot_valid: localSnapshotValid === true,
    witness_statement_integrity_valid: false,
    witness_signature_valid: false,
    witness_authority_valid: false,
    witness_freshness_valid: false,
    witness_quorum_valid: false,
    view_consistency_valid: false,
    equivocation_detected: false,
    accepted_witness_ids: [],
    reason_codes: reasons,
  };
}

function verifyWitnessedFreshness({
  snapshotView,
  localSnapshotValid,
  witnessStatements,
  witnessAuthority,
  nowMs,
}) {
  try {
    snapshotView = structuredClone(snapshotView);
    witnessStatements = structuredClone(witnessStatements);
    witnessAuthority = structuredClone(witnessAuthority);
  } catch {
    return invalidResult(localSnapshotValid, ['INPUT_SNAPSHOT_FAILED']);
  }

  const reasons = [];
  add(reasons, 'LOCAL_SNAPSHOT_INVALID', localSnapshotValid !== true);
  add(reasons, 'NOW_MS_INVALID', !timestamp(nowMs));
  const viewValid = exactObject(snapshotView, VIEW_FIELDS)
    && nonEmptyString(snapshotView.trust_root_id)
    && positiveInteger(snapshotView.generation)
    && hex64(snapshotView.snapshot_digest);
  add(reasons, 'SNAPSHOT_VIEW_INVALID', !viewValid);
  const authorityReasons = validateAuthority(witnessAuthority);
  for (const reason of authorityReasons) add(reasons, reason, true);
  const statementsValid = Array.isArray(witnessStatements) && witnessStatements.length > 0;
  add(reasons, 'WITNESS_STATEMENTS_INVALID', !statementsValid);
  if (!viewValid || authorityReasons.length > 0 || !timestamp(nowMs) || !statementsValid) {
    return invalidResult(localSnapshotValid, reasons);
  }

  let statementIntegrityValid = true;
  let allSignatureValid = true;
  let allAuthorityValid = true;
  let allFresh = true;
  let allViewConsistent = true;
  let equivocationDetected = false;
  const accepted = new Set();
  const seenWitnessIds = new Set();
  const keys = witnessAuthority.keys;
  const allowed = witnessAuthority.allowed_algorithms;
  const maxAge = witnessAuthority.max_statement_age_ms;

  for (const statement of witnessStatements) {
    const shapeReasons = validateStatement(statement);
    for (const reason of shapeReasons) add(reasons, reason, true);
    if (shapeReasons.length > 0) {
      statementIntegrityValid = false;
      allSignatureValid = false;
      allAuthorityValid = false;
      allFresh = false;
      allViewConsistent = false;
      continue;
    }

    const profileOk = statement.profile_id === STATEMENT_PROFILE_ID
      && statement.schema_version === STATEMENT_SCHEMA_VERSION;
    const canonicalOk = statement.canonical_profile === CANONICAL_PROFILE;
    let idOk = false;
    try { idOk = statement.statement_id === computeWitnessStatementId(statement); } catch { idOk = false; }
    add(reasons, 'WITNESS_PROFILE_MISMATCH', !profileOk);
    add(reasons, 'WITNESS_CANONICAL_PROFILE_MISMATCH', !canonicalOk);
    add(reasons, 'WITNESS_STATEMENT_ID_INVALID', !idOk);
    const integrityOk = profileOk && canonicalOk && idOk;
    statementIntegrityValid = statementIntegrityValid && integrityOk;

    const witnessId = statement.witness_id;
    if (seenWitnessIds.has(witnessId)) {
      add(reasons, 'DUPLICATE_WITNESS_ID', true);
      allViewConsistent = false;
    }
    seenWitnessIds.add(witnessId);

    const matching = keys.filter(
      (key) => isObject(key)
        && key.witness_id === witnessId
        && key.witness_key_id === statement.witness_key_id,
    );
    add(reasons, 'WITNESS_NOT_TRUSTED', matching.length === 0);
    add(reasons, 'WITNESS_KEY_AMBIGUOUS', matching.length > 1);
    const key = matching.length === 1 ? matching[0] : null;
    let signatureOk = false;
    let authorityOk = key !== null;
    if (key) {
      const algorithmOk = statement.signature_algorithm === ED25519
        && key.algorithm === ED25519
        && allowed.includes(ED25519);
      add(reasons, 'WITNESS_ALGORITHM_NOT_ALLOWED', !algorithmOk);
      const keyIntervalOk = timestamp(key.not_before_ms)
        && timestamp(key.not_after_ms)
        && key.not_after_ms >= key.not_before_ms;
      add(reasons, 'WITNESS_KEY_VALIDITY_INVALID', !keyIntervalOk);
      add(reasons, 'WITNESS_KEY_REVOKED', key.revoked === true);
      const keyCurrent = keyIntervalOk
        && key.not_before_ms <= nowMs
        && nowMs <= key.not_after_ms;
      add(reasons, 'WITNESS_KEY_NOT_CURRENT', keyIntervalOk && !keyCurrent);
      const publicKey = decodeBase64(key.public_key_base64);
      const signature = decodeBase64(statement.signature);
      const keyMaterialOk = publicKey !== null && publicKey.length === PUBLIC_KEY_BYTES;
      const signatureMaterialOk = signature !== null && signature.length === SIGNATURE_BYTES;
      add(reasons, 'WITNESS_KEY_MATERIAL_INVALID', !keyMaterialOk);
      if (algorithmOk && keyMaterialOk && signatureMaterialOk) {
        try {
          const spki = Buffer.concat([
            Buffer.from('302a300506032b6570032100', 'hex'),
            publicKey,
          ]);
          const keyObject = crypto.createPublicKey({key: spki, format: 'der', type: 'spki'});
          signatureOk = crypto.verify(null, signedWitnessPayload(statement), keyObject, signature);
        } catch {
          signatureOk = false;
        }
      }
      add(reasons, 'WITNESS_SIGNATURE_INVALID', !signatureOk && algorithmOk && keyMaterialOk);
      authorityOk = authorityOk
        && algorithmOk
        && keyIntervalOk
        && keyCurrent
        && key.revoked === false
        && keyMaterialOk;
    }
    allSignatureValid = allSignatureValid && signatureOk;
    allAuthorityValid = allAuthorityValid && authorityOk;

    const fromFuture = statement.observed_at_ms > nowMs;
    const stale = !fromFuture && nowMs - statement.observed_at_ms > maxAge;
    add(reasons, 'WITNESS_STATEMENT_FROM_FUTURE', fromFuture);
    add(reasons, 'WITNESS_STATEMENT_STALE', stale);
    const freshOk = !fromFuture && !stale;
    allFresh = allFresh && freshOk;

    const rootMatch = statement.trust_root_id === snapshotView.trust_root_id;
    const generationMatch = statement.generation === snapshotView.generation;
    const digestMatch = statement.snapshot_digest === snapshotView.snapshot_digest;
    add(reasons, 'WITNESS_TRUST_ROOT_MISMATCH', !rootMatch);
    add(reasons, 'WITNESS_GENERATION_MISMATCH', !generationMatch);
    add(
      reasons,
      'WITNESS_SNAPSHOT_DIGEST_MISMATCH',
      rootMatch && generationMatch && !digestMatch,
    );
    const exactView = rootMatch && generationMatch && digestMatch;
    if (
      integrityOk
      && signatureOk
      && authorityOk
      && freshOk
      && rootMatch
      && generationMatch
      && !digestMatch
    ) {
      equivocationDetected = true;
      add(reasons, 'EQUIVOCATION_DETECTED', true);
    }
    allViewConsistent = allViewConsistent && exactView;
    if (integrityOk && signatureOk && authorityOk && freshOk && exactView) accepted.add(witnessId);
  }

  const quorumValid = accepted.size >= witnessAuthority.quorum;
  add(reasons, 'WITNESS_QUORUM_NOT_MET', !quorumValid);
  const viewConsistencyValid = allViewConsistent && !equivocationDetected;
  const valid = localSnapshotValid === true
    && statementIntegrityValid
    && allSignatureValid
    && allAuthorityValid
    && allFresh
    && quorumValid
    && viewConsistencyValid
    && !equivocationDetected
    && reasons.length === 0;
  return {
    valid,
    local_snapshot_valid: localSnapshotValid === true,
    witness_statement_integrity_valid: statementIntegrityValid,
    witness_signature_valid: allSignatureValid,
    witness_authority_valid: allAuthorityValid,
    witness_freshness_valid: allFresh,
    witness_quorum_valid: quorumValid,
    view_consistency_valid: viewConsistencyValid,
    equivocation_detected: equivocationDetected,
    accepted_witness_ids: [...accepted].sort(),
    reason_codes: reasons,
  };
}

function fixtureFailure() { throw new Error('FIXTURE_SCHEMA_INVALID'); }

function setPath(document, path, value) {
  if (!nonEmptyString(path)) fixtureFailure();
  const parts = path.split('.');
  if (parts.some((part) => DANGEROUS_PATH_PARTS.has(part) || !PATH_PART_RE.test(part))) {
    fixtureFailure();
  }
  let cursor = document;
  for (const part of parts.slice(0, -1)) {
    if (Array.isArray(cursor)) {
      const index = Number(part);
      if (!/^\d+$/.test(part) || index >= cursor.length) fixtureFailure();
      cursor = cursor[index];
    } else if (isObject(cursor) && Object.hasOwn(cursor, part)) {
      cursor = cursor[part];
    } else {
      fixtureFailure();
    }
  }
  const last = parts.at(-1);
  let previous;
  if (Array.isArray(cursor)) {
    const index = Number(last);
    if (!/^\d+$/.test(last) || index >= cursor.length) fixtureFailure();
    previous = cursor[index];
  } else if (isObject(cursor) && Object.hasOwn(cursor, last)) {
    previous = cursor[last];
  } else {
    fixtureFailure();
  }
  try {
    if (canonicalBytes(previous).equals(canonicalBytes(value))) fixtureFailure();
  } catch {
    fixtureFailure();
  }
  if (Array.isArray(cursor)) cursor[Number(last)] = structuredClone(value);
  else cursor[last] = structuredClone(value);
}

function validateFixtureShape(fixture) {
  if (!exactObject(fixture, FIXTURE_FIELDS)) fixtureFailure();
  if (fixture.profile_id !== FIXTURE_PROFILE_ID) fixtureFailure();
  if (fixture.schema_version !== FIXTURE_SCHEMA_VERSION) fixtureFailure();
  if (fixture.canonical_profile !== CANONICAL_PROFILE) fixtureFailure();
  if (!timestamp(fixture.base_now_ms)) fixtureFailure();
  if (typeof fixture.local_snapshot_valid !== 'boolean') fixtureFailure();
  if (
    !exactObject(fixture.snapshot_view, VIEW_FIELDS)
    || !nonEmptyString(fixture.snapshot_view.trust_root_id)
    || !positiveInteger(fixture.snapshot_view.generation)
    || !hex64(fixture.snapshot_view.snapshot_digest)
  ) fixtureFailure();
  if (validateAuthority(fixture.witness_authority).length > 0) fixtureFailure();
  if (
    fixture.witness_authority.allowed_algorithms.length !== 1
    || fixture.witness_authority.allowed_algorithms[0] !== ED25519
  ) fixtureFailure();
  for (const key of fixture.witness_authority.keys) {
    const publicKey = decodeBase64(key.public_key_base64);
    if (
      key.algorithm !== ED25519
      || publicKey === null
      || publicKey.length !== PUBLIC_KEY_BYTES
      || key.not_after_ms < key.not_before_ms
    ) fixtureFailure();
  }

  if (!isObject(fixture.statements) || Object.keys(fixture.statements).length === 0) fixtureFailure();
  for (const [name, statement] of Object.entries(fixture.statements)) {
    if (!nonEmptyString(name) || validateStatement(statement).length > 0) fixtureFailure();
    let identityValid = false;
    try { identityValid = statement.statement_id === computeWitnessStatementId(statement); } catch { identityValid = false; }
    if (
      statement.profile_id !== STATEMENT_PROFILE_ID
      || statement.schema_version !== STATEMENT_SCHEMA_VERSION
      || statement.canonical_profile !== CANONICAL_PROFILE
      || statement.signature_algorithm !== ED25519
      || !identityValid
    ) fixtureFailure();
  }
  if (!Array.isArray(fixture.cases) || fixture.cases.length === 0) fixtureFailure();

  const caseIds = new Set();
  const referencedStatements = new Set();
  const verificationInputs = new Set();
  for (const testCase of fixture.cases) {
    if (!isObject(testCase)) fixtureFailure();
    const fields = Object.keys(testCase);
    if (
      ![...CASE_REQUIRED_FIELDS].every((field) => Object.hasOwn(testCase, field))
      || !fields.every((field) => CASE_ALLOWED_FIELDS.has(field))
    ) fixtureFailure();
    if (!nonEmptyString(testCase.id) || caseIds.has(testCase.id)) fixtureFailure();
    caseIds.add(testCase.id);

    if (
      !Array.isArray(testCase.statement_refs)
      || testCase.statement_refs.length === 0
      || !testCase.statement_refs.every(
        (ref) => nonEmptyString(ref) && Object.hasOwn(fixture.statements, ref),
      )
    ) fixtureFailure();
    for (const ref of testCase.statement_refs) referencedStatements.add(ref);
    if (
      Object.hasOwn(testCase, 'local_snapshot_valid')
      && typeof testCase.local_snapshot_valid !== 'boolean'
    ) fixtureFailure();

    if (!exactObject(testCase.expected, EXPECTED_FIELDS)) fixtureFailure();
    for (const field of EXPECTED_FIELDS) {
      if (
        field !== 'accepted_witness_ids'
        && field !== 'reason_codes'
        && typeof testCase.expected[field] !== 'boolean'
      ) fixtureFailure();
    }
    const accepted = testCase.expected.accepted_witness_ids;
    if (
      !Array.isArray(accepted)
      || !accepted.every(nonEmptyString)
      || new Set(accepted).size !== accepted.length
      || accepted.some((value, index) => index > 0 && accepted[index - 1] > value)
    ) fixtureFailure();
    const reasonCodes = testCase.expected.reason_codes;
    if (
      !Array.isArray(reasonCodes)
      || !reasonCodes.every(nonEmptyString)
      || new Set(reasonCodes).size !== reasonCodes.length
    ) fixtureFailure();

    const authority = structuredClone(fixture.witness_authority);
    const authorityMutations = testCase.authority_mutations ?? [];
    if (!Array.isArray(authorityMutations)) fixtureFailure();
    const authorityPaths = new Set();
    for (const mutation of authorityMutations) {
      if (!exactObject(mutation, MUTATION_FIELDS)) fixtureFailure();
      if (authorityPaths.has(mutation.path)) fixtureFailure();
      authorityPaths.add(mutation.path);
      setPath(authority, mutation.path, mutation.value);
    }

    const statements = testCase.statement_refs.map(
      (ref) => structuredClone(fixture.statements[ref]),
    );
    const statementMutations = testCase.statement_mutations ?? [];
    if (!Array.isArray(statementMutations)) fixtureFailure();
    const statementTargets = new Set();
    for (const mutation of statementMutations) {
      if (!exactObject(mutation, STATEMENT_MUTATION_FIELDS)) fixtureFailure();
      if (!integer(mutation.index) || mutation.index < 0 || mutation.index >= statements.length) {
        fixtureFailure();
      }
      const target = `${mutation.index}\u0000${mutation.path}`;
      if (statementTargets.has(target)) fixtureFailure();
      statementTargets.add(target);
      setPath(statements[mutation.index], mutation.path, mutation.value);
    }
    const verificationInput = canonicalBytes({
      snapshot_view: fixture.snapshot_view,
      local_snapshot_valid: testCase.local_snapshot_valid ?? fixture.local_snapshot_valid,
      witness_statements: statements,
      witness_authority: authority,
      now_ms: fixture.base_now_ms,
    }).toString('base64');
    if (verificationInputs.has(verificationInput)) fixtureFailure();
    verificationInputs.add(verificationInput);
  }
  const statementNames = Object.keys(fixture.statements);
  if (
    referencedStatements.size !== statementNames.length
    || !statementNames.every((name) => referencedStatements.has(name))
  ) fixtureFailure();
}

function runFixture(inputFixture) {
  if (!isObject(inputFixture)) fixtureFailure();
  let fixture;
  try { fixture = structuredClone(inputFixture); } catch { fixtureFailure(); }
  validateFixtureShape(fixture);
  const cases = fixture.cases.map((testCase) => {
    const authority = structuredClone(fixture.witness_authority);
    const statements = testCase.statement_refs.map(
      (ref) => structuredClone(fixture.statements[ref]),
    );
    for (const mutation of testCase.authority_mutations ?? []) {
      setPath(authority, mutation.path, mutation.value);
    }
    for (const mutation of testCase.statement_mutations ?? []) {
      setPath(statements[mutation.index], mutation.path, mutation.value);
    }
    const actual = verifyWitnessedFreshness({
      snapshotView: fixture.snapshot_view,
      localSnapshotValid: testCase.local_snapshot_valid ?? fixture.local_snapshot_valid,
      witnessStatements: statements,
      witnessAuthority: authority,
      nowMs: fixture.base_now_ms,
    });
    return {
      id: testCase.id,
      actual,
      expected: testCase.expected,
      passed: canonicalBytes(actual).equals(canonicalBytes(testCase.expected)),
    };
  });
  const passed = cases.filter((item) => item.passed).length;
  return {
    profile_id: PROFILE_ID,
    schema_version: FIXTURE_SCHEMA_VERSION,
    canonical_profile: CANONICAL_PROFILE,
    cases,
    summary: {
      total: cases.length,
      passed,
      failed: cases.length - passed,
      all_passed: passed === cases.length && cases.some((item) => item.actual.valid),
    },
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  process.stderr.write('usage: node reference/witnessed-freshness-v0.13.mjs <fixture.json>\n');
  process.exit(2);
}
const fixture = strictParse(fs.readFileSync(fixturePath, 'utf8'));
const result = runFixture(fixture);
// Public conformance evidence only; no private witness key material is loaded.
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
if (!result.summary.all_passed) process.exitCode = 1;
