#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';
import {
  CANONICAL_PROFILE,
  canonicalBytes,
  canonicalSha256,
  strictParse,
} from './canonical-runtime-v0.12.mjs';

const PROFILE_ID = 'vtl-transparency-log-v0.14';
const SCHEMA_VERSION = 'vtl.transparency-log/v0.14';
const FIXTURE_SCHEMA_VERSION = 'vtl.transparency-log-fixture/v0.14';
const ENTRY_PROFILE_ID = 'vtl-transparency-log-entry/v0.14';
const CHECKPOINT_PROFILE_ID = 'vtl-transparency-log-checkpoint/v0.14';
const LOG_AUTHORITY_PROFILE_ID = 'vtl-transparency-log-authority/v0.14';
const VERIFIER_CHECKPOINT_PROFILE_ID = 'vtl-transparency-log-verifier-checkpoint/v0.14';
const ED25519 = 'ED25519';

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function nonEmptyString(value) {
  return typeof value === 'string' && value.length > 0;
}
function integer(value) {
  return Number.isSafeInteger(value);
}
function positiveInteger(value) {
  return integer(value) && value >= 1;
}
function hex64(value) {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
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

function nodeHash(left, right) {
  return crypto.createHash('sha256').update(Buffer.concat([Buffer.from([1]), left, right])).digest();
}
function merkleLeafHash(entry) {
  return crypto.createHash('sha256').update(Buffer.concat([Buffer.from([0]), canonicalBytes(entry)])).digest('hex');
}

function verifyInclusionProof({leafIndex, treeSize, leafHash, rootHash, auditPath}) {
  if (
    !integer(leafIndex)
    || !positiveInteger(treeSize)
    || leafIndex < 0
    || leafIndex >= treeSize
    || !hex64(leafHash)
    || !hex64(rootHash)
    || !Array.isArray(auditPath)
    || !auditPath.every(hex64)
  ) return false;

  let fn = leafIndex;
  let sn = treeSize - 1;
  let running = Buffer.from(leafHash, 'hex');
  for (const value of auditPath) {
    if (sn === 0) return false;
    const sibling = Buffer.from(value, 'hex');
    if ((fn & 1) || fn === sn) {
      running = nodeHash(sibling, running);
      while (fn !== 0 && (fn & 1) === 0) {
        fn >>= 1;
        sn >>= 1;
      }
    } else {
      running = nodeHash(running, sibling);
    }
    fn >>= 1;
    sn >>= 1;
  }
  return sn === 0 && running.toString('hex') === rootHash;
}

function verifyConsistencyProof({oldSize, newSize, oldRootHash, newRootHash, proof}) {
  if (
    !positiveInteger(oldSize)
    || !positiveInteger(newSize)
    || oldSize > newSize
    || !hex64(oldRootHash)
    || !hex64(newRootHash)
    || !Array.isArray(proof)
    || !proof.every(hex64)
  ) return false;

  if (oldSize === newSize) return proof.length === 0 && oldRootHash === newRootHash;

  let fn = oldSize - 1;
  let sn = newSize - 1;
  while (fn & 1) {
    fn >>= 1;
    sn >>= 1;
  }

  const nodes = proof.map((value) => Buffer.from(value, 'hex'));
  let oldRunning;
  let newRunning;
  if (fn === 0) {
    oldRunning = Buffer.from(oldRootHash, 'hex');
    newRunning = Buffer.from(oldRootHash, 'hex');
  } else {
    if (nodes.length === 0) return false;
    oldRunning = nodes.shift();
    newRunning = oldRunning;
  }

  for (const node of nodes) {
    if (sn === 0) return false;
    if ((fn & 1) || fn === sn) {
      oldRunning = nodeHash(node, oldRunning);
      newRunning = nodeHash(node, newRunning);
      while (fn !== 0 && (fn & 1) === 0) {
        fn >>= 1;
        sn >>= 1;
      }
    } else {
      newRunning = nodeHash(newRunning, node);
    }
    fn >>= 1;
    sn >>= 1;
  }

  return sn === 0
    && oldRunning.toString('hex') === oldRootHash
    && newRunning.toString('hex') === newRootHash;
}

const CHECKPOINT_FIELDS = [
  'profile_id',
  'schema_version',
  'canonical_profile',
  'log_id',
  'tree_size',
  'root_hash',
  'issued_at_ms',
  'not_before_ms',
  'not_after_ms',
  'issuer_id',
  'log_authority_id',
  'log_key_id',
  'signature_algorithm',
];

function checkpointStatement(checkpoint) {
  const result = {};
  for (const field of CHECKPOINT_FIELDS) result[field] = checkpoint?.[field];
  return result;
}
function computeCheckpointId(checkpoint) {
  return `logcp_${canonicalSha256(checkpointStatement(checkpoint)).slice(0, 24)}`;
}
function signedCheckpointPayload(checkpoint) {
  return canonicalBytes({checkpoint_id: checkpoint?.checkpoint_id, ...checkpointStatement(checkpoint)});
}
function checkpointDigest(checkpoint) {
  return canonicalSha256(checkpoint);
}

function verifyCheckpoint(checkpoint, authority, nowMs) {
  const reasons = [];
  if (!isObject(checkpoint)) return [false, false, false, false, ['CHECKPOINT_INVALID']];
  if (!isObject(authority)) return [false, false, false, false, ['LOG_AUTHORITY_INVALID']];
  if (!integer(nowMs)) return [false, false, false, false, ['NOW_MS_INVALID']];

  add(reasons, 'CHECKPOINT_PROFILE_INVALID', checkpoint.profile_id !== CHECKPOINT_PROFILE_ID);
  add(reasons, 'CHECKPOINT_SCHEMA_VERSION_INVALID', checkpoint.schema_version !== SCHEMA_VERSION);
  const canonicalProfileValid = checkpoint.canonical_profile === CANONICAL_PROFILE;
  add(reasons, 'CANONICAL_PROFILE_MISMATCH', !canonicalProfileValid);
  add(reasons, 'CHECKPOINT_LOG_ID_INVALID', !nonEmptyString(checkpoint.log_id));
  add(reasons, 'CHECKPOINT_TREE_SIZE_INVALID', !positiveInteger(checkpoint.tree_size));
  add(reasons, 'CHECKPOINT_ROOT_HASH_INVALID', !hex64(checkpoint.root_hash));
  add(reasons, 'CHECKPOINT_ISSUER_INVALID', !nonEmptyString(checkpoint.issuer_id));
  add(reasons, 'CHECKPOINT_AUTHORITY_ID_INVALID', !nonEmptyString(checkpoint.log_authority_id));
  add(reasons, 'CHECKPOINT_KEY_ID_INVALID', !nonEmptyString(checkpoint.log_key_id));
  add(reasons, 'CHECKPOINT_ALGORITHM_INVALID', !nonEmptyString(checkpoint.signature_algorithm));
  add(reasons, 'CHECKPOINT_SIGNATURE_ENCODING_INVALID', decodeBase64(checkpoint.signature) === null);

  let expectedId = null;
  try { expectedId = computeCheckpointId(checkpoint); } catch {}
  add(reasons, 'CHECKPOINT_ID_INVALID', checkpoint.checkpoint_id !== expectedId);

  add(reasons, 'LOG_AUTHORITY_PROFILE_INVALID', authority.profile_id !== LOG_AUTHORITY_PROFILE_ID);
  add(reasons, 'LOG_AUTHORITY_ID_MISMATCH', authority.log_authority_id !== checkpoint.log_authority_id);
  const allowed = authority.allowed_algorithms;
  const algorithm = checkpoint.signature_algorithm;
  const algorithmAllowed = Array.isArray(allowed) && allowed.includes(algorithm);
  add(reasons, 'LOG_ALGORITHM_NOT_ALLOWED', !algorithmAllowed);

  const keys = authority.keys;
  const matches = Array.isArray(keys)
    ? keys.filter((key) => isObject(key) && key.log_key_id === checkpoint.log_key_id)
    : [];
  add(reasons, 'LOG_KEY_NOT_TRUSTED', matches.length === 0);
  add(reasons, 'LOG_KEY_AMBIGUOUS', matches.length > 1);

  let signatureValid = false;
  let authorityValid = false;
  const key = matches.length === 1 ? matches[0] : null;
  if (key) {
    const publicKey = decodeBase64(key.public_key_base64);
    const keyMaterialValid = publicKey !== null && publicKey.length === 32;
    add(reasons, 'LOG_KEY_MATERIAL_INVALID', !keyMaterialValid);
    add(reasons, 'LOG_KEY_ISSUER_MISMATCH', key.issuer_id !== checkpoint.issuer_id);
    add(reasons, 'LOG_KEY_ALGORITHM_MISMATCH', key.algorithm !== algorithm);
    add(reasons, 'LOG_KEY_REVOKED', key.revoked === true);

    const keyIntervalValid = integer(key.not_before_ms)
      && integer(key.not_after_ms)
      && key.not_after_ms >= key.not_before_ms;
    add(reasons, 'LOG_KEY_VALIDITY_INVALID', !keyIntervalValid);
    add(reasons, 'LOG_KEY_NOT_YET_VALID', keyIntervalValid && nowMs < key.not_before_ms);
    add(reasons, 'LOG_KEY_EXPIRED', keyIntervalValid && nowMs > key.not_after_ms);

    const signature = decodeBase64(checkpoint.signature);
    if (
      algorithm === ED25519
      && algorithmAllowed
      && key.algorithm === ED25519
      && keyMaterialValid
      && signature !== null
    ) {
      try {
        const spki = Buffer.concat([
          Buffer.from('302a300506032b6570032100', 'hex'),
          publicKey,
        ]);
        const publicKeyObject = crypto.createPublicKey({key: spki, format: 'der', type: 'spki'});
        signatureValid = crypto.verify(null, signedCheckpointPayload(checkpoint), publicKeyObject, signature);
      } catch {
        signatureValid = false;
      }
      add(reasons, 'CHECKPOINT_SIGNATURE_INVALID', !signatureValid);
    }

    authorityValid = authority.profile_id === LOG_AUTHORITY_PROFILE_ID
      && authority.log_authority_id === checkpoint.log_authority_id
      && algorithmAllowed
      && keyMaterialValid
      && key.issuer_id === checkpoint.issuer_id
      && key.algorithm === algorithm
      && key.revoked === false
      && keyIntervalValid
      && nowMs >= key.not_before_ms
      && nowMs <= key.not_after_ms;
  }

  let freshnessValid = true;
  const validityIntervalValid = integer(checkpoint.not_before_ms)
    && integer(checkpoint.not_after_ms)
    && checkpoint.not_after_ms >= checkpoint.not_before_ms;
  add(reasons, 'CHECKPOINT_VALIDITY_INVALID', !validityIntervalValid);
  if (!validityIntervalValid) freshnessValid = false;
  if (validityIntervalValid && nowMs < checkpoint.not_before_ms) {
    add(reasons, 'CHECKPOINT_NOT_YET_VALID', true);
    freshnessValid = false;
  }
  if (validityIntervalValid && nowMs > checkpoint.not_after_ms) {
    add(reasons, 'CHECKPOINT_EXPIRED', true);
    freshnessValid = false;
  }
  if (!integer(checkpoint.issued_at_ms) || checkpoint.issued_at_ms > nowMs) {
    add(reasons, 'CHECKPOINT_ISSUED_IN_FUTURE', true);
    freshnessValid = false;
  }

  return [canonicalProfileValid, signatureValid, authorityValid, freshnessValid, reasons];
}

function verifyTransparencyLog(bundle, nowMs) {
  if (!isObject(bundle)) {
    return {
      valid: false,
      local_witnessed_freshness_valid: false,
      entry_integrity_valid: false,
      log_checkpoint_signature_valid: false,
      log_checkpoint_authority_valid: false,
      log_checkpoint_freshness_valid: false,
      inclusion_valid: false,
      consistency_valid: false,
      view_consistency_valid: false,
      log_equivocation_detected: false,
      accepted_tree_size: null,
      accepted_root_hash: null,
      reason_codes: ['TRANSPARENCY_BUNDLE_INVALID'],
    };
  }

  const reasons = [];
  const localValid = bundle.local_witnessed_freshness_valid === true;
  add(reasons, 'LOCAL_WITNESSED_FRESHNESS_INVALID', !localValid);

  const target = bundle.target;
  const entry = bundle.entry;
  let entryIntegrityValid = isObject(target) && isObject(entry);
  let leafHash = null;
  if (!entryIntegrityValid) {
    add(reasons, 'ENTRY_OR_TARGET_INVALID', true);
  } else {
    add(reasons, 'ENTRY_PROFILE_INVALID', entry.profile_id !== ENTRY_PROFILE_ID);
    add(reasons, 'ENTRY_CANONICAL_PROFILE_INVALID', entry.canonical_profile !== CANONICAL_PROFILE);
    for (const [field, code] of [
      ['log_id', 'ENTRY_LOG_ID_MISMATCH'],
      ['trust_root_id', 'ENTRY_TRUST_ROOT_MISMATCH'],
      ['snapshot_generation', 'ENTRY_GENERATION_MISMATCH'],
      ['snapshot_digest', 'ENTRY_SNAPSHOT_DIGEST_MISMATCH'],
    ]) {
      const mismatch = entry[field] !== target[field];
      add(reasons, code, mismatch);
      entryIntegrityValid = entryIntegrityValid && !mismatch;
    }
    entryIntegrityValid = entryIntegrityValid
      && entry.profile_id === ENTRY_PROFILE_ID
      && entry.canonical_profile === CANONICAL_PROFILE
      && entry.entry_type === 'trust-root-snapshot'
      && nonEmptyString(entry.log_id)
      && nonEmptyString(entry.trust_root_id)
      && positiveInteger(entry.snapshot_generation)
      && hex64(entry.snapshot_digest);
    add(reasons, 'ENTRY_TYPE_INVALID', entry.entry_type !== 'trust-root-snapshot');
    try {
      leafHash = merkleLeafHash(entry);
    } catch {
      leafHash = null;
      entryIntegrityValid = false;
      add(reasons, 'ENTRY_CANONICALIZATION_FAILED', true);
    }
  }

  const checkpoint = bundle.checkpoint;
  const authority = bundle.log_authority;
  const [
    canonicalProfileValid,
    checkpointSignatureValid,
    checkpointAuthorityValid,
    checkpointFreshnessValid,
    checkpointReasons,
  ] = verifyCheckpoint(checkpoint, authority, nowMs);
  for (const reason of checkpointReasons) add(reasons, reason, true);

  if (isObject(entry) && isObject(checkpoint)) {
    const mismatch = entry.log_id !== checkpoint.log_id;
    add(reasons, 'ENTRY_CHECKPOINT_LOG_ID_MISMATCH', mismatch);
    entryIntegrityValid = entryIntegrityValid && !mismatch;
  }

  const inclusionValid = leafHash !== null
    && isObject(checkpoint)
    && verifyInclusionProof({
      leafIndex: bundle.leaf_index,
      treeSize: checkpoint.tree_size,
      leafHash,
      rootHash: checkpoint.root_hash,
      auditPath: bundle.inclusion_path,
    });
  add(reasons, 'INCLUSION_PROOF_INVALID', !inclusionValid);

  const verifierCheckpoint = bundle.verifier_checkpoint;
  let consistencyValid = true;
  let equivocationDetected = false;
  if (!isObject(verifierCheckpoint)) {
    add(reasons, 'LOG_VERIFIER_CHECKPOINT_INVALID', true);
    consistencyValid = false;
  } else if (verifierCheckpoint.profile_id !== VERIFIER_CHECKPOINT_PROFILE_ID) {
    add(reasons, 'LOG_VERIFIER_CHECKPOINT_INVALID', true);
    consistencyValid = false;
  } else {
    if (!integer(verifierCheckpoint.checkpointed_at_ms)) {
      add(reasons, 'LOG_VERIFIER_CHECKPOINT_TIME_INVALID', true);
      consistencyValid = false;
    } else if (verifierCheckpoint.checkpointed_at_ms > nowMs) {
      add(reasons, 'LOG_VERIFIER_CHECKPOINT_FROM_FUTURE', true);
      consistencyValid = false;
    }

    if (!isObject(checkpoint) || verifierCheckpoint.log_id !== checkpoint.log_id) {
      add(reasons, 'LOG_ID_MISMATCH', true);
      consistencyValid = false;
    }

    const knownSize = verifierCheckpoint.known_tree_size;
    const knownRoot = verifierCheckpoint.known_root_hash;
    const treeSize = isObject(checkpoint) ? checkpoint.tree_size : null;
    const rootHash = isObject(checkpoint) ? checkpoint.root_hash : null;

    if (
      !positiveInteger(knownSize)
      || !hex64(knownRoot)
      || !positiveInteger(treeSize)
      || !hex64(rootHash)
    ) {
      add(reasons, 'LOG_VERIFIER_KNOWN_STATE_INVALID', true);
      consistencyValid = false;
    } else {
      const floor = verifierCheckpoint.minimum_tree_size;
      if (!positiveInteger(floor)) {
        add(reasons, 'LOG_MINIMUM_TREE_SIZE_INVALID', true);
        consistencyValid = false;
      } else if (treeSize < floor) {
        add(reasons, 'LOG_TREE_SIZE_BELOW_FLOOR', true);
        consistencyValid = false;
      }

      if (treeSize < knownSize) {
        add(reasons, 'LOG_CHECKPOINT_ROLLBACK', true);
        consistencyValid = false;
      } else if (treeSize === knownSize) {
        if (rootHash !== knownRoot) {
          add(reasons, 'LOG_EQUIVOCATION_DETECTED', true);
          equivocationDetected = true;
          consistencyValid = false;
        } else if (!(
          bundle.consistency_path === null
          || (Array.isArray(bundle.consistency_path) && bundle.consistency_path.length === 0)
        )) {
          add(reasons, 'LOG_CONSISTENCY_PROOF_INVALID', true);
          consistencyValid = false;
        }
      } else {
        const proofValid = verifyConsistencyProof({
          oldSize: knownSize,
          newSize: treeSize,
          oldRootHash: knownRoot,
          newRootHash: rootHash,
          proof: bundle.consistency_path,
        });
        add(reasons, 'LOG_CONSISTENCY_PROOF_INVALID', !proofValid);
        consistencyValid = consistencyValid && proofValid;
      }
    }
  }

  const peers = bundle.peer_checkpoints;
  if (Array.isArray(peers) && isObject(checkpoint)) {
    for (const peer of peers) {
      const [peerCanonical, peerSignature, peerAuthority, peerFreshness] = verifyCheckpoint(peer, authority, nowMs);
      const trustedPeer = peerCanonical
        && peerSignature
        && peerAuthority
        && peerFreshness
        && isObject(peer)
        && peer.log_id === checkpoint.log_id;
      if (
        trustedPeer
        && peer.tree_size === checkpoint.tree_size
        && peer.root_hash !== checkpoint.root_hash
      ) {
        add(reasons, 'LOG_EQUIVOCATION_DETECTED', true);
        equivocationDetected = true;
      }
    }
  }

  const viewConsistencyValid = !equivocationDetected;
  const valid = localValid
    && entryIntegrityValid
    && canonicalProfileValid
    && checkpointSignatureValid
    && checkpointAuthorityValid
    && checkpointFreshnessValid
    && inclusionValid
    && consistencyValid
    && viewConsistencyValid;

  return {
    valid,
    local_witnessed_freshness_valid: localValid,
    entry_integrity_valid: entryIntegrityValid,
    log_checkpoint_signature_valid: checkpointSignatureValid,
    log_checkpoint_authority_valid: checkpointAuthorityValid,
    log_checkpoint_freshness_valid: checkpointFreshnessValid,
    inclusion_valid: inclusionValid,
    consistency_valid: consistencyValid,
    view_consistency_valid: viewConsistencyValid,
    log_equivocation_detected: equivocationDetected,
    accepted_tree_size: isObject(checkpoint) && positiveInteger(checkpoint.tree_size) ? checkpoint.tree_size : null,
    accepted_root_hash: isObject(checkpoint) && hex64(checkpoint.root_hash) ? checkpoint.root_hash : null,
    reason_codes: reasons,
  };
}

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}
function setPath(root, path, value) {
  const parts = path.split('.');
  let current = root;
  for (const part of parts.slice(0, -1)) current = /^\d+$/.test(part) ? current[Number(part)] : current[part];
  const last = parts.at(-1);
  if (/^\d+$/.test(last)) current[Number(last)] = value;
  else current[last] = value;
}
function caseBundle(fixture, testCase) {
  const bundle = deepCopy(fixture.base_bundle);
  if (testCase.checkpoint_ref !== undefined) bundle.checkpoint = deepCopy(fixture.checkpoint_variants[testCase.checkpoint_ref]);
  if (testCase.verifier_checkpoint_ref !== undefined) {
    bundle.verifier_checkpoint = deepCopy(fixture.verifier_checkpoint_variants[testCase.verifier_checkpoint_ref]);
  }
  if (testCase.inclusion_path_ref !== undefined) bundle.inclusion_path = deepCopy(fixture.inclusion_path_variants[testCase.inclusion_path_ref]);
  if (testCase.consistency_path_ref !== undefined) bundle.consistency_path = deepCopy(fixture.consistency_path_variants[testCase.consistency_path_ref]);
  if (testCase.peer_checkpoint_refs !== undefined) {
    bundle.peer_checkpoints = testCase.peer_checkpoint_refs.map((ref) => deepCopy(fixture.checkpoint_variants[ref]));
  }
  for (const mutation of testCase.mutations ?? []) setPath(bundle, mutation.path, deepCopy(mutation.value));
  return bundle;
}
function semanticallyEqual(a, b) {
  return canonicalSha256(a) === canonicalSha256(b);
}

