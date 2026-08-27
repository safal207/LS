#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {
  CANONICAL_PROFILE,
  canonicalBytes,
  canonicalSha256,
  strictParse,
} from './canonical-runtime-v0.12.mjs';

export const PROFILE_ID = 'vtl-transparency-log-v0.14';
export const SCHEMA_VERSION = 'vtl.transparency-log/v0.14';
export const FIXTURE_SCHEMA_VERSION = 'vtl.transparency-log-fixture/v0.14';
export const ENTRY_PROFILE_ID = 'vtl-transparency-log-entry/v0.14';
export const CHECKPOINT_PROFILE_ID = 'vtl-transparency-log-checkpoint/v0.14';
export const LOG_AUTHORITY_PROFILE_ID = 'vtl-transparency-log-authority/v0.14';
export const VERIFIER_CHECKPOINT_PROFILE_ID = 'vtl-transparency-log-verifier-checkpoint/v0.14';
export const ED25519 = 'ED25519';
export const PUBLIC_KEY_BYTES = 32;
export const SIGNATURE_BYTES = 64;
export const MAX_PROOF_NODES = 54;

export const BUNDLE_FIELDS = new Set([
  'local_witnessed_freshness_valid', 'target', 'entry', 'leaf_index',
  'inclusion_path', 'checkpoint', 'log_authority', 'verifier_checkpoint',
  'consistency_path', 'peer_checkpoints',
]);
export const TARGET_FIELDS = new Set([
  'log_id', 'trust_root_id', 'snapshot_generation', 'snapshot_digest',
]);
export const ENTRY_FIELDS = new Set([
  'profile_id', 'canonical_profile', 'entry_type', 'log_id', 'trust_root_id',
  'snapshot_generation', 'snapshot_digest',
]);
export const CHECKPOINT_STATEMENT_FIELDS = [
  'profile_id', 'schema_version', 'canonical_profile', 'log_id', 'tree_size',
  'root_hash', 'issued_at_ms', 'not_before_ms', 'not_after_ms', 'issuer_id',
  'log_authority_id', 'log_key_id', 'signature_algorithm',
];
export const CHECKPOINT_FIELDS = new Set([
  ...CHECKPOINT_STATEMENT_FIELDS, 'checkpoint_id', 'signature',
]);
export const AUTHORITY_FIELDS = new Set([
  'profile_id', 'log_authority_id', 'allowed_algorithms', 'keys',
]);
export const KEY_FIELDS = new Set([
  'log_key_id', 'issuer_id', 'algorithm', 'public_key_base64',
  'not_before_ms', 'not_after_ms', 'revoked',
]);
export const VERIFIER_CHECKPOINT_FIELDS = new Set([
  'profile_id', 'log_id', 'known_tree_size', 'known_root_hash',
  'minimum_tree_size', 'checkpointed_at_ms',
]);
export const CHECKPOINT_INTEGRITY_REASONS = new Set([
  'CHECKPOINT_INVALID',
  'CHECKPOINT_FIELDS_INVALID',
  'CHECKPOINT_PROFILE_INVALID',
  'CHECKPOINT_SCHEMA_VERSION_INVALID',
  'CANONICAL_PROFILE_MISMATCH',
  'CHECKPOINT_LOG_ID_INVALID',
  'CHECKPOINT_TREE_SIZE_INVALID',
  'CHECKPOINT_ROOT_HASH_INVALID',
  'CHECKPOINT_ISSUED_AT_INVALID',
  'CHECKPOINT_NOT_BEFORE_INVALID',
  'CHECKPOINT_NOT_AFTER_INVALID',
  'CHECKPOINT_ISSUER_INVALID',
  'CHECKPOINT_AUTHORITY_ID_INVALID',
  'CHECKPOINT_KEY_ID_INVALID',
  'CHECKPOINT_ALGORITHM_INVALID',
  'CHECKPOINT_SIGNATURE_ENCODING_INVALID',
  'CHECKPOINT_ID_INVALID',
]);

