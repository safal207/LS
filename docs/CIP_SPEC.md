# CIP — Cognitive Interlink Protocol (Web4)

## 0. Purpose and scope
CIP is a protocol for **local cognitive agents** to exchange **state, knowledge, and decisions** without centralized coordination. The protocol focuses on:

- **State-aware communication** (presence/load signals)
- **Trust and identity** (per-peer trust states)
- **Knowledge validation** (anti-hallucination safeguards)
- **Causal memory exchange** (decision provenance)

This document defines the **wire-level message envelope**, **message types**, **handshake**, and a **trust-state FSM**. It also clarifies the **split between Rust (transport) and Python (cognitive logic)**.

---

## 1. Layered architecture

```
Level 0 — Transport (Rust)
Level 1 — Identity & Trust (Python)
Level 2 — Cognitive State Exchange (Python)
Level 3 — Knowledge & Decision Exchange (Python)
```

### 1.1 Rust vs Python responsibilities

| Component | Python | Rust |
|---|---|---|
| Transport (p2p, crypto, channels) |  | ✅ |
| Kernel telemetry |  | ✅ |
| CIP message parsing | ✅ |  |
| Identity & trust (LTP-Peer) | ✅ |  |
| Presence (LPI) | ✅ |  |
| Load (LRI) | ✅ |  |
| Decision memory (DMP) | ✅ |  |
| Causal memory | ✅ |  |
| Knowledge exchange | ✅ |  |
| Anti-hallucination logic | ✅ |  |
| Identity management | ✅ |  |
| Mesh networking |  | ✅ |

---

## 2. Message envelope (CIP/1.0)
All Level 2/3 messages use a shared envelope. The envelope is **signable** and **hashable** for integrity checks.

### 2.1 Envelope JSON (normative)

```json
{
  "cip": "1.0",
  "msg_id": "uuid",
  "type": "HELLO | INTENT | FACT_PROPOSE | FACT_CHALLENGE | FACT_CONFIRM | FACT_REJECT | DECISION_SHARE | STATE_UPDATE",
  "timestamp": "RFC3339",
  "sender": {
    "agent_id": "string",
    "fingerprint": "hex",
    "capabilities": ["string"],
    "pubkey": "base64"
  },
  "receiver": {
    "agent_id": "string",
    "fingerprint": "hex"
  },
  "trust": {
    "sender_view": "untrusted | probing | trusted | blacklisted",
    "receiver_view": "unknown | untrusted | probing | trusted | blacklisted"
  },
  "state": {
    "presence": "focused | diffuse | overloaded | engaged",
    "lri": 0,
    "kernel_signals": ["string"],
    "intent": "string"
  },
  "payload": {},
  "sign": {
    "algo": "ed25519",
    "signature": "base64"
  }
}
```

### 2.2 Envelope field notes
- `msg_id`: UUID v4, unique per message.
- `timestamp`: UTC RFC3339.
- `lri`: **0–100** normalized load index.
- `kernel_signals`: critical local alerts (e.g., overload, degraded memory).
- `intent`: optional high-level purpose for the message.
- `sign`: signature over canonical JSON form of the envelope (excluding `sign`).

---

## 3. Message types and payloads

### 3.1 HELLO (connection establishment)
```json
"payload": {
  "protocols": ["cip/1.0"],
  "capabilities": ["state_exchange", "knowledge_exchange", "dmp_trace"],
  "session_nonce": "base64",
  "challenge": "base64",
  "features": {
    "supports_mesh": true,
    "supports_multiplex": true
  }
}
```

### 3.2 INTENT (purpose of contact)
```json
"payload": {
  "goal": "verify_knowledge | ask | learn | propose_solution | test_hypothesis",
  "topic": "string",
  "priority": "low | normal | high",
  "context": "string"
}
```

### 3.3 FACT_PROPOSE (knowledge offer)
```json
"payload": {
  "fact": {
    "statement": "string",
    "domain": "string",
    "confidence": 0.0,
    "sources": ["string"],
    "context": "string"
  },
  "dmp_trace": {
    "decision_id": "uuid",
    "steps": ["string"],
    "counterfactuals": ["string"],
    "evidence": ["string"]
  },
  "causal_links": ["string"]
}
```

