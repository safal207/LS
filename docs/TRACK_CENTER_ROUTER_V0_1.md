# LS Track Center Router v0.1

## Purpose

The Track Center Router is the single fail-closed entry point for LS track-center
events.

It receives an explicit `TrackCenterEnvelope`, performs exact route matching,
and delegates the payload to the selected track center. It never infers a route
from free-form text and never grants identity, track-state, blame, priority,
task, remediation, or execution authority.

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
| `projects.lifecycle` | Projects Track Center v0.1 |
| `values.evidence` | Values Track Center v0.1 |
| `errors.learning` | Errors/Learning Track Center v0.1 |

The route set is explicit. Adding a center requires reviewed code, schema,
tests, deterministic artifacts, and authority-boundary assertions.

## Decisions

### `ROUTED`

The route key exactly matched a registered center and the payload passed that
center's versioned event-contract validation.

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

Bounded diagnostic codes are route-specific:

- `relationship_loss_payload_invalid`;
- `project_payload_invalid`;
- `value_payload_invalid`;
- `error_learning_payload_invalid`.

The diagnostic never echoes raw payload content.

## Envelope contract

```json
{
  "schema_version": "trusted_runtime.track_center_envelope.v0.1",
  "envelope_id": "track-envelope:123",
  "route_key": "errors.learning",
  "payload": {},
  "submitted_at": "2026-06-25T05:00:00Z",
  "source_refs": ["source:event-bus:123"],
  "metadata": {}
}
```

The envelope digest binds the full canonical envelope, including requested route
and payload.

## Provenance

The deterministic route-result ID binds:

- envelope digest;
- requested route;
- selected route;
- router decision and reason codes;
- nested routed-result ID when present;
- bounded diagnostic code;
- router policy version.

Replayable lineage now supports four paths:

```text
envelope -> route result -> relationship/loss result -> continuity assessment
envelope -> route result -> project result -> continuity assessment
envelope -> route result -> value result -> continuity assessment
envelope -> route result -> error-learning result -> continuity assessment
```

## Authority boundary

Every route result states:

```json
{
  "relational_self_mutation_allowed": false,
  "project_registry_mutation_allowed": false,
  "task_scheduling_allowed": false,
  "value_registry_mutation_allowed": false,
  "priority_mutation_allowed": false,
  "incident_registry_mutation_allowed": false,
  "blame_assignment_allowed": false,
  "remediation_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

These flags remain false even when routing succeeds and a nested center emits a
bounded `LessonCandidate`.

A route is a destination decision, not permission.

## Non-goals

v0.1 does not:

- infer a track from natural language;
- choose among centers using an LLM;
- execute fallback routing;
- mutate relationship, project, value, or incident state;
- assign blame, schedule remediation, or reorder priorities;
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
