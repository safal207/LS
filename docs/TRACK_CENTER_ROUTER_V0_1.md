# LS Track Center Router v0.1

The Router is the fail-closed entry point for LS track events:

```text
TrackCenterEnvelope -> exact route -> typed center
  -> Continuity Coordinator -> ACCEPT | HOLD | BLOCK
```

## Routes

1. `relationships.loss`
2. `projects.lifecycle`
3. `values.evidence`
4. `errors.learning`
5. `goals.commitments`
6. `capabilities.constraints`

The enum and typed dispatch registry must match exactly. No free-text route
inference or fallback routing is allowed.

## Router decisions

- `ROUTED`: exact route and valid versioned payload. The nested decision may
  still be `ACCEPT_BOUNDED_OBSERVATION`, `HOLD_FOR_REVIEW`, or
  `BLOCK_FALSE_PRESENCE`.
- `HOLD_UNKNOWN_ROUTE`: no exact route exists.
- `HOLD_MALFORMED_PAYLOAD`: the typed event contract rejected the payload.

Capability payload failures use `capability_constraint_payload_invalid`. Raw
payload content is never echoed in diagnostics.

## Provenance

The deterministic route-result ID binds the envelope digest, requested and
selected routes, decision, reason codes, nested result ID, diagnostic, and
Router policy version.

## Authority boundary

Routing never grants permission. Every result keeps relationship, project,
value, incident, goal, capability, task, remediation, priority, scheduling,
identity, and execution authority disabled. The capability route explicitly
adds:

```json
{
  "capability_registry_mutation_allowed": false,
  "capability_restriction_allowed": false,
  "global_limitation_assignment_allowed": false,
  "training_scheduling_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

A future route requires a reviewed key, event contract, typed adapter,
fail-closed diagnostic, schema, tests, artifacts, docs, and authority denials.