### 3.4 FACT_CHALLENGE (conflict or non-confirmation)
```json
"payload": {
  "fact_ref": "msg_id",
  "reason": "conflict | insufficient_evidence | cannot_verify",
  "notes": "string"
}
```

### 3.5 FACT_CONFIRM / FACT_REJECT (resolution)
```json
"payload": {
  "fact_ref": "msg_id",
  "decision": "confirm | reject",
  "confidence": 0.0,
  "notes": "string"
}
```

### 3.6 DECISION_SHARE (experience exchange)
```json
"payload": {
  "decision": {
    "choice": "string",
    "outcome": "string",
    "context": "string"
  },
  "dmp_trace": {
    "decision_id": "uuid",
    "steps": ["string"],
    "evidence": ["string"]
  },
  "retrospective": "string"
}
```

### 3.7 STATE_UPDATE (presence and load)
```json
"payload": {
  "presence": "focused | diffuse | overloaded | engaged",
  "lri": 0,
  "ltppeerstate": "untrusted | probing | trusted | blacklisted",
  "kernel_signals": ["string"],
  "intent": "string"
}
```

---

## 4. Handshake (minimal secure handshake)

### 4.1 Steps
1. **HELLO →** Agent A sends `HELLO` with `session_nonce` and `challenge`.
2. **HELLO ←** Agent B responds with `HELLO`, includes its own `session_nonce` and response to A’s challenge (signed).
3. **VERIFY** Both agents verify:
   - signature validity
   - fingerprint matches pubkey
   - replay protection (nonce + timestamp)
4. **TRUST GATE** If valid, move trust to `probing`.
5. **STATE_UPDATE** Exchange first state signal with LPI/LRI.
6. **INTENT** Agent A declares intent; Agent B accepts or defers.

### 4.2 Handshake acceptance rules
- If signature invalid → **drop** and mark peer `untrusted`.
- If fingerprint mismatch → **drop** and mark peer `blacklisted`.
- If peer overloads (LPI=overloaded) → **defer**.

---

## 5. Trust FSM (LTP-Peer)

### 5.1 States
- `untrusted`
- `probing`
- `trusted`
- `blacklisted`

### 5.2 Transitions (summary)

| From | Event | To | Notes |
|---|---|---|---|
| untrusted | valid handshake | probing | minimal interaction only |
| probing | verified knowledge (>=2 trusted confirmations) | trusted | stable exchange allowed |
| probing | conflict or repeated unverifiable | untrusted | cooldown |
| trusted | severe conflict / malicious evidence | blacklisted | long-term deny |
| trusted | temporary anomaly | probing | re-verify |
| blacklisted | manual override | probing | human authority |

---

## 6. Anti-hallucination policy (normative)
An agent **must not accept** a knowledge claim unless:

1. It matches or is reconcilable with **causal memory**.
2. It is consistent with **DMP-trace** or decision provenance.
3. It is confirmed by **≥2 trusted peers**.
4. It passes **trust gating** (peer ≠ untrusted/blacklisted).
5. It respects local state constraints (LPI/LRI are not overloaded).

### 6.1 Resolution rules
- **2+ trusted confirmations → accept**
- **Any trusted conflict → mark as disputed**
- **Untrusted source → reject**

---

## 7. Security and integrity
- **Sign every message** using Ed25519.
- **Canonical JSON** required for signing.
- **Nonce + timestamp** protect against replay.
- **Multiplexed channels** on Rust transport allow concurrent state/knowledge flows.

---

## 8. Compliance checklist (for implementers)
- [ ] Envelope + signature validation
- [ ] Trust FSM transitions implemented
- [ ] LPI/LRI signals used for pacing
- [ ] DMP-trace and causal memory checks
- [ ] ≥2 trusted confirmations for knowledge acceptance
- [ ] Reject on fingerprint/pubkey mismatch

---

## 9. Next extension points
- Formal JSON Schema files (`.schema.json`)
- Binary encoding variant (CBOR)
- Mesh routing hints
- Cross-domain policy negotiation
