# LS Track Center Router v0.1

## Purpose

The Track Center Router is the single fail-closed entry point for LS track-center
events.

It receives an explicit `TrackCenterEnvelope`, performs exact route matching,
and delegates the payload to the selected track center. It never infers a route
from free-form text and never grants identity, memory, Relational Self, or
execution authority.

## Runtime position

```text
TrackCenterEnvelope
  -> Track Center Router
  -> exact route match
  -> concrete Track Center
  -> Continuity Coordinator
  -> bounded lesson | HOLD | BLOCK
  -> existing Verified Episode / Identity Control Plane
```

## Supported routes in v0.1

| Route key | Handler |
|---|---|
| `relationships.loss` | Relationship/Loss Track Center v0.1 |

The route set is explicit and immutable for the v0.1 contract. Adding a future
center requires a reviewed code and schema change.

## Decisions

### `ROUTED`

The route key exactly matched a registered center and the payload passed that
center's event-contract validation.

`ROUTED` does not mean the inner observation was accepted. The routed result may
still contain a Continuity Coordinator decision of:

- `ACCEPT_BOUNDED_OBSERVATION`;
- `HOLD_FOR_REVIEW`;
- `BLOCK_FALSE_PRESENCE`.

The router preserves this nested decision without weakening it.

### `HOLD_UNKNOWN_ROUTE`

No exact route exists. The router does not guess based on payload fields,
keywords, embeddings, or model output.

```json
{
  "decision": "HOLD_UNKNOWN_ROUTE",
  "selected_route": null,
  "diagnostic_code": "unknown_track_center_route"
}
```

### `HOLD_MALFORMED_PAYLOAD`

The route exists, but the payload cannot instantiate the selected center's
versioned event contract.

Examples:

- missing required field;
- invalid lifecycle status;
- invalid enum value;
- relationship lifecycle inconsistency;
- duplicate evidence references;
- partial identity-candidate fields.

The diagnostic is intentionally bounded and does not echo potentially sensitive
payload content.

## Envelope contract

```json
{
  "schema_version": "trusted_runtime.track_center_envelope.v0.1",
  "envelope_id": "track-envelope:123",
  "route_key": "relationships.loss",
  "payload": {},
  "submitted_at": "2026-06-25T05:00:00Z",
  "source_refs": ["source:event-bus:123"],
  "metadata": {}
}
```

The envelope digest binds the full canonical envelope, including the requested
route and payload.

## Provenance

The deterministic route-result ID binds:

- envelope digest;
- requested route;
- selected route;
- router decision and reason codes;
- nested routed-result ID when present;
- bounded diagnostic code;
- router policy version.

This preserves replayable lineage:

```text
envelope
  -> route result
  -> relationship/loss result
  -> track observation
  -> continuity assessment
```

## Authority boundary

Every route result states:

```json
{
  "relational_self_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

These flags remain false even when routing succeeds and the nested center emits
a bounded `LessonCandidate`.

A route is a destination decision, not permission.

## Non-goals

v0.1 does not:

- infer a track from natural language;
- choose among multiple candidate centers using an LLM;
- execute fallback routing;
- mutate memory or identity;
- retry malformed payloads automatically;
- authorize tools or external effects;
- dynamically load unreviewed track-center plugins.

## Extension rule

A future track center must add all of the following in one governed change:

1. canonical route key;
2. versioned input contract;
3. deterministic mapping adapter;
4. fail-closed malformed-payload behavior;
5. schema and tests;
6. reviewer artifacts;
7. explicit no-authority assertions.
