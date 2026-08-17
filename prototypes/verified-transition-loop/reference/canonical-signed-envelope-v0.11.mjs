#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';

const PROFILE_ID = 'vtl-canonical-signed-envelope-v0.11';
const SCHEMA_VERSION = 'vtl.canonical-signed-envelope/v0.11';
const FIXTURE_SCHEMA_VERSION = 'vtl.canonical-signed-envelope-fixture/v0.11';
const TRUST_ROOT_PROFILE_ID = 'vtl-canonical-trust-root/v0.11';
const CANONICAL_PROFILE = 'rfc8785-safe-integer/v0.10';
const ED25519 = 'ED25519';
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

class CanonicalizationError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

function validateUnicodeScalarString(value) {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      if (i + 1 >= value.length) throw new CanonicalizationError('INVALID_UNICODE_SCALAR');
      const next = value.charCodeAt(i + 1);
      if (next < 0xdc00 || next > 0xdfff) throw new CanonicalizationError('INVALID_UNICODE_SCALAR');
      i += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      throw new CanonicalizationError('INVALID_UNICODE_SCALAR');
    }
  }
}

function escapeString(value) {
  validateUnicodeScalarString(value);
  let output = '"';
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    const ch = value[i];
    if (code >= 0xd800 && code <= 0xdbff) {
      output += value[i] + value[i + 1];
      i += 1;
      continue;
    }
    if (ch === '"') output += '\\"';
    else if (ch === '\\') output += '\\\\';
    else if (code === 0x08) output += '\\b';
    else if (code === 0x09) output += '\\t';
    else if (code === 0x0a) output += '\\n';
    else if (code === 0x0c) output += '\\f';
    else if (code === 0x0d) output += '\\r';
    else if (code <= 0x1f) output += `\\u${code.toString(16).padStart(4, '0')}`;
    else output += ch;
  }
  return output + '"';
}

