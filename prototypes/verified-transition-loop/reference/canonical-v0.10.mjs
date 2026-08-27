#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';

const PROFILE_ID = 'vtl-canonical-proof-v0.10';
const SCHEMA_VERSION = 'vtl.canonical-proof/v0.10';
const CANONICAL_PROFILE = 'rfc8785-safe-integer/v0.10';
const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;
const FIXTURE_FIELDS = [
  'profile_id',
  'schema_version',
  'canonical_profile',
  'cases',
  'negative_cases',
  'mutation_cases',
];
const CASE_FIELDS = ['id', 'raw_json', 'canonical_utf8_base64', 'sha256'];
const NEGATIVE_CASE_FIELDS = ['id', 'raw_json', 'error_code'];
const MUTATION_CASE_FIELDS = [
  'id',
  'base_raw_json',
  'mutated_raw_json',
  'base_sha256',
  'mutated_sha256',
  'digests_differ',
];
const NEGATIVE_ERROR_CODES = new Set([
  'UNSUPPORTED_NUMBER',
  'INTEGER_OUT_OF_RANGE',
  'DUPLICATE_KEY',
  'INVALID_UNICODE_SCALAR',
  'INVALID_JSON',
]);

class CanonicalizationError extends Error {
  constructor(code, detail = '') {
    super(detail || code);
    this.code = code;
  }
}

