# OVC → VerifiedEpisode v0.2 fixtures

These suites define the executable bridge from Outcome Verification Center results into governed learning candidates.

## Run

```bash
python -m pip install jsonschema==4.23.0

python tools/run_ovc_verified_episode_fixtures.py \
  schemas/trusted_runtime/ovc_verified_episode_adapter_v0.1.schema.json \
  schemas/trusted_runtime/verified_episode_v0.2.schema.json \
  fixtures/ovc-verified-episode/mandatory-v0.2.json \
  fixtures/ovc-verified-episode/precedence-v0.2.json
```

## Coverage

The mandatory suite covers expected, failed, and unexpected verified outcomes; non-verified or unsafe OVC results; missing identity and provenance bindings; episode and causal-trace replay; retention expiry; invalid lifecycle ordering; lesson/outcome mismatch; incomplete redaction; missing lesson evidence; supersession; durable retention; and no direct identity mutation.

## Precedence

```text
REJECT > REVIEW > FORGET > ABSTAIN > WRITE_CANDIDATE
```

## Compatibility

Only `expected` projects to v0.1 `VERIFIED / MATCHED`. Verified `failed` and `unexpected` episodes project fail-closed to `UNVERIFIED / MISMATCHED`.
