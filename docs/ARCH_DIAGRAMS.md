# Web4 Architecture Diagrams (Mermaid)

## 1. Protocol stack
```mermaid
flowchart TB
  Human((Human)) -->|HCP| AgentA[Agent (Python Cognition)]
  AgentA -->|CIP| AgentB[Agent (Python Cognition)]
  AgentA -.->|LIP| Internet[(Open Internet)]
  AgentA -->|RTT| RustTransport[Secure Rust Transport]
  RustTransport <--> Mesh[Mesh / P2P Network]
```

## 2. CIP handshake
```mermaid
sequenceDiagram
  participant A as Agent A
  participant B as Agent B
  A->>B: HELLO (nonce, challenge)
  B->>A: HELLO (nonce, signed challenge)
  A-->>B: VERIFY (signature, fingerprint)
  A->>B: STATE_UPDATE (presence, lri)
  A->>B: INTENT (goal)
```

## 3. Trust FSM
```mermaid
stateDiagram-v2
  [*] --> untrusted
  untrusted --> probing: valid handshake
  probing --> trusted: verified knowledge
  probing --> untrusted: conflict
  trusted --> probing: anomaly
  trusted --> blacklisted: malicious evidence
  blacklisted --> probing: manual override
```

## 4. LIP deferred acceptance
```mermaid
stateDiagram-v2
  [*] --> pending
  pending --> accepted: verified
  pending --> disputed: conflict
  disputed --> accepted: resolved
  pending --> rejected: low trust
```
