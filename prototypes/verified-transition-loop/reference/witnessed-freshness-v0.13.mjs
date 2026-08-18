#!/usr/bin/env node

import fs from 'node:fs';
import crypto from 'node:crypto';
import {CANONICAL_PROFILE, canonicalBytes, canonicalSha256, strictParse} from './canonical-runtime-v0.12.mjs';

const PROFILE_ID = 'vtl-witnessed-freshness-v0.13';
const FIXTURE_SCHEMA_VERSION = 'vtl.witnessed-freshness-fixture/v0.13';
const STATEMENT_PROFILE_ID = 'vtl-witness-statement/v0.13';
const STATEMENT_SCHEMA_VERSION = 'vtl.witness-statement/v0.13';
const AUTHORITY_PROFILE_ID = 'vtl-witness-authority/v0.13';
const ED25519 = 'ED25519';

function add(reasons, reason, condition) { if (condition && !reasons.includes(reason)) reasons.push(reason); }
function string(value) { return typeof value === 'string' && value.length > 0; }
function integer(value) { return Number.isSafeInteger(value); }
function positiveInteger(value) { return integer(value) && value >= 1; }
function hex64(value) { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function decodeBase64(value) {
  try {
    if (typeof value !== 'string') return null;
    const decoded = Buffer.from(value, 'base64');
    return decoded.toString('base64') === value ? decoded : null;
  } catch { return null; }
}

const STATEMENT_FIELDS = [
  'profile_id','schema_version','canonical_profile','trust_root_id','generation','snapshot_digest',
  'observed_at_ms','witness_id','witness_key_id','signature_algorithm',
];
function witnessStatement(statement) {
  const result = {};
  for (const field of STATEMENT_FIELDS) result[field] = statement?.[field];
  return result;
}
function computeWitnessStatementId(statement) { return `witness_${canonicalSha256(witnessStatement(statement)).slice(0,24)}`; }
function signedWitnessPayload(statement) { return canonicalBytes({statement_id: statement?.statement_id, ...witnessStatement(statement)}); }

function validateStatement(statement) {
  if (!object(statement)) return ['WITNESS_STATEMENT_INVALID'];
  const reasons = [];
  const required = {
    statement_id:string, profile_id:string, schema_version:string, canonical_profile:string,
    trust_root_id:string, generation:positiveInteger, snapshot_digest:hex64, observed_at_ms:integer,
    witness_id:string, witness_key_id:string, signature_algorithm:string, signature:string,
  };
  for (const [field,predicate] of Object.entries(required)) {
    if (!(field in statement) || !predicate(statement[field])) add(reasons, `WITNESS_STATEMENT_SCHEMA_INVALID:${field}`, true);
  }
  return reasons;
}
function validateAuthority(authority) {
  if (!object(authority)) return ['WITNESS_AUTHORITY_INVALID'];
  const reasons = [];
  add(reasons,'WITNESS_AUTHORITY_PROFILE_INVALID',authority.profile_id !== AUTHORITY_PROFILE_ID);
  add(reasons,'WITNESS_QUORUM_CONFIG_INVALID',!positiveInteger(authority.quorum));
  add(reasons,'WITNESS_MAX_AGE_INVALID',!positiveInteger(authority.max_statement_age_ms));
  add(reasons,'WITNESS_ALLOWED_ALGORITHMS_INVALID',!Array.isArray(authority.allowed_algorithms) || authority.allowed_algorithms.length === 0 || !authority.allowed_algorithms.every(string));
  if (!Array.isArray(authority.keys) || authority.keys.length === 0) {
    add(reasons,'WITNESS_KEYS_INVALID',true);
    return reasons;
  }
  authority.keys.forEach((key,index) => {
    if (!object(key)) { add(reasons,`WITNESS_KEY_INVALID:${index}`,true); return; }
    const specs = {
      witness_id:string,witness_key_id:string,algorithm:string,public_key_base64:string,
      not_before_ms:integer,not_after_ms:integer,revoked:(value)=>typeof value === 'boolean',
    };
    for (const [field,predicate] of Object.entries(specs)) {
      if (!(field in key) || !predicate(key[field])) add(reasons,`WITNESS_KEY_SCHEMA_INVALID:${index}.${field}`,true);
    }
  });
  return reasons;
}

function verifyWitnessedFreshness({snapshotView,localSnapshotValid,witnessStatements,witnessAuthority,nowMs}) {
  const reasons = [];
  add(reasons,'LOCAL_SNAPSHOT_INVALID',localSnapshotValid !== true);
  add(reasons,'NOW_MS_INVALID',!integer(nowMs));
  const viewValid = object(snapshotView) && string(snapshotView.trust_root_id) && positiveInteger(snapshotView.generation) && hex64(snapshotView.snapshot_digest);
  add(reasons,'SNAPSHOT_VIEW_INVALID',!viewValid);
  const authorityReasons = validateAuthority(witnessAuthority);
  for (const reason of authorityReasons) add(reasons,reason,true);
  if (!Array.isArray(witnessStatements) || witnessStatements.length === 0) add(reasons,'WITNESS_STATEMENTS_INVALID',true);
  if (reasons.length > 0 && (!viewValid || authorityReasons.length > 0 || !integer(nowMs))) {
    return {valid:false,local_snapshot_valid:localSnapshotValid===true,witness_statement_integrity_valid:false,witness_signature_valid:false,witness_authority_valid:false,witness_freshness_valid:false,witness_quorum_valid:false,view_consistency_valid:false,equivocation_detected:false,accepted_witness_ids:[],reason_codes:reasons};
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
    for (const reason of shapeReasons) add(reasons,reason,true);
    if (shapeReasons.length > 0) {
      statementIntegrityValid=false; allSignatureValid=false; allAuthorityValid=false; allFresh=false; allViewConsistent=false; continue;
    }
    const profileOk = statement.profile_id === STATEMENT_PROFILE_ID && statement.schema_version === STATEMENT_SCHEMA_VERSION;
    const canonicalOk = statement.canonical_profile === CANONICAL_PROFILE;
    const idOk = statement.statement_id === computeWitnessStatementId(statement);
    add(reasons,'WITNESS_PROFILE_MISMATCH',!profileOk);
    add(reasons,'WITNESS_CANONICAL_PROFILE_MISMATCH',!canonicalOk);
    add(reasons,'WITNESS_STATEMENT_ID_INVALID',!idOk);
    const integrityOk = profileOk && canonicalOk && idOk;
    statementIntegrityValid = statementIntegrityValid && integrityOk;

    const witnessId = statement.witness_id;
    if (seenWitnessIds.has(witnessId)) { add(reasons,'DUPLICATE_WITNESS_ID',true); allViewConsistent=false; }
    seenWitnessIds.add(witnessId);

    const matching = keys.filter((key)=>object(key) && key.witness_id===witnessId && key.witness_key_id===statement.witness_key_id);
    add(reasons,'WITNESS_NOT_TRUSTED',matching.length===0);
    add(reasons,'WITNESS_KEY_AMBIGUOUS',matching.length>1);
    const key = matching.length===1 ? matching[0] : null;
    let signatureOk = false;
    let authorityOk = key !== null;
    if (key) {
      const algorithmOk = statement.signature_algorithm===ED25519 && key.algorithm===ED25519 && allowed.includes(ED25519);
      add(reasons,'WITNESS_ALGORITHM_NOT_ALLOWED',!algorithmOk);
      const keyIntervalOk = integer(key.not_before_ms) && integer(key.not_after_ms) && key.not_after_ms >= key.not_before_ms;
      add(reasons,'WITNESS_KEY_VALIDITY_INVALID',!keyIntervalOk);
      add(reasons,'WITNESS_KEY_REVOKED',key.revoked===true);
      const keyCurrent = keyIntervalOk && key.not_before_ms <= nowMs && nowMs <= key.not_after_ms;
      add(reasons,'WITNESS_KEY_NOT_CURRENT',keyIntervalOk && !keyCurrent);
      const publicKey = decodeBase64(key.public_key_base64);
      const signature = decodeBase64(statement.signature);
      const keyMaterialOk = publicKey !== null && publicKey.length === 32;
      add(reasons,'WITNESS_KEY_MATERIAL_INVALID',!keyMaterialOk);
      if (algorithmOk && keyMaterialOk && signature !== null) {
        try {
          const spki = Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),publicKey]);
          const keyObject = crypto.createPublicKey({key:spki,format:'der',type:'spki'});
          signatureOk = crypto.verify(null,signedWitnessPayload(statement),keyObject,signature);
        } catch { signatureOk=false; }
      }
      add(reasons,'WITNESS_SIGNATURE_INVALID',!signatureOk && algorithmOk && keyMaterialOk);
      authorityOk = authorityOk && algorithmOk && keyIntervalOk && keyCurrent && key.revoked===false && keyMaterialOk;
    }
    allSignatureValid = allSignatureValid && signatureOk;
    allAuthorityValid = allAuthorityValid && authorityOk;

    const fromFuture = statement.observed_at_ms > nowMs;
    const stale = !fromFuture && nowMs - statement.observed_at_ms > maxAge;
    add(reasons,'WITNESS_STATEMENT_FROM_FUTURE',fromFuture);
    add(reasons,'WITNESS_STATEMENT_STALE',stale);
    const freshOk = !fromFuture && !stale;
    allFresh = allFresh && freshOk;

    const rootMatch = statement.trust_root_id === snapshotView.trust_root_id;
    const generationMatch = statement.generation === snapshotView.generation;
    const digestMatch = statement.snapshot_digest === snapshotView.snapshot_digest;
    add(reasons,'WITNESS_TRUST_ROOT_MISMATCH',!rootMatch);
    add(reasons,'WITNESS_GENERATION_MISMATCH',!generationMatch);
    add(reasons,'WITNESS_SNAPSHOT_DIGEST_MISMATCH',rootMatch && generationMatch && !digestMatch);
    const exactView = rootMatch && generationMatch && digestMatch;
    if (signatureOk && authorityOk && freshOk && rootMatch && generationMatch && !digestMatch) {
      equivocationDetected=true;
      add(reasons,'EQUIVOCATION_DETECTED',true);
    }
    allViewConsistent = allViewConsistent && exactView;
    if (integrityOk && signatureOk && authorityOk && freshOk && exactView) accepted.add(witnessId);
  }

  const quorumValid = accepted.size >= witnessAuthority.quorum;
  add(reasons,'WITNESS_QUORUM_NOT_MET',!quorumValid);
  const viewConsistencyValid = allViewConsistent && !equivocationDetected;
  const valid = localSnapshotValid===true && statementIntegrityValid && allSignatureValid && allAuthorityValid && allFresh && quorumValid && viewConsistencyValid && !equivocationDetected && reasons.length===0;
  return {valid,local_snapshot_valid:localSnapshotValid===true,witness_statement_integrity_valid:statementIntegrityValid,witness_signature_valid:allSignatureValid,witness_authority_valid:allAuthorityValid,witness_freshness_valid:allFresh,witness_quorum_valid:quorumValid,view_consistency_valid:viewConsistencyValid,equivocation_detected:equivocationDetected,accepted_witness_ids:[...accepted].sort(),reason_codes:reasons};
}

