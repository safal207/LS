# Architecture

```mermaid
flowchart LR
    A[AI agent proposes action] --> B[FastAPI gateway]
    B --> C[Deterministic policy floor]
    B --> D[Qwen Cloud risk reasoner]
    C --> E[Decision combiner: strictest wins]
    D --> E
    E -->|ALLOW| F[Advisory execution token]
    E -->|HUMAN_APPROVAL| G[(SQLite approval queue)]
    E -->|BLOCK| H[Evidence-backed rejection]
    G --> I[Human reviewer]
    I --> J[Approved or rejected record]
```

## Trust boundary

- Qwen provides semantic risk reasoning, not execution authority.
- Deterministic policy can only make the result stricter.
- Model failure becomes `HUMAN_APPROVAL`, never silent success.
- The MVP records approval decisions but deliberately does not execute destructive tools.
