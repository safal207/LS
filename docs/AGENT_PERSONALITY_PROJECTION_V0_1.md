# LS Agent Personality Projection v0.1

## Purpose

`AgentPersonalityProjection` is a read-only runtime view derived from an active,
governed `IdentityProfile` plus accepted, context-bound capability state.

It answers:

> What approved identity traits and current bounded capability facts may this
> runtime agent express in this specific context?

It does **not** answer:

> What should the agent permanently become?

That question remains inside the governed identity lifecycle.

## Runtime position

```text
Verified experience and continuity tracks
  -> IdentityProposalCandidate
  -> governance approval
  -> profile patch and durable commit
  -> active IdentityProfile
  -> AgentPersonalityProjection
  -> JSON / AGENTS.md / CLAUDE.md / system-prompt adapter
```

The projection is downstream of identity governance. A prompt file may deliver
it, but a prompt file is not the source of identity truth.

## Input boundary

The projector accepts only:

1. an active `IdentityProfile`;
2. a profile produced by a governed application, or an explicitly approved
   baseline profile with provenance;
3. an explicit runtime scope;
4. optional accepted current capability/constraint results from the governed
   `capabilities.constraints` center.

Pending proposals, approvals without application, inactive profiles, free-form
personality prose, disputed traits, and held capability claims are not active
projection inputs.

## Supported trait namespaces

v0.1 projects only explicit identity-profile keys under:

- `communication_style.*`;
- `working_tendencies.*`;
- `relationship_rules.*`.

Unknown namespaces are excluded rather than inferred.

A structured trait may carry:

```json
{
  "value": "proposal_before_action",
  "state": "ACTIVE",
  "confidence": 0.94,
  "source_refs": ["identity-influence:delegation:v2"],
  "scope": {
    "level": "relationship",
    "counterparty_ref": "human:alex"
  },
  "expires_at": null,
  "disputed": false,
  "conflict_refs": []
}
```

A trait is excluded when it is inactive, expired, disputed, conflicting,
unsupported, or outside the requested scope.

## Scope model

Every projection has exactly one scope:

- `individual`;
- `relationship` with a counterparty reference;
- `project` with a project reference;
- `organization` with an organization reference;
- `system`.

Scope is not a promotion ladder.

Examples:

- a relationship rule for `human:alex` does not appear for another human;
- a project capability for `project:ls` does not become system capability;
- an individual working tendency may be visible in a narrower runtime context,
  but relational or project claims require exact context matching;
- v0.1 does not project contextual capability claims into `system` scope.

## Capability and constraint inputs

Only accepted current claims from the governed Capabilities/Constraints Track
Center may enter the projection.

### Capability claim

Required shape:

- event type `CURRENT_CAPABILITY_CLAIM`;
- status `AVAILABLE` or `RECOVERED`;
- Continuity Coordinator decision `ACCEPT_BOUNDED_OBSERVATION`;
- source evidence;
- matching runtime context.

### Active constraint

Required shape:

- event type `CURRENT_LIMITATION_CLAIM`;
- status `CONSTRAINED` or `UNAVAILABLE`;
- a bounded non-unknown constraint kind;
- Continuity Coordinator decision `ACCEPT_BOUNDED_OBSERVATION`;
- source evidence;
- matching runtime context.

Observed, disputed, unknown, held, blocked, historical, recovered limitation,
expired, or retired claims are excluded from active capability projection.

Capability description is not permission. Constraint description is not access
denial.

## Projection record

The canonical record includes:

- projection ID and schema version;
- agent ID;
- exact identity-profile reference and version;
- creation and optional expiry timestamps;
- explicit runtime scope;
- communication style;
- working tendencies;
- relationship rules;
- current capability claims;
- active contextual constraints;
- complete source references;
- excluded or disputed references;
- explicit all-false authority effects.

The projection ID is deterministic for the same canonical input.

## Runtime adapters

v0.1 provides:

1. canonical JSON via `to_dict()`;
2. bounded Markdown via `render_personality_projection_markdown()`.

The Markdown adapter can be embedded in `AGENTS.md`, `CLAUDE.md`, or another
runtime instruction surface. It includes the source identity version and an
explicit authority disclaimer.

The adapter must not add inferred traits or hide excluded/disputed inputs.

## Freshness and invalidation

`validate_personality_projection()` evaluates a projection without modifying it.

Possible states:

- `ACTIVE` — source identity is still active and the projection is current;
- `STALE` — the active identity profile changed, was rolled back, or belongs to
  another agent;
- `REVOKED` — a source reference was explicitly revoked;
- `EXPIRED` — the projection validity window ended.

A new profile version invalidates projections bound to the old profile ref.
Rollback therefore makes the prior projection stale through the normal identity
version chain; it does not rewrite projection history.

## Authority boundary

Every projection states:

```json
{
  "may_authorize_execution": false,
  "may_approve_identity_change": false,
  "may_apply_identity_change": false,
  "may_create_profile_patch": false,
  "may_grant_tool_access": false,
  "may_deny_tool_access": false,
  "may_bypass_governance": false,
  "may_expand_scope": false
}
```

A runtime agent cannot use personality language such as “confident”, “trusted”,
“capable”, or “initiative-oriented” to obtain authority.

## Determinism and replay

The projection ID binds:

- agent ID;
- exact active profile ref and version;
- runtime scope;
- projected items and provenance;
- excluded/disputed refs;
- creation and expiry timestamps;
- projection policy version.

Replay can reconstruct the same read-only projection without rerunning a model,
reapproving identity, or reapplying profile changes.

## Non-goals

v0.1 does not:

- infer personality with an LLM;
- convert one episode directly into a trait;
- approve or apply identity changes;
- replace the active identity profile;
- grant or deny tools;
- authorize execution;
- simulate emotion;
- promote contextual capability to global capability;
- treat `AGENTS.md`, `CLAUDE.md`, or a system prompt as identity authority.

## Product principle

> The agent may express a personality at runtime, but only governed identity may
> define where that personality came from.
