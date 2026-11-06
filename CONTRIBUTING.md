# Contributing to LS

Thank you for contributing to LS. We welcome focused bug reports, tests, documentation, examples, UX improvements, and fixes that make evidence-backed AI software delivery safer and easier to inspect.

**Start here:** [Project README](README.md) · [Good first tasks](docs/COMMUNITY_TASKS.md) · [Roadmap](ROADMAP.md) · [Lotus principles](LOTUS.md) · [Pull request template](.github/pull_request_template.md)

## Choose your contribution area

LS contains several layers; you do **not** need to install the entire research stack to contribute.

| Area | Where to start | Typical contributions |
| --- | --- | --- |
| **LS Exact-Head PR Risk Audit** (supported product) | [CLI documentation](packages/ls-audit-cli/README.md), `packages/ls-audit-cli/` | Exact-head validation, evidence collection, scorecards, deterministic tests, safe error handling |
| **Verified Transition Loop** (prototype) | [VTL README](prototypes/verified-transition-loop/README.md), `prototypes/verified-transition-loop/` | Protocol regression tests, Python/Node parity, fixtures, clear non-normative documentation |
| **Public site** | [Landing](ghostgpt-ls-landing/), [Pages setup](docs/GITHUB_PAGES_SETUP.md) | Mobile UX, accessibility, clearer examples and bilingual copy |
| **Legacy/research components** | [Legacy README](README_LEGACY.md) | Rust, local-first runtimes, agent integration, experimental features |

The root Python/Rust/ML stack is **legacy research infrastructure**, not a prerequisite for the supported audit CLI or most contributions. Choose the smallest environment that matches your change.

## First contribution: from issue to PR

