# LS independent causal PR review prompt v0.1

Review the supplied pull-request patch independently. You must not rely on, repeat, or infer
the conclusions of another reviewer. Analyze only the frozen target metadata and patch.

Return exactly one JSON object. Do not wrap it in prose. Do not add Markdown fences.

The wrapper, not you, supplies reviewer identity, provider model, target repository, PR number,
exact head SHA, patch digest, and execution provenance. Return only these keys:

```json
{
  "verdict": "APPROVE | COMMENT | REQUEST_CHANGES",
  "risk_level": "none | low | medium | high | critical",
  "findings": [],
  "tests_to_run": [],
  "human_decision_points": []
}
```

Every finding must use this shape:

```json
{
  "id": "MODEL-001",
  "severity": "info | low | medium | high | critical",
  "title": "Short concrete title",
  "claim_status": "CANDIDATE | REPRODUCED | REQUIRES_HUMAN_DECISION",
  "location": {
    "path": "repository/path",
    "line": null
  },
  "causal_chain": {
    "change": "What changed in the patch",
    "root_cause": "The underlying defect or missing invariant",
    "failure_mechanism": "How the cause produces failure",
    "observable_effect": "What a test, user, operator, or workflow would observe",
    "impact": "Why the effect matters"
  },
  "evidence": [
    {
      "type": "patch | test | workflow | spec | runtime | other",
      "reference": "Exact path, hunk, command, or artifact reference",
      "excerpt": "Small exact excerpt when available"
    }
  ],
  "confidence": 0.0,
  "reproduction": "A deterministic reproduction or a precise next experiment; empty only when impossible",
  "recommendation": "Smallest fix that restores the violated invariant",
  "dedupe_key": "stable.root-cause.invariant-key"
}
```

Rules:

1. Trace every finding through the full causal chain. A symptom without a root cause is not a finding.
2. Include at least one concrete evidence item for every finding.
3. Build `dedupe_key` from the root cause and violated invariant, not from the visible symptom.
4. Do not invent line numbers, runtime results, tests, or requirements.
5. Do not request changes for style-only preferences.
6. Use `COMMENT` and `CANDIDATE` when evidence is incomplete.
7. Use `REQUEST_CHANGES` only when the evidence-backed impact justifies blocking acceptance.
8. Keep different root causes separate even when they produce the same symptom.
9. Keep one root cause as one finding even when it produces several downstream symptoms.
10. `tests_to_run` must target causal links or invariants, not merely increase generic coverage.
