# LIP — Liminal Internet Protocol (Web4)

## 0. Purpose and scope
LIP defines how agents **learn from the open internet** without hallucination or unsafe assimilation. It provides **source trust**, **cross-agent verification**, and **deferred acceptance** rules.

---

## 1. Core objectives
- **Safe ingestion** of external information
- **Trust-weighted validation**
- **Conflict detection** and resolution
- **Deferred acceptance** until corroborated

---

## 2. Source trust model
Each source is assigned a trust tier:

- `unknown`
- `low`
- `medium`
- `high`
- `blocked`

Trust is adjusted based on:
- provenance quality
- corroboration by trusted peers
- historical accuracy

---

## 3. Envelope (LIP/1.0)
LIP reuses CIP with `lip` prefix and a `source` block.

```json
{
  "lip": "1.0",
  "msg_id": "uuid",
  "type": "LIP_FETCH | LIP_EVIDENCE | LIP_CONFLICT | LIP_ACCEPT | LIP_REJECT",
  "timestamp": "RFC3339",
  "sender": { "agent_id": "string", "fingerprint": "hex" },
  "receiver": { "agent_id": "string", "fingerprint": "hex" },
  "source": {
    "uri": "string",
    "trust_tier": "unknown | low | medium | high | blocked",
    "retrieved_at": "RFC3339"
  },
  "payload": {},
  "sign": { "algo": "ed25519", "signature": "base64" }
}
```

---

## 4. Message types

### 4.1 LIP_FETCH
Request external knowledge acquisition.
```json
"payload": {
  "query": "string",
  "constraints": ["no_personal_data", "domain:science"]
}
```

### 4.2 LIP_EVIDENCE
Return retrieved evidence.
```json
"payload": {
  "claims": ["string"],
  "evidence": ["string"],
  "confidence": 0.0,
  "extraction_notes": "string"
}
```

### 4.3 LIP_CONFLICT
Report conflicts with local knowledge.
```json
"payload": {
  "conflicts": ["string"],
  "local_refs": ["string"],
  "severity": "low | medium | high"
}
```

### 4.4 LIP_ACCEPT / LIP_REJECT
Resolution after validation.
```json
"payload": {
  "decision": "accept | reject",
  "reason": "string",
  "corroborators": ["agent_id"]
}
```

---

## 5. Anti-hallucination rules (normative)
An agent **must not accept** LIP evidence unless:

1. **Source trust tier ≥ medium** *or* verified by ≥2 trusted peers.
2. Conflicts are resolved or marked disputed.
3. Evidence includes provenance and retrieval timestamp.
4. Local cognitive state allows assimilation (not overloaded).

---

## 6. Deferred acceptance queue
Claims enter a **liminal state**:
- `pending`
- `disputed`
- `accepted`
- `rejected`

Only `accepted` claims can update causal memory.

---

## 7. Extension points
- Domain-specific trust scorers
- Citation normalization
- Fact clustering and deduplication
