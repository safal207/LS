# Fellowship Dataset

This folder contains a curated sample of council-ledger artifacts selected from `artifacts/council-ledger`.

Summary:

- ledger_count: 8
- success_count: 7
- failure_count: 1
- avg_resonance: 0.4062
- avg_contribution: 0.8345

Selection policy:

- exclude demo cycles
- exclude contract fixtures
- exclude `dry_run:unknown` ledgers
- keep a small mixed sample for fellowship review

Contents:

- `manifest.json`: dataset manifest and limitations
- `ledgers/`: selected council-ledger JSON artifacts
- `traces/`: reserved for replay traces in a follow-up package