function add(reasons, reason, condition) {
  if (condition && !reasons.includes(reason)) reasons.push(reason);
}
export function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
export function exactObject(value, fields) {
  if (!isObject(value)) return false;
  const keys = Object.keys(value);
  return keys.length === fields.size && keys.every((key) => fields.has(key));
}
export function nonEmptyString(value) {
  if (typeof value !== 'string' || value.length === 0) return false;
  try { canonicalBytes(value); } catch { return false; }
  return true;
}
export function integer(value) {
  return Number.isSafeInteger(value);
}
export function timestamp(value) {
  return integer(value) && value >= 0;
}
export function positiveInteger(value) {
  return integer(value) && value >= 1;
}
export function hex64(value) {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
}
export function decodeBase64(value) {
  try {
    if (typeof value !== 'string') return null;
    const decoded = Buffer.from(value, 'base64');
    return decoded.toString('base64') === value ? decoded : null;
  } catch {
    return null;
  }
}

function invalidResult(reasons, localWitnessedFreshnessValid = false) {
  return {
    valid: false,
    local_witnessed_freshness_valid: localWitnessedFreshnessValid === true,
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
    reason_codes: reasons,
  };
}

function nodeHash(left, right) {
  return crypto.createHash('sha256')
    .update(Buffer.concat([Buffer.from([1]), left, right]))
    .digest();
}
export function merkleLeafHash(entry) {
  return crypto.createHash('sha256')
    .update(Buffer.concat([Buffer.from([0]), canonicalBytes(entry)]))
    .digest('hex');
}

export function verifyInclusionProof({
  leafIndex,
  treeSize,
  leafHash,
  rootHash,
  auditPath,
}) {
  if (
    !integer(leafIndex)
    || !positiveInteger(treeSize)
    || leafIndex < 0
    || leafIndex >= treeSize
    || !hex64(leafHash)
    || !hex64(rootHash)
    || !Array.isArray(auditPath)
    || auditPath.length > MAX_PROOF_NODES
    || !auditPath.every(hex64)
  ) return false;

  let fn = leafIndex;
  let sn = treeSize - 1;
  let running = Buffer.from(leafHash, 'hex');
  for (const value of auditPath) {
    if (sn === 0) return false;
    const sibling = Buffer.from(value, 'hex');
    if ((fn % 2) === 1 || fn === sn) {
      running = nodeHash(sibling, running);
      while (fn !== 0 && (fn % 2) === 0) {
        fn = Math.floor(fn / 2);
        sn = Math.floor(sn / 2);
      }
    } else {
      running = nodeHash(running, sibling);
    }
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
  }
  return sn === 0 && running.toString('hex') === rootHash;
}

export function verifyConsistencyProof({
  oldSize,
  newSize,
  oldRootHash,
  newRootHash,
  proof,
}) {
  if (
    !positiveInteger(oldSize)
    || !positiveInteger(newSize)
    || oldSize > newSize
    || !hex64(oldRootHash)
    || !hex64(newRootHash)
    || !Array.isArray(proof)
    || proof.length > MAX_PROOF_NODES
    || !proof.every(hex64)
  ) return false;

  if (oldSize === newSize) {
    return proof.length === 0 && oldRootHash === newRootHash;
  }

  let fn = oldSize - 1;
  let sn = newSize - 1;
  while ((fn % 2) === 1) {
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
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
    if ((fn % 2) === 1 || fn === sn) {
      oldRunning = nodeHash(node, oldRunning);
      newRunning = nodeHash(node, newRunning);
      while (fn !== 0 && (fn % 2) === 0) {
        fn = Math.floor(fn / 2);
        sn = Math.floor(sn / 2);
      }
    } else {
      newRunning = nodeHash(newRunning, node);
    }
    fn = Math.floor(fn / 2);
    sn = Math.floor(sn / 2);
  }

  return sn === 0
    && oldRunning.toString('hex') === oldRootHash
    && newRunning.toString('hex') === newRootHash;
}

export function checkpointStatement(checkpoint) {
  const result = {};
  for (const field of CHECKPOINT_STATEMENT_FIELDS) {
    result[field] = checkpoint?.[field];
  }
  return result;
}
export function computeCheckpointId(checkpoint) {
  return `logcp_${canonicalSha256(checkpointStatement(checkpoint)).slice(0, 24)}`;
}
export function signedCheckpointPayload(checkpoint) {
  return canonicalBytes({
    checkpoint_id: checkpoint?.checkpoint_id,
    ...checkpointStatement(checkpoint),
  });
}
export function checkpointDigest(checkpoint) {
  return canonicalSha256(checkpoint);
}

