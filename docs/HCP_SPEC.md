# HCP — Human Connection Protocol (Web4)

## 0. Purpose and scope
HCP defines how **humans connect through cognitive agents** with clarity, consent, and emotional safety. It mirrors CIP but centers on **human state**, **intent**, and **social trust** so agents can coordinate without misrepresenting people.

---

## 1. Core principles
- **Consent-first:** human intent and boundaries override agent objectives.
- **State-aware mediation:** emotional load and clarity guide pacing.
- **Trust as a social signal:** trust is dynamic and contextual.
- **Provenance:** decisions and agreements capture context, not just outcomes.

---

## 2. Human state model
Each HCP message carries a lightweight human-state vector:

| Field | Type | Meaning |
|---|---|---|
| `presence` | enum | focused / diffuse / overloaded / engaged |
| `affect` | enum | calm / tense / anxious / energized / neutral |
| `clarity` | int | 0–100 self-reported clarity |
| `pressure` | int | 0–100 perceived pressure |
| `intent` | string | human-stated purpose |
| `consent` | enum | granted / limited / revoked |

---

## 3. Envelope (HCP/1.0)
HCP reuses the CIP envelope with a `type` namespace and a `human` block in `state`.

```json
{
  "hcp": "1.0",
  "msg_id": "uuid",
  "type": "HCP_HELLO | HCP_INTENT | HCP_CONTEXT | HCP_DECISION | HCP_FEEDBACK | HCP_STATE_UPDATE",
  "timestamp": "RFC3339",
  "sender": { "agent_id": "string", "fingerprint": "hex" },
  "receiver": { "agent_id": "string", "fingerprint": "hex" },
  "state": {
    "human": {
      "presence": "focused | diffuse | overloaded | engaged",
      "affect": "calm | tense | anxious | energized | neutral",
      "clarity": 0,
      "pressure": 0,
      "intent": "string",
      "consent": "granted | limited | revoked"
    }
  },
  "payload": {},
  "sign": { "algo": "ed25519", "signature": "base64" }
}
```

---

## 4. Message types

### 4.1 HCP_HELLO
Establishes the human context boundary and consent.
```json
"payload": {
  "identity": { "name": "string", "role": "string" },
  "consent_scope": ["topic:work", "topic:personal"],
  "safety_flags": ["avoid_conflict", "slow_pacing"]
}
```

### 4.2 HCP_INTENT
Declares the goal of contact.
```json
"payload": {
  "goal": "align | request | clarify | decide | resolve_conflict",
  "topic": "string",
  "priority": "low | normal | high"
}
```

### 4.3 HCP_CONTEXT
Shares context and constraints.
```json
"payload": {
  "context": "string",
  "constraints": ["time_limit", "no_legal_advice"],
  "shared_history": ["string"]
}
```

### 4.4 HCP_DECISION
Records joint decisions and rationale.
```json
"payload": {
  "decision": "string",
  "rationale": "string",
  "alternatives": ["string"],
  "follow_up": "string"
}
```

### 4.5 HCP_FEEDBACK
Captures human feedback and correction.
```json
"payload": {
  "feedback": "string",
  "corrections": ["string"],
  "satisfaction": 0
}
```

### 4.6 HCP_STATE_UPDATE
Updates human state during a conversation.
```json
"payload": {
  "presence": "focused | diffuse | overloaded | engaged",
  "affect": "calm | tense | anxious | energized | neutral",
  "clarity": 0,
  "pressure": 0,
  "consent": "granted | limited | revoked"
}
```

---

## 5. Social trust model (HCP-Trust)
States:
- `untrusted`
- `probing`
- `trusted`
- `restricted`

Transitions emphasize **human comfort** and **consent**:
- If consent revoked → `restricted`
- If repeated misunderstanding → `probing`
- If mutual validation → `trusted`

---

## 6. Safety requirements (normative)
- **Consent overrides** any automated action.
- **Pressure ≥ 80** or **clarity ≤ 30** forces the agent to slow down or defer.
- **Affect = anxious/tense** requires explicit check-ins.
- Decisions must include **rationale** and **alternatives**.

---

## 7. Extension points
- Formal JSON Schema
- Human identity verification bindings
- Cultural localization bundles