function canonicalText(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isInteger(value)) throw new CanonicalizationError('UNSUPPORTED_NUMBER');
    if (!Number.isSafeInteger(value)) throw new CanonicalizationError('INTEGER_OUT_OF_RANGE');
    return Object.is(value, -0) ? '0' : String(value);
  }
  if (typeof value === 'string') return escapeString(value);
  if (Array.isArray(value)) return `[${value.map(canonicalText).join(',')}]`;
  if (typeof value === 'object') {
    const keys = Object.keys(value);
    for (const key of keys) validateUnicodeScalarString(key);
    keys.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${keys.map((key) => `${escapeString(key)}:${canonicalText(value[key])}`).join(',')}}`;
  }
  throw new CanonicalizationError('UNSUPPORTED_TYPE');
}

function canonicalBytes(value) {
  return Buffer.from(canonicalText(value), 'utf8');
}

function canonicalSha256(value) {
  return crypto.createHash('sha256').update(canonicalBytes(value)).digest('hex');
}

function strictParse(raw) {
  let index = 0;
  const fail = (code) => { throw new CanonicalizationError(code); };
  const skipWhitespace = () => {
    while (index < raw.length && /[\t\n\r ]/.test(raw[index])) index += 1;
  };

  function parseString() {
    if (raw[index] !== '"') fail('INVALID_JSON');
    const start = index;
    index += 1;
    while (index < raw.length) {
      const ch = raw[index];
      const code = raw.charCodeAt(index);
      if (code <= 0x1f) fail('INVALID_JSON');
      if (ch === '\\') {
        index += 1;
        if (index >= raw.length) fail('INVALID_JSON');
        if (raw[index] === 'u') {
          const hex = raw.slice(index + 1, index + 5);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) fail('INVALID_JSON');
          index += 5;
        } else {
          if (!'"\\/bfnrt'.includes(raw[index])) fail('INVALID_JSON');
          index += 1;
        }
        continue;
      }
      if (ch === '"') {
        index += 1;
        let value;
        try { value = JSON.parse(raw.slice(start, index)); } catch { fail('INVALID_JSON'); }
        validateUnicodeScalarString(value);
        return value;
      }
      index += 1;
    }
    fail('INVALID_JSON');
  }

  function parseNumber() {
    const match = raw.slice(index).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!match) fail('INVALID_JSON');
    const token = match[0];
    index += token.length;
    if (/[.eE]/.test(token)) fail('UNSUPPORTED_NUMBER');
    const value = BigInt(token);
    const max = BigInt(MAX_SAFE_INTEGER);
    if (value > max || value < -max) fail('INTEGER_OUT_OF_RANGE');
    return Number(value);
  }

  function parseLiteral(token, value) {
    if (raw.slice(index, index + token.length) !== token) fail('INVALID_JSON');
    index += token.length;
    return value;
  }

  function parseArray() {
    const result = [];
    index += 1;
    skipWhitespace();
    if (raw[index] === ']') { index += 1; return result; }
    while (true) {
      result.push(parseValue());
      skipWhitespace();
      if (raw[index] === ']') { index += 1; return result; }
      if (raw[index] !== ',') fail('INVALID_JSON');
      index += 1;
      skipWhitespace();
    }
  }

  function parseObject() {
    const result = Object.create(null);
    const seen = new Set();
    index += 1;
    skipWhitespace();
    if (raw[index] === '}') { index += 1; return result; }
    while (true) {
      if (raw[index] !== '"') fail('INVALID_JSON');
      const key = parseString();
      if (seen.has(key)) fail('DUPLICATE_KEY');
      seen.add(key);
      skipWhitespace();
      if (raw[index] !== ':') fail('INVALID_JSON');
      index += 1;
      result[key] = parseValue();
      skipWhitespace();
      if (raw[index] === '}') { index += 1; return result; }
      if (raw[index] !== ',') fail('INVALID_JSON');
      index += 1;
      skipWhitespace();
    }
  }

  function parseValue() {
    skipWhitespace();
    if (index >= raw.length) fail('INVALID_JSON');
    const ch = raw[index];
    if (ch === '"') return parseString();
    if (ch === '{') return parseObject();
    if (ch === '[') return parseArray();
    if (ch === 't') return parseLiteral('true', true);
    if (ch === 'f') return parseLiteral('false', false);
    if (ch === 'n') return parseLiteral('null', null);
    if (ch === '-' || /[0-9]/.test(ch)) return parseNumber();
    fail('INVALID_JSON');
  }

  const value = parseValue();
  skipWhitespace();
  if (index !== raw.length) fail('INVALID_JSON');
  canonicalBytes(value);
  return value;
}

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
function nonEmptyString(value) { return typeof value === 'string' && value.length > 0; }
function integer(value) { return Number.isSafeInteger(value); }
function hex64(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }

const STATEMENT_FIELDS = [
  'payload_digest', 'issuer_id', 'signer_key_id', 'trust_root_id',
  'issued_at_ms', 'not_before_ms', 'not_after_ms', 'signature_algorithm',
];

function attestationStatement(envelope) {
  const attestation = envelope.attestation;
  const result = {
    profile_id: envelope.profile_id,
    schema_version: envelope.schema_version,
    canonical_profile: envelope.canonical_profile,
  };
  for (const field of STATEMENT_FIELDS) result[field] = attestation?.[field];
  return result;
}

function computeAttestationId(envelope) {
  return `attest_${canonicalSha256(attestationStatement(envelope)).slice(0, 24)}`;
}

function signedPayload(envelope) {
  return canonicalBytes({
    attestation_id: envelope.attestation?.attestation_id,
    ...attestationStatement(envelope),
  });
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

function verifyCanonicalSignedEnvelope(envelope, trustRoot, nowMs) {
  const reasons = [];
  const invalid = (code) => ({
    valid: false,
    payload_digest_matches: false,
    attestation_id_valid: false,
    canonical_profile_valid: false,
    signature_valid: false,
    trusted_current_authority: false,
    signed_payload_base64: '',
    reason_codes: [code],
  });

  if (!envelope || typeof envelope !== 'object' || Array.isArray(envelope)) return invalid('ENVELOPE_ROOT_INVALID');
  if (!trustRoot || typeof trustRoot !== 'object' || Array.isArray(trustRoot)) return invalid('TRUST_ROOT_INVALID');

  add(reasons, 'PROFILE_ID_MISMATCH', envelope.profile_id !== PROFILE_ID);
  add(reasons, 'SCHEMA_VERSION_MISMATCH', envelope.schema_version !== SCHEMA_VERSION);
  const canonicalProfileValid = envelope.canonical_profile === CANONICAL_PROFILE;
  add(reasons, 'CANONICAL_PROFILE_MISMATCH', !canonicalProfileValid);

  const payload = envelope.payload;
  const attestation = envelope.attestation;
  if (!(Array.isArray(payload) || (payload && typeof payload === 'object'))) add(reasons, 'PAYLOAD_INVALID', true);
  if (!(attestation && typeof attestation === 'object' && !Array.isArray(attestation))) {
    add(reasons, 'ATTESTATION_INVALID', true);
    return {
      valid: false, payload_digest_matches: false, attestation_id_valid: false,
      canonical_profile_valid: canonicalProfileValid, signature_valid: false,
      trusted_current_authority: false, signed_payload_base64: '', reason_codes: reasons,
    };
  }

  const required = {
    attestation_id: nonEmptyString, payload_digest: hex64, issuer_id: nonEmptyString,
    signer_key_id: nonEmptyString, trust_root_id: nonEmptyString, issued_at_ms: integer,
    not_before_ms: integer, not_after_ms: integer, signature_algorithm: nonEmptyString,
    signature: nonEmptyString,
  };
  for (const [field, predicate] of Object.entries(required)) {
    if (!(field in attestation) || !predicate(attestation[field])) add(reasons, `ATTESTATION_SCHEMA_INVALID:${field}`, true);
  }
  if (reasons.some((reason) => reason.startsWith('ATTESTATION_SCHEMA_INVALID:')) || reasons.includes('PAYLOAD_INVALID')) {
    return {
      valid: false, payload_digest_matches: false, attestation_id_valid: false,
      canonical_profile_valid: canonicalProfileValid, signature_valid: false,
      trusted_current_authority: false, signed_payload_base64: '', reason_codes: reasons,
    };
  }

  let actualPayloadDigest;
  let signed;
  try {
    actualPayloadDigest = canonicalSha256(payload);
    signed = signedPayload(envelope);
  } catch (error) {
    add(reasons, `CANONICALIZATION_ERROR:${error.code ?? 'UNKNOWN'}`, true);
    return {
      valid: false, payload_digest_matches: false, attestation_id_valid: false,
      canonical_profile_valid: canonicalProfileValid, signature_valid: false,
      trusted_current_authority: false, signed_payload_base64: '', reason_codes: reasons,
    };
  }

  const signedPayloadBase64 = signed.toString('base64');
  const payloadDigestMatches = attestation.payload_digest === actualPayloadDigest;
  add(reasons, 'PAYLOAD_DIGEST_MISMATCH', !payloadDigestMatches);
  const attestationIdValid = attestation.attestation_id === computeAttestationId(envelope);
  add(reasons, 'ATTESTATION_ID_INVALID', !attestationIdValid);

  const trustReasons = [];
  add(trustReasons, 'TRUST_ROOT_PROFILE_INVALID', trustRoot.profile_id !== TRUST_ROOT_PROFILE_ID);
  add(trustReasons, 'TRUST_ROOT_MISMATCH', attestation.trust_root_id !== trustRoot.trust_root_id);

  let allowedAlgorithms = trustRoot.allowed_algorithms;
  if (!Array.isArray(allowedAlgorithms) || !allowedAlgorithms.every(nonEmptyString)) {
    add(trustReasons, 'TRUST_ROOT_ALGORITHMS_INVALID', true);
    allowedAlgorithms = [];
  }
  const algorithm = attestation.signature_algorithm;
  const algorithmAllowed = algorithm === ED25519 && allowedAlgorithms.includes(algorithm);
  add(trustReasons, 'ALGORITHM_NOT_ALLOWED', !algorithmAllowed);

  let keys = trustRoot.keys;
  if (!Array.isArray(keys)) {
    add(trustReasons, 'TRUST_ROOT_KEYS_INVALID', true);
    keys = [];
  }
  const matchingKeys = keys.filter((key) => key && typeof key === 'object' && !Array.isArray(key) && key.signer_key_id === attestation.signer_key_id);
  const key = matchingKeys.length === 1 ? matchingKeys[0] : null;
  add(trustReasons, 'SIGNER_NOT_TRUSTED', matchingKeys.length === 0);
  add(trustReasons, 'SIGNER_KEY_AMBIGUOUS', matchingKeys.length > 1);

  let signatureValid = false;
  if (key) {
    add(trustReasons, 'ISSUER_MISMATCH', key.issuer_id !== attestation.issuer_id);
    add(trustReasons, 'KEY_ALGORITHM_MISMATCH', key.algorithm !== algorithm);
    add(trustReasons, 'SIGNER_REVOKED', key.revoked === true);

    const keyIntervalValid = integer(key.not_before_ms) && integer(key.not_after_ms) && key.not_after_ms >= key.not_before_ms;
    add(trustReasons, 'SIGNER_KEY_VALIDITY_INVALID', !keyIntervalValid);
    add(trustReasons, 'SIGNER_KEY_NOT_CURRENT', keyIntervalValid && (nowMs < key.not_before_ms || nowMs > key.not_after_ms));

    const publicKey = decodeBase64(key.public_key_base64);
    const signature = decodeBase64(attestation.signature);
    const keyMaterialValid = publicKey !== null && publicKey.length === 32;
    add(trustReasons, 'TRUST_KEY_MATERIAL_INVALID', !keyMaterialValid);

    if (algorithmAllowed && key.algorithm === ED25519 && signature !== null && keyMaterialValid) {
      try {
        const spki = Buffer.concat([
          Buffer.from('302a300506032b6570032100', 'hex'),
          publicKey,
        ]);
        const publicKeyObject = crypto.createPublicKey({key: spki, format: 'der', type: 'spki'});
        signatureValid = crypto.verify(null, signed, publicKeyObject, signature);
      } catch {
        signatureValid = false;
      }
    }
    add(reasons, 'SIGNATURE_INVALID', !signatureValid && algorithmAllowed && keyMaterialValid);
  }

  add(trustReasons, 'ATTESTATION_VALIDITY_INVALID', attestation.not_after_ms < attestation.not_before_ms);
  add(trustReasons, 'ATTESTATION_NOT_YET_VALID', nowMs < attestation.not_before_ms);
  add(trustReasons, 'ATTESTATION_EXPIRED', nowMs > attestation.not_after_ms);
  add(trustReasons, 'ATTESTATION_ISSUED_IN_FUTURE', attestation.issued_at_ms > nowMs);
  for (const reason of trustReasons) add(reasons, reason, true);

  const trustedCurrentAuthority = trustReasons.length === 0;
  const valid = payloadDigestMatches && attestationIdValid && canonicalProfileValid && signatureValid && trustedCurrentAuthority && reasons.length === 0;
  return {
    valid,
    payload_digest_matches: payloadDigestMatches,
    attestation_id_valid: attestationIdValid,
    canonical_profile_valid: canonicalProfileValid,
    signature_valid: signatureValid,
    trusted_current_authority: trustedCurrentAuthority,
    signed_payload_base64: signedPayloadBase64,
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

function runFixture(fixture) {
  const cases = fixture.cases.map((testCase) => {
    const envelope = structuredClone(fixture.base_envelope);
    const trustRoot = structuredClone(fixture.trust_root);
    for (const mutation of testCase.envelope_mutations ?? []) setPath(envelope, mutation.path, mutation.value);
    for (const mutation of testCase.trust_root_mutations ?? []) setPath(trustRoot, mutation.path, mutation.value);
    const result = verifyCanonicalSignedEnvelope(envelope, trustRoot, testCase.now_ms);
    const actual = {
      valid: result.valid,
      payload_digest_matches: result.payload_digest_matches,
      attestation_id_valid: result.attestation_id_valid,
      canonical_profile_valid: result.canonical_profile_valid,
      signature_valid: result.signature_valid,
      trusted_current_authority: result.trusted_current_authority,
      reason_codes: result.reason_codes,
    };
    return {
      id: testCase.id,
      actual,
      expected: testCase.expected,
      passed: JSON.stringify(actual) === JSON.stringify(testCase.expected),
    };
  });

  const baseResult = verifyCanonicalSignedEnvelope(structuredClone(fixture.base_envelope), structuredClone(fixture.trust_root), fixture.base_now_ms);
  const signature = fixture.base_envelope.attestation.signature;
  const parity = {
    signed_payload_base64: baseResult.signed_payload_base64,
    signed_payload_matches_expected: baseResult.signed_payload_base64 === fixture.expected_signed_payload_base64,
    signature_base64: signature,
    signature_matches_expected: signature === fixture.expected_signature_base64,
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
      all_passed: passed === cases.length && parity.signed_payload_matches_expected && parity.signature_matches_expected,
    },
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: node reference/canonical-signed-envelope-v0.11.mjs <fixture.json>');
  process.exit(2);
}

const fixture = strictParse(fs.readFileSync(fixturePath, 'utf8'));
const result = runFixture(fixture);
console.log(JSON.stringify(result, null, 2));
if (!result.summary.all_passed) process.exitCode = 1;
