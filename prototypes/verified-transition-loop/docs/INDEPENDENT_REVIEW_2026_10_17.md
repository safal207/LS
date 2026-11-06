# LGD-Eval v0.14 independent review: non-normative disposition

- Baseline: [`safal207/LS@9c7fc7c`](https://github.com/safal207/LS/tree/9c7fc7c3c73ec0107615af3051e78639405301e7/prototypes/verified-transition-loop)
- [LGD-Eval review](https://github.com/LGD-Eval/evaluation-protocol/blob/63e0acb2e0b099d69653889bdae538568a7294fb/reviews/verified-transition-loop/REVIEW.md)

This documents existing verifier behavior, **not** a protocol revision, certification, or new result contract. v0.14 fixtures, schemas and acceptance semantics remain unchanged.

## Finding dispositions

| Finding | Existing behavior | Consumer guidance |
| --- | --- | --- |
| F1: `valid=false` is binary | `reason_codes` distinguish missing bundle structure (`TRANSPARENCY_BUNDLE_FIELDS_INVALID`) from conflicting evidence (`ENTRY_SNAPSHOT_DIGEST_MISMATCH`); either may also fail inclusion | Treat `valid=false` as non-acceptance, **not** proof of compromise. Structural invalidity may mean *missing or extra fields*; mixed diagnoses require inspecting the evidence and provenance |
| F2: accepted checkpoint fields are null on rejection | `accepted_tree_size` and `accepted_root_hash` describe only a fully accepted candidate; they are `null` on failure | Retain the caller's independently trusted prior checkpoint; do **not** promote a rejected candidate or recover the anchor from untrusted bundle contents |
| F3: cryptographic proof versus structural integrity | Extra checkpoint fields fail `CHECKPOINT_FIELDS_INVALID`, even if signature, inclusion and consistency calculations remain valid | Never let valid mathematical proofs override a failed structural prerequisite |

The `verifier_checkpoint` input supplies previously trusted anchor values, but the reference verifier **does not implement durable anchor storage or persistence**. Callers must protect and maintain that state separately. Reason codes do not constitute a universal retryable-versus-compromised classifier.

## Regressions and boundaries

`tests/test_lgd_eval_v014_regressions.py` checks missing evidence, a tampered entry digest, rejected candidate checkpoint retention in a **test-only caller policy**, checkpoint structural rejection, and exact Python/Node strict-verifier output parity. It does not test production durable storage.

From `prototypes/verified-transition-loop`:

```sh
python -m pip install -e '.[dev]'
pytest -q tests/test_lgd_eval_v014_regressions.py
```

Node.js must be available as `node` on `PATH`; absence fails the parity tests explicitly.

The external review's **9/9 fixture-file parsing** must not be conflated with the repository's **26 semantic v0.14 conformance cases**. The reported review variants found no verification bypass within their tested scope; this regression suite protects the relevant existing behavior without introducing a new security status or reason-code taxonomy.
