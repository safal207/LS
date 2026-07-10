# TypeScript 7 stable review council carrier

This LS pull request is a one-time, read-only review carrier for two frozen external pull requests:

1. `safal207/typescript-7-rc-qa-benchmark#11`
   - base: `0930de5b62dca8b0fd4580cefded6d58af3e3435`
   - head: `7a6c5ff9e2adc513bb66135bcfd19c5c59bf4ef8`
2. `safal207/typescript-go-qa-findings#15`
   - base: `4535e1184e2048f400756cf5f0538cbdf8260f25`
   - head: `3206fe04b73ffc819143f47540bfd734ccbe2490`

## Trust boundary

The carrier workflow:

- validates that each target PR is still open;
- validates the exact base and head SHA before review;
- downloads patch text with GitHub CLI;
- never checks out or executes code from either target repository;
- sends only bounded patch text and target metadata to the pinned `grok-4.5` model;
- publishes an advisory result on this carrier PR;
- stores the manifest, combined patch, and model response as a 90-day artifact.

## Council lanes

- CodeRabbit: source-PR review comments and inline findings
- Qodo: source-PR review comments and inline findings
- Grok 4.5: frozen external patch review through this LS carrier
- Human adjudication: verify findings, construct a causal graph, apply only supported fixes, rerun CI, and resolve review threads

The carrier has no merge authority over either target PR.
