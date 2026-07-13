# LS OpenAI Build Week trust-gate demo

This slice implements all four required scenarios from issue #897:

```text
stale approval       -> BLOCKED / STALE_APPROVAL
spoofed reviewer     -> BLOCKED / UNTRUSTED_REVIEWER
required check absent -> BLOCKED / REQUIRED_LANE_NOT_RUN
current-head review  -> TRUSTED, eligible only for human-authorized delivery
```

The evaluator is deterministic, dependency-free, and performs no network or
delivery action. A fixture contains normalized GitHub evidence. Reviewer policy
is stored separately under `policy/`, so an input fixture cannot declare its own
reviewer trusted.

## Run

From the repository root:

```bash
for fixture in build-week/demo/*.json; do
  python3 tools/build_week_trust_gate.py "$fixture" --verify-expected
done
```

Each command prints a human verdict followed by the canonical JSON trust report.
Use `--format human` or `--format json` to select one representation.

Without `--verify-expected`, a `BLOCKED` verdict returns a non-zero exit code so
the gate fails closed. `--verify-expected` is only the fixture-test mode: it
returns zero when the observed verdict and reason match the fixture oracle.

## Test

```bash
python3 -m unittest -v tests/test_build_week_trust_gate.py
```

## Trust boundary

- The exact current PR head is an explicit decision input.
- Review evidence is bound to a commit SHA.
- Reviewer login, account type, authenticated provenance, and route are checked
  against a separate trusted policy.
- Required lanes retain distinct `PASS`, `FAIL`, and `NOT_RUN` states.
- Unknown, malformed, incomplete, or stale evidence fails closed.
- Fixture-only `expected_outcome` annotations are excluded from the decision
  evidence digest and cannot change a verdict.
- `TRUSTED` never means autonomous delivery; human authorization remains required.

The current fixtures model normalized evidence at the trusted collection
boundary. Live GitHub collection is deliberately outside this first demo slice.
