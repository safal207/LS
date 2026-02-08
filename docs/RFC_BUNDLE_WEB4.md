# Web4 RFC Bundle

## RFC Index
- RFC-CIP-1.0 — Cognitive Interlink Protocol
- RFC-HCP-1.0 — Human Connection Protocol
- RFC-LIP-1.0 — Liminal Internet Protocol
- RFC-RTT-1.0 — Rust Transport & Trust Tunnel

---

# RFC-CIP-1.0 — Cognitive Interlink Protocol

## 1. Scope
CIP defines agent-to-agent exchange of state, knowledge, and decisions.

## 2. Envelope (normative)
All CIP messages MUST use the envelope defined in `docs/CIP_SPEC.md`.

## 3. Message types
- HELLO
- INTENT
- FACT_PROPOSE
- FACT_CHALLENGE
- FACT_CONFIRM
- FACT_REJECT
- DECISION_SHARE
- STATE_UPDATE

## 4. Handshake
Implementers MUST follow the handshake described in `docs/CIP_SPEC.md`.

## 5. Anti-hallucination
Knowledge acceptance MUST require ≥2 trusted confirmations or equivalent local causal alignment.

---

# RFC-HCP-1.0 — Human Connection Protocol

## 1. Scope
HCP defines mediated human-to-human connection through agents with consent and safety.

## 2. Envelope (normative)
All HCP messages MUST use the envelope defined in `docs/HCP_SPEC.md`.

## 3. Message types
- HCP_HELLO
- HCP_INTENT
- HCP_CONTEXT
- HCP_DECISION
- HCP_FEEDBACK
- HCP_STATE_UPDATE

## 4. Safety
Consent MUST override any automated action. Pressure and clarity MUST throttle pacing.

---

# RFC-LIP-1.0 — Liminal Internet Protocol

## 1. Scope
LIP defines safe ingestion from external sources with trust tiers and deferred acceptance.

## 2. Envelope (normative)
All LIP messages MUST use the envelope defined in `docs/LIP_SPEC.md`.

## 3. Message types
- LIP_FETCH
- LIP_EVIDENCE
- LIP_CONFLICT
- LIP_ACCEPT
- LIP_REJECT

## 4. Acceptance
Claims MUST be accepted only when trust tier is sufficient or corroborated by trusted peers.

---

# RFC-RTT-1.0 — Rust Transport & Trust Tunnel

## 1. Scope
RTT defines the Rust transport baseline for secure, multiplexed p2p communication.

## 2. Requirements
- End-to-end encryption
- Peer authentication
- Multiplexed streams
- Heartbeat + reconnect
- Replay protection

## 3. Interfaces
RTT exposes:
- `open_channel(type)`
- `send(channel, bytes)`
- `receive(channel)`
- `close_channel(channel)`

## 4. Binding
Python CIP/HCP/LIP must run over RTT channels.
