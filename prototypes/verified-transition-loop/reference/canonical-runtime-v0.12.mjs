import crypto from 'node:crypto';

export const CANONICAL_PROFILE = 'rfc8785-safe-integer/v0.10';
export const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

export class CanonicalizationError extends Error {
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

export function canonicalText(value) {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isInteger(value)) throw new CanonicalizationError('UNSUPPORTED_NUMBER');
    if (!Number.isSafeInteger(value)) throw new CanonicalizationError('INTEGER_OUT_OF_RANGE');
    return Object.is(value, -0) ? '0' : String(value);
  }
  if (typeof value === 'string') return escapeString(value);
  if (Array.isArray(value)) return `[${value.map(canonicalText).join(',')}]`;
  if (value && typeof value === 'object') {
    const keys = Object.keys(value);
    for (const key of keys) validateUnicodeScalarString(key);
    keys.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${keys.map((key) => `${escapeString(key)}:${canonicalText(value[key])}`).join(',')}}`;
  }
  throw new CanonicalizationError('UNSUPPORTED_TYPE');
}

export function canonicalBytes(value) {
  return Buffer.from(canonicalText(value), 'utf8');
}

export function canonicalSha256(value) {
  return crypto.createHash('sha256').update(canonicalBytes(value)).digest('hex');
}

export function strictParse(raw) {
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