export function checkpointShapeReasons(checkpoint) {
  if (!isObject(checkpoint)) return ['CHECKPOINT_INVALID'];
  const reasons = [];
  add(reasons, 'CHECKPOINT_FIELDS_INVALID', !exactObject(checkpoint, CHECKPOINT_FIELDS));
  add(reasons, 'CHECKPOINT_PROFILE_INVALID', checkpoint.profile_id !== CHECKPOINT_PROFILE_ID);
  add(reasons, 'CHECKPOINT_SCHEMA_VERSION_INVALID', checkpoint.schema_version !== SCHEMA_VERSION);
  add(reasons, 'CANONICAL_PROFILE_MISMATCH', checkpoint.canonical_profile !== CANONICAL_PROFILE);
  add(reasons, 'CHECKPOINT_LOG_ID_INVALID', !nonEmptyString(checkpoint.log_id));
  add(reasons, 'CHECKPOINT_TREE_SIZE_INVALID', !positiveInteger(checkpoint.tree_size));
  add(reasons, 'CHECKPOINT_ROOT_HASH_INVALID', !hex64(checkpoint.root_hash));
  add(reasons, 'CHECKPOINT_ISSUED_AT_INVALID', !timestamp(checkpoint.issued_at_ms));
  add(reasons, 'CHECKPOINT_NOT_BEFORE_INVALID', !timestamp(checkpoint.not_before_ms));
  add(reasons, 'CHECKPOINT_NOT_AFTER_INVALID', !timestamp(checkpoint.not_after_ms));
  add(reasons, 'CHECKPOINT_ISSUER_INVALID', !nonEmptyString(checkpoint.issuer_id));
  add(reasons, 'CHECKPOINT_AUTHORITY_ID_INVALID', !nonEmptyString(checkpoint.log_authority_id));
  add(reasons, 'CHECKPOINT_KEY_ID_INVALID', !nonEmptyString(checkpoint.log_key_id));
  add(reasons, 'CHECKPOINT_ALGORITHM_INVALID', !nonEmptyString(checkpoint.signature_algorithm));
  const signature = decodeBase64(checkpoint.signature);
  add(
    reasons,
    'CHECKPOINT_SIGNATURE_ENCODING_INVALID',
    signature === null || signature.length !== SIGNATURE_BYTES,
  );
  let expectedId = null;
  try { expectedId = computeCheckpointId(checkpoint); } catch { expectedId = null; }
  add(reasons, 'CHECKPOINT_ID_INVALID', checkpoint.checkpoint_id !== expectedId);
  return reasons;
}

export function authorityShapeReasons(authority) {
  if (!isObject(authority)) return ['LOG_AUTHORITY_INVALID'];
  const reasons = [];
  add(reasons, 'LOG_AUTHORITY_FIELDS_INVALID', !exactObject(authority, AUTHORITY_FIELDS));
  add(reasons, 'LOG_AUTHORITY_PROFILE_INVALID', authority.profile_id !== LOG_AUTHORITY_PROFILE_ID);
  add(reasons, 'LOG_AUTHORITY_ID_INVALID', !nonEmptyString(authority.log_authority_id));
  const allowed = authority.allowed_algorithms;
  add(
    reasons,
    'LOG_ALLOWED_ALGORITHMS_INVALID',
    !Array.isArray(allowed)
      || allowed.length === 0
      || !allowed.every(nonEmptyString)
      || new Set(allowed).size !== allowed.length,
  );
  const keys = authority.keys;
  if (!Array.isArray(keys) || keys.length === 0) {
    add(reasons, 'LOG_KEYS_INVALID', true);
    return reasons;
  }
  keys.forEach((key, index) => {
    if (!isObject(key)) {
      add(reasons, `LOG_KEY_INVALID:${index}`, true);
      return;
    }
    add(reasons, `LOG_KEY_FIELDS_INVALID:${index}`, !exactObject(key, KEY_FIELDS));
    const specs = {
      log_key_id: nonEmptyString,
      issuer_id: nonEmptyString,
      algorithm: nonEmptyString,
      public_key_base64: nonEmptyString,
      not_before_ms: timestamp,
      not_after_ms: timestamp,
      revoked: (value) => typeof value === 'boolean',
    };
    for (const [field, predicate] of Object.entries(specs)) {
      if (!(field in key) || !predicate(key[field])) {
        add(reasons, `LOG_KEY_SCHEMA_INVALID:${index}.${field}`, true);
      }
    }
  });
  return reasons;
}