function validateUnicodeScalarString(value) {
  for (let i = 0; i < value.length; i += 1) {
    const code = value.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      if (i + 1 >= value.length) {
        throw new CanonicalizationError('INVALID_UNICODE_SCALAR');
      }
      const next = value.charCodeAt(i + 1);
      if (next < 0xdc00 || next > 0xdfff) {
        throw new CanonicalizationError('INVALID_UNICODE_SCALAR');
      }
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

function compareUtf16(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
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
  if (Array.isArray(value)) return `[${value.map((item) => canonicalText(item)).join(',')}]`;
  if (typeof value === 'object') {
    const keys = Object.keys(value);
    for (const key of keys) validateUnicodeScalarString(key);
    keys.sort(compareUtf16);
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

  function fail(code, detail = '') {
    throw new CanonicalizationError(code, detail);
  }

  function skipWhitespace() {
    while (index < raw.length && /[\t\n\r ]/.test(raw[index])) index += 1;
  }

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
        try {
          value = JSON.parse(raw.slice(start, index));
        } catch {
          fail('INVALID_JSON');
        }
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
    let big;
    try {
      big = BigInt(token);
    } catch {
      fail('INVALID_JSON');
    }
    const max = BigInt(MAX_SAFE_INTEGER);
    if (big > max || big < -max) fail('INTEGER_OUT_OF_RANGE');
    return Number(big);
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
    if (raw[index] === ']') {
      index += 1;
      return result;
    }
    while (true) {
      result.push(parseValue());
      skipWhitespace();
      if (raw[index] === ']') {
        index += 1;
        return result;
      }
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
    if (raw[index] === '}') {
      index += 1;
      return result;
    }
    while (true) {
      if (raw[index] !== '"') fail('INVALID_JSON');
      const key = parseString();
      if (seen.has(key)) fail('DUPLICATE_KEY', key);
      seen.add(key);
      skipWhitespace();
      if (raw[index] !== ':') fail('INVALID_JSON');
      index += 1;
      result[key] = parseValue();
      skipWhitespace();
      if (raw[index] === '}') {
        index += 1;
        return result;
      }
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

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasExactFields(value, fields) {
  if (!isRecord(value)) return false;
  const keys = Object.keys(value);
  return keys.length === fields.length && fields.every((field) => keys.includes(field));
}

function isNonEmptyString(value) {
  return typeof value === 'string' && value.length > 0;
}

function isHex64(value) {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}

function isCanonicalBase64(value) {
  if (!isNonEmptyString(value)) return false;
  return Buffer.from(value, 'base64').toString('base64') === value;
}

function validateFixtureShape(fixture) {
  if (!isRecord(fixture)) throw new CanonicalizationError('FIXTURE_ROOT_INVALID');
  if (!hasExactFields(fixture, FIXTURE_FIELDS)) {
    throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', 'fixture fields');
  }

  const groups = [
    ['cases', CASE_FIELDS],
    ['negative_cases', NEGATIVE_CASE_FIELDS],
    ['mutation_cases', MUTATION_CASE_FIELDS],
  ];
  const identifiers = new Set();
  for (const [groupName, fields] of groups) {
    const group = fixture[groupName];
    if (!Array.isArray(group) || group.length === 0) {
      throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `${groupName} must be non-empty`);
    }
    for (let index = 0; index < group.length; index += 1) {
      const testCase = group[index];
      if (!hasExactFields(testCase, fields)) {
        throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `${groupName}[${index}] fields`);
      }
      if (!isNonEmptyString(testCase.id)) {
        throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `${groupName}[${index}].id`);
      }
      if (identifiers.has(testCase.id)) {
        throw new CanonicalizationError('FIXTURE_CASE_ID_DUPLICATE', testCase.id);
      }
      identifiers.add(testCase.id);
    }
  }

  fixture.cases.forEach((testCase, index) => {
    if (
      typeof testCase.raw_json !== 'string'
      || !isCanonicalBase64(testCase.canonical_utf8_base64)
      || !isHex64(testCase.sha256)
    ) {
      throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `cases[${index}] values`);
    }
  });

  fixture.negative_cases.forEach((testCase, index) => {
    if (
      typeof testCase.raw_json !== 'string'
      || !NEGATIVE_ERROR_CODES.has(testCase.error_code)
    ) {
      throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `negative_cases[${index}] values`);
    }
  });

  fixture.mutation_cases.forEach((testCase, index) => {
    if (
      typeof testCase.base_raw_json !== 'string'
      || typeof testCase.mutated_raw_json !== 'string'
      || !isHex64(testCase.base_sha256)
      || !isHex64(testCase.mutated_sha256)
      || testCase.digests_differ !== true
    ) {
      throw new CanonicalizationError('FIXTURE_SCHEMA_INVALID', `mutation_cases[${index}] values`);
    }
  });
}

function verifyFixture(fixture) {
  validateFixtureShape(fixture);
  if (fixture.profile_id !== PROFILE_ID) throw new CanonicalizationError('PROFILE_ID_MISMATCH');
  if (fixture.schema_version !== SCHEMA_VERSION) throw new CanonicalizationError('SCHEMA_VERSION_MISMATCH');
  if (fixture.canonical_profile !== CANONICAL_PROFILE) throw new CanonicalizationError('CANONICAL_PROFILE_MISMATCH');

  const cases = fixture.cases.map((testCase) => {
    const value = strictParse(testCase.raw_json);
    const bytes = canonicalBytes(value);
    const canonicalUtf8Base64 = bytes.toString('base64');
    const sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    return {
      id: testCase.id,
      canonical_utf8_base64: canonicalUtf8Base64,
      sha256,
      passed: canonicalUtf8Base64 === testCase.canonical_utf8_base64 && sha256 === testCase.sha256,
    };
  });

  const negativeCases = fixture.negative_cases.map((testCase) => {
    let errorCode = null;
    try {
      const value = strictParse(testCase.raw_json);
      canonicalBytes(value);
    } catch (error) {
      if (error instanceof CanonicalizationError) errorCode = error.code;
      else throw error;
    }
    return {id: testCase.id, error_code: errorCode, passed: errorCode === testCase.error_code};
  });

  const mutationCases = fixture.mutation_cases.map((testCase) => {
    const baseDigest = canonicalSha256(strictParse(testCase.base_raw_json));
    const mutatedDigest = canonicalSha256(strictParse(testCase.mutated_raw_json));
    const digestsDiffer = baseDigest !== mutatedDigest;
    return {
      id: testCase.id,
      base_sha256: baseDigest,
      mutated_sha256: mutatedDigest,
      digests_differ: digestsDiffer,
      passed: baseDigest === testCase.base_sha256 && mutatedDigest === testCase.mutated_sha256 && digestsDiffer === testCase.digests_differ,
    };
  });

  const all = [...cases, ...negativeCases, ...mutationCases];
  const passed = all.filter((result) => result.passed).length;
  return {
    profile_id: PROFILE_ID,
    schema_version: SCHEMA_VERSION,
    canonical_profile: CANONICAL_PROFILE,
    cases,
    negative_cases: negativeCases,
    mutation_cases: mutationCases,
    summary: {
      total: all.length,
      passed,
      failed: all.length - passed,
      all_passed: passed === all.length,
    },
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: node reference/canonical-v0.10.mjs <fixture.json>');
  process.exit(2);
}

const fixture = strictParse(fs.readFileSync(fixturePath, 'utf8'));
const result = verifyFixture(fixture);
console.log(JSON.stringify(result, null, 2));
if (!result.summary.all_passed) process.exitCode = 1;
