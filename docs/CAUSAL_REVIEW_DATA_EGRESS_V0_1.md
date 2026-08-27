# LS Causal Reviewer Data Egress v0.1

## Scope

The trusted causal ensemble may send one frozen pull-request patch and wrapper-owned target metadata
to external model providers. This document defines the current boundary.

## Provider opt-in

A native provider is enabled only when its repository secret exists:

| Lane | Repository secret | External endpoint |
| --- | --- | --- |
| Grok | `XAI_API_KEY` | xAI API configured by the trusted Grok wrapper |
| DeepSeek | `DEEPSEEK_API_KEY` | `DEEPSEEK_API_URL` |
| Codex | `OPENAI_API_KEY` | `OPENAI_RESPONSES_API_URL` |

Creating one of these repository secrets is the repository owner's explicit opt-in to sending the
verified frozen patch to that provider. A missing secret creates `NOT_RUN/UNVERIFIED`; it never
silently falls back to another provider.

## Data sent

A native reviewer receives only:

- repository and PR identity;
- exact reviewed head SHA;
- exact patch SHA-256;
- bounded frozen patch text;
- causal-review instructions.

It does not receive another reviewer's findings before completing its own lane. Target-PR code is
not executed, imported, built, installed, or tested by the trusted workflow.

## Data not intentionally sent

The workflow does not intentionally send:

- repository model API keys;
- GitHub tokens;
- workflow environment variables unrelated to target identity;
- files outside the exact GitHub patch;
- local workspace or dependency contents.

The patch itself remains untrusted data and may contain sensitive source text. Repository owners
must not configure a provider secret when organizational policy forbids that provider from
receiving the repository's patches.

## Artifact retention

Trusted and fork evidence artifacts use seven-day retention. They may contain:

- exact patch bytes;
- raw GitHub review-thread responses;
- raw provider responses;
- validated reviewer artifacts;
- provisional ensemble reports.

Artifact access follows repository GitHub Actions permissions. Artifacts must not be published as
public release assets or copied into merge-authoritative status checks.

## Failure semantics

Provider HTTP errors, quota exhaustion, model mismatch, invalid causal output, missing credentials,
and stale target identity remain explicit non-completed states. No such state may be interpreted as
a successful zero-finding review.

## Authority

External reviewer output is advisory evidence only. Human adjudication is required, and no provider
lane can approve, block, or merge a pull request by itself.
