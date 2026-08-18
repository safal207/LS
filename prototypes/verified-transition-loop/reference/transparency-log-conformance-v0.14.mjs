#!/usr/bin/env node

import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {canonicalSha256} from './canonical-runtime-v0.12.mjs';

function equal(a, b) {
  return canonicalSha256(a) === canonicalSha256(b);
}

function matchesExpected(actual, expected) {
  return Object.entries(expected).every(([key, value]) => {
    if (key === 'reason_codes') {
      return Array.isArray(actual[key])
        && Array.isArray(value)
        && equal([...actual[key]].sort(), [...value].sort());
    }
    return equal(actual[key], value);
  });
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: transparency log fixture path required');
  process.exit(2);
}

const verifierPath = fileURLToPath(new URL('./transparency-log-strict-v0.14.mjs', import.meta.url));
const child = spawnSync(process.execPath, [verifierPath, fixturePath], {
  encoding: 'utf8',
  maxBuffer: 16 * 1024 * 1024,
});
if (!child.stdout) {
  process.stderr.write(child.stderr ?? 'Node verifier produced no output\n');
  process.exit(1);
}

const result = JSON.parse(child.stdout);
for (const testCase of result.cases) {
  testCase.passed = matchesExpected(testCase.actual, testCase.expected);
}
const passed = result.cases.filter((testCase) => testCase.passed).length;
const loadBearingParityKeys = [
  'entry_canonical_matches_expected',
  'leaf_hash_matches_expected',
  'checkpoint_signature_matches_expected',
  'checkpoint_digest_matches_expected',
  'root_hash_matches_expected',
];
const parityPassed = loadBearingParityKeys.every((key) => result.parity[key] === true);
result.summary = {
  total: result.cases.length,
  passed,
  failed: result.cases.length - passed,
  all_passed: passed === result.cases.length && parityPassed,
};

console.log(JSON.stringify(result, null, 2));
process.exit(result.summary.all_passed ? 0 : 1);