1. Look at [community tasks](docs/COMMUNITY_TASKS.md), [open issues](https://github.com/safal207/LS/issues), or open a concise issue proposing your change. For a small documentation or test fix, a focused PR is also welcome.
2. Fork `safal207/LS`, create a topic branch from the latest `main`, and keep your changes limited to one concern.
3. Add or update the smallest meaningful tests for behavior changes. Documentation-only or copy-only contributions do not need artificial tests; check links, examples, and formatting instead.
4. Run the relevant local check(s) below and record the *actual* commands and results. If something cannot run, say so; never report missing tests as passed.
5. Push the branch and open a PR targeting `safal207/LS:main`. Fill in [the PR template](.github/pull_request_template.md): purpose, affected scope, validation, evidence, exact head SHA, and the Lotus check.
6. Respond to maintainer comments and update tests/evidence after any relevant commit. Merging is a maintainer decision following the applicable review and CI gates.

Example:

~~~bash
git clone https://github.com/YOUR_USERNAME/LS.git
cd LS
git remote add upstream https://github.com/safal207/LS.git
git fetch upstream
git switch -c fix/short-description upstream/main
# Make and verify your change, then commit and push to your fork.
~~~

### If your fork's GitHub Actions say `action_required`

**This is usually an approval gate, not a test failure.** GitHub may hold workflows from a first-time or otherwise untrusted fork contributor until someone with appropriate upstream permissions explicitly authorizes them.

- **Contributor:** leave the PR open; post a short comment with the exact head SHA and local results, then ask a maintainer to review the diff and approve the held workflow runs. You cannot approve upstream Actions from your fork. You do not need to push an empty commit or change CI settings to clear this gate.
- **Maintainer:** inspect the PR diff, especially any workflow, script, or dependency changes, *before* approving the run. In the PR's **Checks** area, use **Approve workflows to run** when the approval banner is shown and the code is safe to execute. Then check each workflow's real job results.
- **Both:** `action_required` with no jobs is **not** a green CI result. An approved run is also **not** a passed run. If the approval control is missing, check your repository permissions and Actions policy rather than disabling the security gate.

For reference, [PR #969](https://github.com/safal207/LS/pull/969) was held at this gate as an external fork contribution; it proceeded after maintainer approval and its CI completed successfully.

## Run only the checks you need

Use an environment dedicated to the subsystem you are changing. These commands are examples of *local checks*, not a claim that every check has been run on your branch.

### Audit CLI (Python 3.11+)

From repository root:

~~~bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install ./packages/ls-audit-cli pytest
python -m pytest -q packages/ls-audit-cli/tests
~~~

See [audit CLI operator documentation](docs/LS_EXACT_HEAD_AUDIT_CLI.md). Never commit an audit bundle that contains private patches, credentials, or customer data.

### Verified Transition Loop v0.14 (Python 3.11+, Node.js)

~~~bash
cd prototypes/verified-transition-loop
python -m pip install -e '.[dev]'
python -m pytest -q tests
node reference/transparency-log-conformance-v0.14.mjs fixtures/transparency-log-v0.14.json
~~~

Preserve the existing fixture, schema, acceptance and fail-closed semantics unless a protocol change has been explicitly scoped and reviewed. Keep prior trusted checkpoints separate from rejected candidate data. Compare Python and Node results when touching shared verifier behavior.

### Landing page (Node.js)

~~~bash
cd ghostgpt-ls-landing
npm ci
npm run build
npm run dev
~~~

Local preview: `http://127.0.0.1:5173/`. Include mobile screenshots for visual changes.

### Legacy Rust/Python components

Use the subsystem's own README and CI workflow; do not install the entire stack by default. Where applicable, run targeted `pytest`, `cargo test`, `clippy`, or `pre-commit` checks and state what was actually executed.

## Evidence, review and security expectations

- **Bind test evidence to the exact PR head SHA.** Copy the full 40-character SHA from the pushed branch. If the head, relevant inputs, dependency state or environment change, rerun the affected validation and update the PR.
- **Respect the trust boundary.** Never add personal data, real secrets, private logs, API keys, production credentials or unredacted third-party code to issues, fixtures, screenshots or artifacts. Use synthetic examples.
- **Fail closed.** Missing evidence, rejected proofs, stale checks, `NOT_RUN` and `INCOMPLETE` cannot be represented as success. AI-generated reviews and bot comments are advisory unless an explicit repository policy makes a check required.
- **Do not bypass Actions approval**, disable gates, or expose write-scoped tokens to untrusted fork code to make a PR appear green.
- **Keep design claims bounded.** Say which invariants and cases your tests cover; do not describe a test-only example as production persistence or imply universal security guarantees.
- **Follow [LOTUS.md](LOTUS.md):** decisions should remain inspectable, challengeable, privacy-preserving and human-governed. Automated evidence collection does not itself grant review, approval or merge authority.
- **Be constructive.** Explain risks with reproducible steps and actionable suggestions. Smaller PRs are easier to validate and review.

## Before requesting merge

- [ ] Changes are limited to a coherent scope, with relevant docs updated.
- [ ] Tests or manual verification match the changes; unavailable checks are clearly identified.
- [ ] The PR template includes the exact **current head SHA** and evidence captured at that revision.
- [ ] Held external-fork workflows were reviewed and approved by a maintainer before running.
- [ ] Required GitHub checks have **completed successfully**; `queued`, `action_required` and `in_progress` are not success.
- [ ] Reviewer concerns and applicable repository policies have been resolved.
- [ ] Any missing optional AI/bot review is described honestly, not treated as approval.

CI can take time; please do not force-push or make unrelated changes solely to retrigger held jobs.

## Communication and attribution

Use [Issues](https://github.com/safal207/LS/issues) for actionable defects and feature requests, or GitHub Discussions when available for open-ended architecture ideas. A short reproduction and expected vs. actual behavior are much more helpful than a vague failure report.

Contributors receive attribution through their commits and merged PR history. We appreciate external validation and respectful technical disagreement. Contributions to LS are made under the repository's [Apache-2.0 license](LICENSE).
