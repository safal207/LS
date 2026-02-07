# Web4 Diagrams (text specification)

## 1. Web4 architecture
```
Human
  ↓ HCP
Agent (Python cognition)
  ↓ CIP
Agent (Rust transport)
  ↔ Mesh (p2p)
  ↑ LIP (internet learning)
```

## 2. CIP handshake
```
A → HELLO(session_nonce, challenge)
B → HELLO(session_nonce, signed_challenge)
A ↔ VERIFY(signature, fingerprint, replay)
A ↔ STATE_UPDATE(presence, lri)
A → INTENT(goal)
```

## 3. HCP handshake
```
Human A ↔ Agent A: consent, intent
Agent A → HCP_HELLO (consent_scope)
Agent B → HCP_HELLO (accept/limits)
Agents ↔ HCP_STATE_UPDATE
Agents ↔ HCP_INTENT
```

## 4. Trust FSM (CIP/HCP)
```
untrusted → probing → trusted
      ↘ conflict ↙
        blacklisted
```

## 5. Cognitive loop (agent)
```
Perception → State Update → Intent → Decision → DMP Trace → Exchange → Memory
```

## 6. Social loop (human)
```
Need → Intent → Consent → Decision → Feedback → Shared Memory
```