function runFixture(fixture) {
  if (!isObject(fixture)) throw new Error('FIXTURE_ROOT_INVALID');
  if (fixture.profile_id !== PROFILE_ID) throw new Error('PROFILE_ID_MISMATCH');
  if (fixture.schema_version !== FIXTURE_SCHEMA_VERSION) throw new Error('SCHEMA_VERSION_MISMATCH');
  if (fixture.canonical_profile !== CANONICAL_PROFILE) throw new Error('CANONICAL_PROFILE_MISMATCH');

  const nowMs = fixture.base_now_ms;
  const cases = fixture.cases.map((testCase) => {
    const bundle = caseBundle(fixture, testCase);
    const actual = verifyTransparencyLog(bundle, nowMs);
    return {
      id: testCase.id,
      actual,
      expected: testCase.expected,
      passed: semanticallyEqual(actual, testCase.expected),
    };
  });

  const base = fixture.base_bundle;
  const entryBytes = canonicalBytes(base.entry);
  const checkpointPayload = signedCheckpointPayload(base.checkpoint);
  const parity = {
    entry_canonical_base64: entryBytes.toString('base64'),
    entry_canonical_matches_expected: entryBytes.toString('base64') === fixture.expected_base_entry_canonical_base64,
    leaf_hash: merkleLeafHash(base.entry),
    leaf_hash_matches_expected: merkleLeafHash(base.entry) === fixture.expected_base_leaf_hash,
    checkpoint_signed_payload_base64: checkpointPayload.toString('base64'),
    checkpoint_signed_payload_matches_expected: checkpointPayload.toString('base64') === fixture.expected_base_checkpoint_signed_payload_base64,
    checkpoint_signature_matches_expected: base.checkpoint.signature === fixture.expected_base_checkpoint_signature_base64,
    checkpoint_digest: checkpointDigest(base.checkpoint),
    checkpoint_digest_matches_expected: checkpointDigest(base.checkpoint) === fixture.expected_base_checkpoint_digest,
    root_hash_matches_expected: base.checkpoint.root_hash === fixture.expected_base_root_hash,
  };
  const passed = cases.filter((testCase) => testCase.passed).length;
  const parityPassed = Object.entries(parity)
    .filter(([key]) => key.endsWith('_matches_expected'))
    .every(([, value]) => value === true);
  const summary = {
    total: cases.length,
    passed,
    failed: cases.length - passed,
    all_passed: passed === cases.length && parityPassed,
  };
  return {
    profile_id: PROFILE_ID,
    schema_version: FIXTURE_SCHEMA_VERSION,
    canonical_profile: CANONICAL_PROFILE,
    cases,
    parity,
    summary,
  };
}

const fixturePath = process.argv[2];
if (!fixturePath) {
  console.error('usage: transparency log fixture path required');
  process.exit(2);
}
const fixture = strictParse(fs.readFileSync(fixturePath, 'utf8'));
const result = runFixture(fixture);
console.log(JSON.stringify(result, null, 2));
process.exit(result.summary.all_passed ? 0 : 1);
