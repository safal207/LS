# Ordinary update/reopen projection regression vector

External failure-class evidence: `openai/codex#26990`, severe recurrence reported 2026-08-14.

## Why this vector exists

The original state-projection fixture proves that derived project/index state can be rebuilt from intact durable thread evidence. The newer recurrence adds a stricter transition requirement: an **ordinary desktop update/reopen** can be enough to lose visible project membership and pinned conversations even when durable thread data remains intact.

That means power loss is not a required trigger. Startup migration/reconciliation itself must be treated as a state transition with preservation invariants.

## Transition model

```text
trusted committed projection
        +
authoritative durable threads
        |
        v
update / reopen / startup reconciliation
        |
        v
candidate projection
        |
        +-- stale generation? -----------------> BLOCK
        +-- content mutation? -----------------> BLOCK
        +-- silent project-membership loss? ---> BLOCK
        +-- silent pinned-state loss? ----------> BLOCK
        |
        v
ACCEPT only if preservation invariants hold
```

## Core invariant

If canonical thread/session evidence still exists, an update, reopen, migration, crash recovery, or startup reconciliation must not silently reduce project membership or pinned state without an explicit user mutation authorizing that reduction.

Pins are intentionally treated differently from cwd-derived membership: **pinned state is user-authored state and must be preserved, not reconstructed from paths.**

## Frozen cases

`fixtures/update_reopen_cases.json` includes:

1. `ordinary_update_reopen_preserves_projection` — a newer candidate generation drops two memberships and two pins; the candidate is blocked and the trusted projection remains authoritative.
2. `ordinary_update_reopen_complete_projection_accepted` — a complete newer projection is accepted.
3. `explicit_user_mutation_can_reduce_projection` — legitimate user-authorized reduction is accepted, so the oracle does not confuse intentional edits with data loss.
4. `stale_update_reopen_candidate_blocked` — a stale startup writer cannot overwrite a newer committed generation.

## Redaction boundary

Detailed per-case reports exist only in-process for deterministic tests. The CLI/CI artifact crosses a stricter allowlist boundary and emits only the total case count plus counts per fixed verdict class. It does not log fixture identities, trigger strings, generations, thread IDs, project IDs, paths, content digests, prompts, titles, tokens, or session contents.

This split is intentional: conformance logic can remain richly testable without turning synthetic or future vendor-supplied fixture fields into an accidental logging channel.

## Run

```bash
python ls-conformance/state_projection_recovery/run_update_reopen_fixture.py \
  ls-conformance/state_projection_recovery/fixtures/update_reopen_cases.json
```

The vector is vendor-neutral. It is a conformance oracle, not a Codex repair script and not a claim about any vendor's internal storage implementation.