function setPath(document,path,value) {
  const parts=path.split('.'); let cursor=document;
  for (const part of parts.slice(0,-1)) cursor=Array.isArray(cursor)?cursor[Number(part)]:cursor[part];
  const last=parts.at(-1); if (Array.isArray(cursor)) cursor[Number(last)]=structuredClone(value); else cursor[last]=structuredClone(value);
}
function runFixture(fixture) {
  const cases=fixture.cases.map((testCase)=>{
    const authority=structuredClone(fixture.witness_authority);
    const statements=testCase.statement_refs.map((ref)=>structuredClone(fixture.statements[ref]));
    for (const mutation of testCase.authority_mutations ?? []) setPath(authority,mutation.path,mutation.value);
    for (const mutation of testCase.statement_mutations ?? []) setPath(statements[mutation.index],mutation.path,mutation.value);
    const actual=verifyWitnessedFreshness({snapshotView:structuredClone(fixture.snapshot_view),localSnapshotValid:testCase.local_snapshot_valid ?? fixture.local_snapshot_valid,witnessStatements:statements,witnessAuthority:authority,nowMs:fixture.base_now_ms});
    const expected=testCase.expected;
    const passed=actual.valid===expected.valid && canonicalSha256(actual.reason_codes)===canonicalSha256(expected.reason_codes);
    return {id:testCase.id,actual,expected,passed};
  });
  const passed=cases.filter((item)=>item.passed).length;
  return {profile_id:PROFILE_ID,schema_version:FIXTURE_SCHEMA_VERSION,canonical_profile:CANONICAL_PROFILE,cases,summary:{total:cases.length,passed,failed:cases.length-passed,all_passed:passed===cases.length}};
}

const fixturePath=process.argv[2];
if (!fixturePath) { console.error('usage: node reference/witnessed-freshness-v0.13.mjs <fixture.json>'); process.exit(2); }
const fixture=strictParse(fs.readFileSync(fixturePath,'utf8'));
const result=runFixture(fixture);
console.log(JSON.stringify(result,null,2));
if (!result.summary.all_passed) process.exitCode=1;