export function verifyCheckpoint(checkpoint, authority, nowMs) {
  const checkpointReasons = checkpointShapeReasons(checkpoint);
  const authorityReasons = authorityShapeReasons(authority);
  const reasons = [...checkpointReasons, ...authorityReasons];
  const checkpointIntegrityValid = checkpointReasons.length === 0;
  if (!isObject(checkpoint) || !isObject(authority)) {
    return [checkpointIntegrityValid, false, false, false, reasons];
  }

  add(
    reasons,
    'LOG_AUTHORITY_ID_MISMATCH',
    authority.log_authority_id !== checkpoint.log_authority_id,
  );
  const allowed = authority.allowed_algorithms;
  const algorithm = checkpoint.signature_algorithm;
  const algorithmAllowed = algorithm === ED25519
    && Array.isArray(allowed)
    && allowed.includes(ED25519);
  add(reasons, 'LOG_ALGORITHM_NOT_ALLOWED', !algorithmAllowed);

  const keys = authority.keys;
  const matches = Array.isArray(keys)
    ? keys.filter(
      (key) => isObject(key) && key.log_key_id === checkpoint.log_key_id,
    )
    : [];
  add(reasons, 'LOG_KEY_NOT_TRUSTED', matches.length === 0);
  add(reasons, 'LOG_KEY_AMBIGUOUS', matches.length > 1);

  let signatureValid = false;
  let authorityValid = false;
  const key = matches.length === 1 ? matches[0] : null;
  if (key) {
    const publicKey = decodeBase64(key.public_key_base64);
    const signature = decodeBase64(checkpoint.signature);
    const keyMaterialValid = publicKey !== null
      && publicKey.length === PUBLIC_KEY_BYTES;
    const signatureMaterialValid = signature !== null
      && signature.length === SIGNATURE_BYTES;
    add(reasons, 'LOG_KEY_MATERIAL_INVALID', !keyMaterialValid);
    add(reasons, 'LOG_KEY_ISSUER_MISMATCH', key.issuer_id !== checkpoint.issuer_id);
    add(reasons, 'LOG_KEY_ALGORITHM_MISMATCH', key.algorithm !== algorithm);
    add(reasons, 'LOG_KEY_REVOKED', key.revoked === true);

    const keyIntervalValid = timestamp(key.not_before_ms)
      && timestamp(key.not_after_ms)
      && key.not_after_ms >= key.not_before_ms;
    add(reasons, 'LOG_KEY_VALIDITY_INVALID', !keyIntervalValid);
    add(reasons, 'LOG_KEY_NOT_YET_VALID', keyIntervalValid && nowMs < key.not_before_ms);
    add(reasons, 'LOG_KEY_EXPIRED', keyIntervalValid && nowMs > key.not_after_ms);

    if (
      algorithm === ED25519
      && key.algorithm === ED25519
      && keyMaterialValid
      && signatureMaterialValid
    ) {
      try {
        const spki = Buffer.concat([
          Buffer.from('302a300506032b6570032100', 'hex'),
          publicKey,
        ]);
        const publicKeyObject = crypto.createPublicKey({
          key: spki,
          format: 'der',
          type: 'spki',
        });
        signatureValid = crypto.verify(
          null,
          signedCheckpointPayload(checkpoint),
          publicKeyObject,
          signature,
        );
      } catch {
        signatureValid = false;
      }
      add(reasons, 'CHECKPOINT_SIGNATURE_INVALID', !signatureValid);
    }

    authorityValid = authorityReasons.length === 0
      && authority.profile_id === LOG_AUTHORITY_PROFILE_ID
      && authority.log_authority_id === checkpoint.log_authority_id
      && algorithmAllowed
      && keyMaterialValid
      && key.issuer_id === checkpoint.issuer_id
      && key.algorithm === algorithm
      && key.revoked === false
      && keyIntervalValid
      && key.not_before_ms <= nowMs
      && nowMs <= key.not_after_ms;
  }

  const issuedAt = checkpoint.issued_at_ms;
  const notBefore = checkpoint.not_before_ms;
  const notAfter = checkpoint.not_after_ms;
  const validityIntervalValid = timestamp(notBefore)
    && timestamp(notAfter)
    && notAfter >= notBefore;
  const freshnessValid = validityIntervalValid
    && timestamp(issuedAt)
    && issuedAt <= nowMs
    && notBefore <= nowMs
    && nowMs <= notAfter;
  add(reasons, 'CHECKPOINT_VALIDITY_INVALID', !validityIntervalValid);
  add(reasons, 'CHECKPOINT_NOT_YET_VALID', validityIntervalValid && nowMs < notBefore);
  add(reasons, 'CHECKPOINT_EXPIRED', validityIntervalValid && nowMs > notAfter);
  add(reasons, 'CHECKPOINT_ISSUED_IN_FUTURE', timestamp(issuedAt) && issuedAt > nowMs);

  return [
    checkpointIntegrityValid,
    signatureValid,
    authorityValid,
    freshnessValid,
    reasons,
  ];
}

