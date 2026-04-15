# Threat Model

This is a high-level threat model for LS as a local-first cognitive runtime.

## Assets

- Operator inputs and workflow context.
- Model prompts, responses, and intermediate state.
- Quality and safety artifacts.
- Configuration, secrets, and dependency graph.

## Trust Boundaries

- Local runtime process boundary.
- External model/API integrations (when enabled).
- CI/CD and repository automation boundary.
- Artifact publication boundary.

## Threat Categories

### 1) Supply-Chain and Dependency Risk

- Vulnerable package versions.
- Malicious dependency updates.
- Drift between local and CI environments.

**Mitigations**
- Vulnerability scanning, pinning, and review windows.
- Explicit temporary exceptions with expiry.
- Reproducible dependency workflow.

### 2) Prompt and Input Injection

- Adversarial content entering operator or model flow.
- Unsafe tool-call instruction propagation.

**Mitigations**
- Input sanitization and bounded tool behavior.
- Safety checks and quality gates in CI.
- Clear separation of untrusted content from system policy.

### 3) Secrets and Configuration Exposure

- Accidental secret commits.
- Overly permissive CI logs/artifacts.

**Mitigations**
- Secret scanning and review gates.
- Principle of least privilege in workflows.
- Artifact redaction discipline.

### 4) CI/CD Integrity

- Unauthorized workflow changes.
- Bypass of required checks.

**Mitigations**
- Branch protection and required checks.
- Code review for workflow/security changes.
- Audit trail in PR and release process.

### 5) Operational Reliability as Safety Risk

- Flaky checks masking regressions.
- Unstable release process causing unsafe rollback patterns.

**Mitigations**
- Green-main policy.
- Flake triage and budget.
- Release checklist with post-release monitoring.

## Residual Risks

- Third-party ecosystem vulnerabilities can appear faster than remediation windows.
- Optional external integrations may increase attack surface if misconfigured.

## Review Cadence

Threat model should be reviewed at least quarterly and after major architectural changes.
