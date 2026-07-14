# LS OpenAI Build Week trust-gate demo

This slice implements all four required scenarios from issue #897:

```text
stale approval         -> BLOCKED / STALE_APPROVAL
spoofed reviewer       -> BLOCKED / UNTRUSTED_REVIEWER
required check absent  -> BLOCKED / REQUIRED_LANE_NOT_RUN
current-head review    -> TRUSTED / ALL_REQUIRED_EVIDENCE_VALID
```

The evaluator is deterministic, dependency-free, and performs no network or
delivery action. A fixture contains normalized GitHub evidence. Reviewer policy
is stored separately under `policy/`, so an input fixture cannot declare its own
reviewer trusted.

## Fastest judge path: Docker

Prerequisite: Docker Engine or Docker Desktop.

From the repository root:

```bash
./scripts/run_build_week_docker.sh
```

The script builds `Dockerfile.build-week`, runs the four-scenario demo, and then
runs all focused unit tests inside a fresh `python:3.12-slim` container. No
third-party Python packages, credentials, network calls, or external services
are required at runtime.

Equivalent manual commands:

```bash
docker build --pull --file Dockerfile.build-week --tag ls-build-week:local .
docker run --rm ls-build-week:local
```

GitHub Actions also runs the same clean-room path from the exact source SHA in
[`Build Week Docker Smoke`](../.github/workflows/build-week-docker-smoke.yml).

## Native run

Prerequisites: Bash and Python 3.

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

The runner is location-independent and exits non-zero if any observed verdict
or reason differs from the required matrix. Set `PYTHON=/path/to/python3` to
select a specific interpreter.

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

## Native tests

```bash
python3 -m unittest -v \
  tests/test_build_week_trust_gate.py \
  tests/test_build_week_demo.py
```

## Supported and verified environment

- Docker clean room: Linux GitHub-hosted runner + `python:3.12-slim` image.
- Native evidence snapshot: Linux, Python 3.12.13, Bash 5.2.21.
- Expected to work with Docker Desktop on macOS and Windows, but those hosts are
  not claimed as independently verified.

## Evidence snapshot

The reproducible core-demo evidence snapshot is bound to reviewed commit
[`299db4b`](https://github.com/safal207/LS/commit/299db4b239eddad32b621f31bd8b47de25f40fd7):

- [attack matrix](evidence/attack-matrix.md);
- [machine-readable test and CI results](evidence/test-results.json);
- [canonical stale-approval trust report](evidence/trust-report.example.json);
- [Codex contribution log](evidence/codex-contribution-log.md);
- [Docker clean-room validation](evidence/docker-smoke.md), bound separately to
  exact source commit `3b5b048`.

Each evidence record names its subject SHA so later documentation commits do not
silently rewrite which implementation and CI run were verified.

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
