# HCP Marketplace MVP (internal credits)

## Scope

- **No blockchain:** balances are **internal credits** per `instance_id` (LS / runtime instance id).
- **Items:** 8 seed catalog entries (`hcp-safety-pack`, `hcp-benchmark-kit`, …) created on first store load; persisted in JSON.
- **Flows:** list catalog → `purchase` (deduct credits) → `install` (records install, returns `plugin_id` for a future PluginManager load).

## HTTP API (stdlib server)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/hcp/health` | liveness |
| GET | `/api/hcp/items` | full catalog |
| GET | `/api/hcp/items/{id}` | one item |
| GET | `/api/hcp/credits?instance=...` | balance (default instance `default` gets starting credits) |
| POST | `/api/hcp/purchase` | `{"item_id", "instance_id"}` |
| POST | `/api/hcp/install` | `{"item_id", "instance_id"}` (requires prior purchase) |

CORS: optional env `HCP_CORS_ORIGIN` (default `*`).

## Run

```bash
PYTHONPATH=python python scripts/run_hcp_marketplace_api.py --port 8781
```

State file: `hcp_marketplace.json` in cwd (override with `--state`).

## Tests

`python/tests/test_hcp_marketplace.py` — seed count, service purchase/install, HTTP smoke.
