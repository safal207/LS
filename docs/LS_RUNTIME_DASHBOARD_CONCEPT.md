# LS Runtime Dashboard Concept

_Status: visual concept and public-facing observability note_

This document defines how the LS runtime dashboard visuals should be used in the
project, landing page, README, and public posts.

The uploaded visual bundle contains five 1600×900 PNG dashboard concepts:

- `preview-desktop.png`
- `final-mid.png`
- `preview-hcp.png`
- `preview-lower.png`
- `preview-bottom.png`

Recommended repository location:

```text
docs/assets/dashboard/preview-desktop.png
docs/assets/dashboard/final-mid.png
docs/assets/dashboard/preview-hcp.png
docs/assets/dashboard/preview-lower.png
docs/assets/dashboard/preview-bottom.png
```

## Core interpretation

These visuals should be used as:

> Concept interface for inspecting LS runtime state.

They should not be used as:

- production UI proof,
- consciousness claim,
- biological system claim,
- safety proof by themselves,
- or evidence that all displayed modules are complete runtime features.

## Best public framing

Use this line:

> LS makes agentic cognition inspectable: gateway decisions, trust transitions,
> memory events, human-state checks, protocol activity, and governed runtime
> state in one visual surface.

Shorter:

> Living cognition, made inspectable.

Product framing:

> A runtime dashboard for your personal AI operating layer.

Safety framing:

> A concept UI for observing how raw agent output becomes governed transitions.

## Why these visuals matter

LS is architecturally deep. Text alone can make it feel abstract.

The dashboard concepts create an immediate mental model:

```text
LS is not just a chat wrapper.
LS is a runtime with observable state.
```

They help communicate:

- architecture layers,
- runtime health,
- trust state,
- protocol activity,
- emotional/relational signals,
- memory timeline,
- human-state proxy checks,
- and HCP / protocol marketplace direction.

## Recommended usage

### 1. GitHub Pages landing

Use `preview-desktop.png` as the main hero/product visual.

Suggested caption:

```text
Runtime dashboard concept: inspect gateway state, trust transitions,
protocol activity, memory events, and relational signals as LS routes agent
output into governed transitions.
```

Do not caption it as production UI.

### 2. README

Add a short section after the project thesis or live-site link:

```md
## Runtime dashboard concept

LS is designed to expose not only final answers, but the state of the runtime:
gateway decisions, trust transitions, memory events, human-state checks, and
protocol activity.

![LS runtime dashboard concept](docs/assets/dashboard/preview-desktop.png)
```

### 3. Attention / social content

Good public hook:

```text
Most AI dashboards show tokens, latency, and cost.

LS dashboard concept shows something different:
- trust transitions
- memory events
- consent/evidence gates
- emotional resonance signals
- protocol activity
- governed runtime state

Not just observability of models.
Observability of agentic cognition.
```

### 4. Reviewer path

Use the visuals as orientation, then route reviewers to evidence:

1. dashboard concept image,
2. `docs/LS_SYSTEM_MAP.md`,
3. `docs/LS_ONTOLOGY.md`,
4. `docs/LS_TRANSITION_ID_DESIGN.md`,
5. demo / benchmark / trace artifacts.

## Claim discipline

The visuals contain bio-inspired labels such as:

- amygdala,
- bloodstream,
- endocrine,
- emotional resonance,
- human state,
- bio systems.

These are powerful metaphors, but they must be framed carefully.

Recommended disclaimer:

> Bio-inspired labels are interface metaphors for runtime observability. They do
> not claim biological equivalence, subjective emotion, or machine consciousness.

## Mapping visual regions to LS concepts

| Visual region | LS interpretation | Safety note |
|---|---|---|
| Architecture stack | Layer map / runtime modules | Orientation, not proof |
| Trust FSM network | Transition and trust-state visualization | Must be backed by trace data |
| Human State / HCP | Human/context protocol surface | Avoid medical/biological claims |
| Emotional resonance | Inferred relational/emotional signals | Advisory only |
| Memory timeline | Event and memory continuity | Should link to transition IDs |
| Protocol activity | Marketplace/plugin/protocol events | Needs provenance and authorization |
| Runtime metrics | Observability summary | Should distinguish real metrics from concept placeholders |

## Best next implementation steps

### Step 1 — add assets

Add the five PNG files under:

```text
docs/assets/dashboard/
```

### Step 2 — README concept section

Add a concise README block with one image and a careful caption.

### Step 3 — landing integration

Add `preview-desktop.png` to the landing hero or proof section.

Suggested landing block:

```text
Runtime observability for agentic cognition

See how LS tracks raw agent output, gateway decisions, trust transitions,
memory events, and evidence-gated actions before anything becomes persistent
state.
```

### Step 4 — tie visuals to transition replay

Once `episode_id` / `transition_id` support lands, connect the dashboard story to
real replay artifacts:

```text
visual node → transition_id → trace artifact → decision digest
```

This turns the dashboard from a concept image into a proof surface.

## Related work

- `docs/LS_SYSTEM_MAP.md`
- `docs/LS_ONTOLOGY.md`
- `docs/LS_TRANSITION_ID_DESIGN.md`
- `docs/LS_ATTENTION_BACKLOG.md`
- Issue: `Rewrite GitHub Pages hero around personal AI operating layer`

## Final positioning

The dashboard concept is valuable because it makes the LS thesis visible:

> not just answers, but governed runtime state.

Or even shorter:

> living cognition, made inspectable.
