# GitHub Merge Preflight v0.1 — trust boundary

The preflight binds approval to the declared repository, pull request, and expected head SHA. It does not contact GitHub and therefore does not prove that the declared SHA is still the live PR head.

A real effect path must combine three independent proofs:

```text
Exact-head Evidence Acquisition (#802)
→ live repository / PR / head proof

GitHub Merge Preflight (#814)
→ user approval bound to that same identity

Commit-Before-Effect (#691)
→ verified authorization bundle, durable commit, one bounded effect
```

The exact-head evidence bundle must match the preflight binding on repository, pull-request number, and head SHA. Any mismatch, missing bundle, stale head, or incomplete comparison blocks the downstream claim.

`ALLOW_CLAIM` from the preflight is not execution authority. It remains insufficient by itself:

```json
{
  "execution_authorized": false,
  "merge_performed": false,
  "side_effects_performed": false
}
```
