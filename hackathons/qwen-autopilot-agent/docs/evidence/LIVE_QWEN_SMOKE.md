# Live Qwen smoke evidence

A real Alibaba Cloud Model Studio request completed successfully through the Qwen OpenAI-compatible endpoint.

## Exact evidence

- source branch: `agent/qwen-autopilot-agent`
- tested head: `24ab32d04871798b240b95e2daf6d3e18049dfec`
- workflow: `Qwen Autopilot Agent`
- workflow run ID: `29706522814`
- job ID: `88244366628`
- artifact ID: `8448074218`
- artifact digest: `sha256:6fa93b99181c67d3696d4924c16ffb7e33a8ab171e0a4d733f6f931316737ae2`
- model: `qwen3.7-plus`
- Qwen status: `COMPLETED`
- validated assessment: `LOW / ALLOW`
- confidence: `0.98`
- execution status: `NOT_EXECUTED`
- authority: `advisory_only`

The repository secret was masked by GitHub Actions and is not present in this evidence. The live job checked out the exact subject head, validated the returned JSON with the application schema, and uploaded only the redacted result.

## Redacted result

See [`qwen-live-smoke-24ab32d0.json`](qwen-live-smoke-24ab32d0.json).

## Boundary

This proves that the configured key can call Qwen Cloud and that the application can validate a real structured response. It does not yet prove an Alibaba Cloud deployment. Public deployment evidence remains a separate submission requirement.
