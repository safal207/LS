# Network Operations

This document is the operator-facing entry point for the network control layer.

It covers the runtime scripts that expose the current state of:
- memory and reuse
- route pheromone history
- coalition health
- derived module health
- observer and adequacy state
- fix priorities

## Scripts

### 1. Unified dashboard

```powershell
python scripts/network_dashboard.py
```

Sections:
- `health`
- `explain`
- `fix`

Examples:

```powershell
python scripts/network_dashboard.py --section health
python scripts/network_dashboard.py --section explain
python scripts/network_dashboard.py --section fix
python scripts/network_dashboard.py --json
```

### 2. Raw health report

```powershell
python scripts/network_health.py
python scripts/network_health.py --json
```

This shows:
- `observer.status`
- `adequacy.status`
- `trajectory.trend`
- active route
- resonance knowledge units
- strong/weak routes
- top coalition
- top derived module
- stale modules
- future scenarios

### 3. Plain-language explanation

```powershell
python scripts/network_health_explain.py
python scripts/network_health_explain.py --json
```

This turns the raw health report into:
- `summary`
- `good`
- `bad`
- `next`

### 4. Prioritized fix plan

```powershell
python scripts/network_health_fix_plan.py
python scripts/network_health_fix_plan.py --json
```

This produces:
- `overall`
- `do_now`
- `do_next`
- `keep`

### 5. Operator loop

```powershell
python scripts/network_operator_loop.py
python scripts/network_operator_loop.py --json
```

Записать safe overrides в локальный env-файл:

```powershell
python scripts/network_operator_loop.py --apply-env-file
```

Или в конкретный файл:

```powershell
python scripts/network_operator_loop.py --apply-env-file .env.network
```

`python/modules/config.py` автоматически читает `.env.network` через `GRAPH_OPERATOR_ENV_FILE` как низкоприоритетный слой overrides:
- значения из `.env.network` применяются только если такие env ещё не заданы в системе;
- явные системные env-переменные сильнее;
- это безопасный слой для временных операторских корректировок.

## How to read the dashboard

### `observer.status`

- `stable`
  - the network is inside the current tuning fork
- `watch`
  - the network is usable, but drift or weak routes are building up
- `intervene`
  - the network should stop promoting aggressive routing until quality is restored

### `adequacy.status`

This is the short answer to:
- Is the network still cognitively sane and aligned?

If this is `watch` or `intervene`, do not increase route trust blindly.

### `route.active`

This is the current strongest route by:
- pheromone
- quality
- goal alignment
- run history

It is the current backbone of the network, not permanent truth.

### `resonance.units`

This shows how many verified reasoning-route units the network has stored.

If this is low or zero:
- the network still remembers answers and routes,
- but it does not yet have enough reusable cognitive-path memory.

### `coalition.active`

This shows the strongest cooperative group if one exists.

If this is empty:
- the network has not yet accumulated enough strong cooperative evidence

### `derived.active`

This shows the strongest trusted derived micro-module if one exists.

If this is empty:
- the network does not yet trust any derived module enough for reliable reuse

## Operational guidance

### When `observer.status = stable`

- keep the strongest route
- continue collecting evidence
- avoid unnecessary routing churn

### When `observer.status = watch`

- prune weak routes
- reduce trust inflation
- prefer grounded cooperative answers
- only grow derived modules from strong cooperative runs

### When `observer.status = intervene`

- stop promoting new derived modules
- lower exploration pressure
- force review of weak routes and stale modules
- run care cycles before expanding the network

## Practical workflow

### Quick check

```powershell
python scripts/network_dashboard.py
```

### Detailed machine-readable report

```powershell
python scripts/network_dashboard.py --json
```

### Action-oriented operator pass

1. Run:
```powershell
python scripts/network_dashboard.py --section fix
```
2. Apply `do_now`
3. Re-run the dashboard
4. Compare whether:
   - `observer.status` improved
   - weak routes shrank
   - adequacy risks decreased

### Apply-safe override loop

1. Generate and write safe overrides:
```powershell
python scripts/network_operator_loop.py --apply-env-file
```
2. Re-run:
```powershell
python scripts/network_dashboard.py
```
3. Compare whether:
   - `observer.status` improved
   - `adequacy.status` improved
   - weak routes shrank

## Related docs

- `docs/NETWORK_VOCABULARY.md`
- `docs/NETWORK_ORIENTATION_AND_TRAJECTORY.md`
- `docs/COOPERATIVE_MERITOCRACY_NETWORK.md`