export function targetValid(target) {
  return exactObject(target, TARGET_FIELDS)
    && nonEmptyString(target.log_id)
    && nonEmptyString(target.trust_root_id)
    && positiveInteger(target.snapshot_generation)
    && hex64(target.snapshot_digest);
}
export function entryValid(entry) {
  return exactObject(entry, ENTRY_FIELDS)
    && entry.profile_id === ENTRY_PROFILE_ID
    && entry.canonical_profile === CANONICAL_PROFILE
    && entry.entry_type === 'trust-root-snapshot'
    && nonEmptyString(entry.log_id)
    && nonEmptyString(entry.trust_root_id)
    && positiveInteger(entry.snapshot_generation)
    && hex64(entry.snapshot_digest);
}

export function verifyTransparencyLog(inputBundle, nowMs) {
  let bundle;
  try { bundle = structuredClone(inputBundle); } catch {
    return invalidResult(['INPUT_SNAPSHOT_FAILED']);
  }
  if (!isObject(bundle)) {
    return invalidResult(['TRANSPARENCY_BUNDLE_INVALID']);
  }
  const localValid = bundle.local_witnessed_freshness_valid === true;
  if (!timestamp(nowMs)) {
    return invalidResult(['NOW_MS_INVALID'], localValid);
  }

  const reasons = [];
  const bundleFieldsValid = exactObject(bundle, BUNDLE_FIELDS);
  add(reasons, 'TRANSPARENCY_BUNDLE_FIELDS_INVALID', !bundleFieldsValid);
  add(reasons, 'LOCAL_WITNESSED_FRESHNESS_INVALID', !localValid);

  const target = bundle.target;
  const entry = bundle.entry;
  const targetIsValid = targetValid(target);
  const entryShapeValid = entryValid(entry);
  if (!isObject(target) || !isObject(entry)) {
    add(reasons, 'ENTRY_OR_TARGET_INVALID', true);
  } else {
    add(reasons, 'TARGET_FIELDS_INVALID', !exactObject(target, TARGET_FIELDS));
    add(
      reasons,
      'TARGET_SCHEMA_INVALID',
      !targetIsValid && exactObject(target, TARGET_FIELDS),
    );
    add(reasons, 'ENTRY_FIELDS_INVALID', !exactObject(entry, ENTRY_FIELDS));
    add(reasons, 'ENTRY_PROFILE_INVALID', entry.profile_id !== ENTRY_PROFILE_ID);
    add(
      reasons,
      'ENTRY_CANONICAL_PROFILE_INVALID',
      entry.canonical_profile !== CANONICAL_PROFILE,
    );
    add(reasons, 'ENTRY_TYPE_INVALID', entry.entry_type !== 'trust-root-snapshot');
  }

  let entryIntegrityValid = targetIsValid && entryShapeValid;
  if (isObject(target) && isObject(entry)) {
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
  }

  let leafHash = null;
  if (isObject(entry)) {
    try { leafHash = merkleLeafHash(entry); } catch {
      add(reasons, 'ENTRY_CANONICALIZATION_FAILED', true);
      entryIntegrityValid = false;
    }
  }

  const checkpoint = bundle.checkpoint;
  const authority = bundle.log_authority;
  const [
    checkpointIntegrityValid,
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
  } else {
    const fieldsValid = exactObject(
      verifierCheckpoint,
      VERIFIER_CHECKPOINT_FIELDS,
    );
    add(reasons, 'LOG_VERIFIER_CHECKPOINT_FIELDS_INVALID', !fieldsValid);
    const profileValid = verifierCheckpoint.profile_id
      === VERIFIER_CHECKPOINT_PROFILE_ID;
    add(reasons, 'LOG_VERIFIER_CHECKPOINT_INVALID', !profileValid);
    const checkpointTime = verifierCheckpoint.checkpointed_at_ms;
    if (!timestamp(checkpointTime)) {
      add(reasons, 'LOG_VERIFIER_CHECKPOINT_TIME_INVALID', true);
      consistencyValid = false;
    } else if (checkpointTime > nowMs) {
      add(reasons, 'LOG_VERIFIER_CHECKPOINT_FROM_FUTURE', true);
      consistencyValid = false;
    }

    if (!fieldsValid || !profileValid) consistencyValid = false;
    if (
      !isObject(checkpoint)
      || verifierCheckpoint.log_id !== checkpoint.log_id
    ) {
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
        } else if (!(Array.isArray(bundle.consistency_path)
          && bundle.consistency_path.length === 0)) {
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
  let peerEvidenceValid = Array.isArray(peers);
  add(reasons, 'PEER_CHECKPOINTS_INVALID', !peerEvidenceValid);
  const seenPeerIds = new Set();
  if (Array.isArray(peers) && isObject(checkpoint)) {
    peers.forEach((peer, index) => {
      const [
        peerIntegrity,
        peerSignature,
        peerAuthority,
        peerFreshness,
      ] = verifyCheckpoint(peer, authority, nowMs);
      const peerId = isObject(peer) ? peer.checkpoint_id : null;
      const duplicate = typeof peerId === 'string'
        && seenPeerIds.has(peerId);
      if (typeof peerId === 'string') seenPeerIds.add(peerId);
      add(reasons, 'DUPLICATE_PEER_CHECKPOINT', duplicate);
      const peerValid = peerIntegrity
        && peerSignature
        && peerAuthority
        && peerFreshness
        && isObject(peer)
        && peer.log_id === checkpoint.log_id
        && !duplicate;
      if (!peerValid) {
        add(reasons, `PEER_CHECKPOINT_INVALID:${index}`, true);
        peerEvidenceValid = false;
        return;
      }
      if (
        peer.tree_size === checkpoint.tree_size
        && peer.root_hash !== checkpoint.root_hash
      ) {
        add(reasons, 'LOG_EQUIVOCATION_DETECTED', true);
        equivocationDetected = true;
      }
    });
  }

  const viewConsistencyValid = peerEvidenceValid && !equivocationDetected;
  const valid = bundleFieldsValid
    && localValid
    && entryIntegrityValid
    && checkpointIntegrityValid
    && checkpointSignatureValid
    && checkpointAuthorityValid
    && checkpointFreshnessValid
    && inclusionValid
    && consistencyValid
    && viewConsistencyValid
    && reasons.length === 0;

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
    accepted_tree_size: valid ? checkpoint.tree_size : null,
    accepted_root_hash: valid ? checkpoint.root_hash : null,
    reason_codes: reasons,
  };
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const inputPath = process.argv[2];
  if (!inputPath) {
    process.stderr.write(
      'usage: node reference/transparency-log-v0.14.mjs <bundle-or-fixture.json> [now_ms]\n',
    );
    process.exit(2);
  }
  const input = strictParse(fs.readFileSync(inputPath, 'utf8'));
  const bundle = isObject(input) && isObject(input.base_bundle)
    ? input.base_bundle
    : input;
  const nowMs = isObject(input) && timestamp(input.base_now_ms)
    ? input.base_now_ms
    : Number(process.argv[3]);
  const result = verifyTransparencyLog(bundle, nowMs);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (!result.valid) process.exitCode = 1;
}
