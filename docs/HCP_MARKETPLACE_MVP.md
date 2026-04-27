# HCP Marketplace MVP (internal credits)

## Scope

- **No blockchain:** balances are **internal credits** per `instance_id` (LS / runtime instance id).
- **Items:** 9 seed catalog entries (`hcp-safety-pack`, `hcp-benchmark-kit`, …) created on first store load; persisted in JSON.
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
| GET | `/api/hcp/runtime` | `detached` or `attached` (PluginManager bound to the process) |
| POST | `/api/hcp/load` | `{"item_id", "instance_id"}` → `load_plugin_into_manager` (**501** if API started without `--bootstrap`) |

CORS: optional env `HCP_CORS_ORIGIN` (default `*`).

## Run

```bash
PYTHONPATH=python python scripts/run_hcp_marketplace_api.py --port 8781
# With live PluginManager (POST /api/hcp/load enabled):
PYTHONPATH=python python scripts/run_hcp_marketplace_api.py --bootstrap apps/console/main.py
```

State file: `hcp_marketplace.json` in cwd (override with `--state`).

## CLI (load without HTTP)

```bash
PYTHONPATH=python python scripts/hcp_load_plugin.py --item hcp-runtime-echo --instance default
```

## Runtime load (PluginManager)

Items may set metadata `plugin_module` (e.g. `echo_plugin.py` under `python/plugins/`). After **purchase** and **install**, call:

`HcpMarketplaceService.load_plugin_into_manager(item_id, instance_id, plugin_manager)` to run `PluginManager.load_from_path` for that file. Demo item: `hcp-runtime-echo` (maps to the existing `echo_plugin.py` example).

## Tests

`python/tests/test_hcp_marketplace.py` — seed count, service purchase/install, HTTP smoke, PluginManager load for `hcp-runtime-echo`.
