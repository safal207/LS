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
./scripts/run_build_week_demo.sh
```

Expected summary:

```text
Scenario 1: stale approval           BLOCKED STALE_APPROVAL
Scenario 2: spoofed reviewer         BLOCKED UNTRUSTED_REVIEWER
Scenario 3: required lane absent     BLOCKED REQUIRED_LANE_NOT_RUN
Scenario 4: current-head review      TRUSTED ALL_REQUIRED_EVIDENCE_VALID
```

The runner is location-independent, uses only Bash and Python 3, and exits
non-zero if any observed verdict or reason differs from the required matrix.
Set `PYTHON=/path/to/python3` to select a specific interpreter.

For a detailed human or machine report from one fixture:

```bash
python3 tools/build_week_trust_gate.py build-week/demo/stale-approval.json --format human
python3 tools/build_week_trust_gate.py build-week/demo/stale-approval.json --format json
```

Without `--format`, the CLI prints a human verdict followed by the canonical
JSON trust report. Use `--format human` or `--format json` to select one
representation.

Without `--verify-expected`, a `BLOCKED` verdict returns a non-zero exit code so
the gate fails closed. `--verify-expected` is only the fixture-test mode: it
returns zero when the observed verdict and reason match the fixture oracle.

## Test

```bash
python3 -m unittest -v \
  tests/test_build_week_trust_gate.py \
  tests/test_build_week_demo.py
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
