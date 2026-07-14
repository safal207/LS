# Docker clean-room validation

Validation subject: [`3b5b0486ca51f0b08190d1207204cf20a3d219b6`](https://github.com/safal207/LS/commit/3b5b0486ca51f0b08190d1207204cf20a3d219b6)  
Workflow: [`Build Week Docker Smoke` run 29317829635](https://github.com/safal207/LS/actions/runs/29317829635)  
Result: **SUCCESS**

## Environment

- GitHub-hosted Ubuntu 24.04 runner;
- container base image: `python:3.12-slim`;
- no third-party Python packages;
- no credentials or external services required by the running demo.

## Exact-head proof

The workflow resolved the pull-request source SHA to
`3b5b0486ca51f0b08190d1207204cf20a3d219b6`, checked out that exact commit, and
verified `git rev-parse HEAD` before building the image.

## Reproduced command

```bash
./scripts/run_build_week_docker.sh 3b5b0486ca51f0b08190d1207204cf20a3d219b6
```

The container command runs, in order:

```bash
./scripts/run_build_week_demo.sh
python3 -m unittest -v \
  tests/test_build_week_trust_gate.py \
  tests/test_build_week_demo.py
```

Because the container uses `set -e` semantics and the GitHub Actions step
completed successfully, both the four-scenario verdict matrix and all 10 focused
tests completed with exit code zero.

## Boundaries

This validates reproducibility in a clean Linux container. Docker Desktop hosts
on macOS and Windows are not claimed as independently tested by this evidence.
