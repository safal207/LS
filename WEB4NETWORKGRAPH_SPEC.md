# WEB4NETWORKGRAPH_SPEC.md — Web4 Network Graph Specification (v1.0)

## 🎯 Purpose
Define the formal network graph schema for Web4 so mesh routing, trust propagation, service invocation, and observability are interoperable across implementations.

---

## 1) Node Schema

A **Node** represents an agent, service, or infrastructure peer.

```json
{
  "id": "node-a",
  "kind": "agent|service|router",
  "address": "local://node-a",
  "capabilities": ["cip", "mesh", "service"],
  "metadata": {
    "version": "1.0",
    "tags": ["edge", "demo"]
  }
}
```

### Required fields
- `id` (string)
- `kind` (string)
- `address` (string)

---

## 2) Edge Schema

An **Edge** represents a directed relationship between nodes.

```json
{
  "id": "edge-a-c",
  "source": "node-a",
  "target": "node-c",
  "relation": "routes|trusts|invokes",
  "weight": 1.0,
  "state": "active|inactive",
  "metadata": {
    "latency_ms": 5,
    "bandwidth": "low"
  }
}
```

### Required fields
- `id` (string)
- `source` (string)
- `target` (string)
- `relation` (string)

---

## 3) TrustFSM State Machine

TrustFSM states and transitions for a single peer:

- `unknown` → `probing` on handshake
- `probing` → `trusted` on verification
- `probing` → `blocked` on conflict
- `trusted` → `probing` on conflict
- Any → `blocked` on malicious signal

---

## 4) DistributedTrustFSM

Distributed trust propagates over trusted edges:

- If node A trusts node C, and node C introduces node B, node A sets node B to `probing`.
- Propagation MUST NOT auto-promote to `trusted` without local verification.

---

## 5) MeshEnvelope Schema

MeshEnvelope is the transport carrier for graph-aware routing.

```json
{
  "mesh": "1.0",
  "id": "<uuid>",
  "type": "MESH_HELLO|SERVICE_INVOKE",
  "origin": "node-a",
  "destination": "node-b",
  "payload": {},
  "hops": ["node-c"],
  "created_at": "2025-01-01T00:00:00Z"
}
```

Required fields: `mesh`, `id`, `type`, `origin`, `destination`, `payload`, `hops`, `created_at`.

---

## 6) Routing Rules (Minimal)

1. If `destination` equals `origin`, route locally.
2. Drop if destination already in `hops` (loop prevention).
3. Drop if hop count exceeds policy limit.
4. Drop if destination trust state is `blocked`.
5. Only route to destinations present in the peer registry.

---

## 7) Observability Event Contract

Events are emitted as graph-aware records:

```json
{
  "event_type": "mesh_routed|trust_updated|service_invoked",
  "node": "node-a",
  "peer": "node-b",
  "payload": {},
  "occurred_at": "2025-01-01T00:00:00Z"
}
```

---

## 8) Service Graph Extensions

Service invocation extends the graph with `invokes` edges:

- `relation`: `invokes`
- `metadata`: `{ "service": "service-b", "version": "1.0" }`

Services are nodes with `kind: "service"` and MUST expose a handler.
