# LS Track Center Router v0.1

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
7. `roles.permissions`

The enum and typed dispatch registry must match exactly. Free-text inference and
fallback routing are forbidden.

## Decisions

- `ROUTED`: exact route and valid versioned payload. The nested result may still
  be `ACCEPT_BOUNDED_OBSERVATION`, `HOLD_FOR_REVIEW`, or
  `BLOCK_FALSE_PRESENCE`.
- `HOLD_UNKNOWN_ROUTE`: no exact route exists.
- `HOLD_MALFORMED_PAYLOAD`: the typed contract rejected the payload.

Roles/permissions failures use `role_permission_payload_invalid`. Diagnostics do
not echo raw payload data.

## Authority boundary

Routing is not authorization. The seventh route adds explicit denials for role
and permission mutation, access grants and denials, approval, delegation,
policy mutation, stable-identity updates, and execution.

```json
{
  "role_registry_mutation_allowed": false,
  "permission_registry_mutation_allowed": false,
  "access_grant_allowed": false,
  "access_denial_allowed": false,
  "approval_allowed": false,
  "delegation_allowed": false,
  "policy_mutation_allowed": false,
  "stable_identity_update_allowed": false,
  "execution_authorized": false
}
```

A future route requires a reviewed key, contract, typed adapter, fail-closed
diagnostic, schema, tests, artifacts, docs, and authority denials.
