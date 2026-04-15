# Security Policy

## Supported Scope

Security maintenance is focused on the active default branch and current release line.

## Reporting a Vulnerability

Please report vulnerabilities privately and include:

- Affected component and version/commit.
- Clear reproduction steps.
- Expected vs actual behavior.
- Potential impact assessment.

Do not open public issues for undisclosed vulnerabilities.

## Response Targets

- **Acknowledgement**: within 3 business days
- **Initial triage**: within 7 business days
- **Remediation plan**: within 14 business days for confirmed high severity issues

## Severity Model

- **Critical**: immediate compromise or remote code execution risk
- **High**: significant security bypass or sensitive data exposure
- **Medium**: constrained but meaningful security weakness
- **Low**: limited exploitability or low-impact hardening gap

## Remediation Process

1. Triage and severity assignment.
2. Patch development and review.
3. CI verification and security checks.
4. Coordinated disclosure note in release/changelog.

## Dependency and Supply-Chain Controls

- Pin dependencies where practical.
- Run vulnerability scanning in CI.
- Track exceptions explicitly with rationale and expiry review.

## Safe Harbor

Good-faith security research and responsible disclosure are appreciated.
