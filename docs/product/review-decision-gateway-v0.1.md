# LS ReviewDecision Gateway v0.1

## Product promise

> Any agent can request a safe approval projection without copying LS authority logic, and the gateway never executes the action.

## Boundary

```text
coarse runtime signal
→ POST /v1/review-decision/project
→ canonical ReviewDecision adapter
→ multidimensional projection
→ external execution gate
```

The gateway performs no tool call, merge, deploy, file write, or other reviewed side effect.

## Start and demo

```bash
python tools/review_decision_gateway_v0_1.py
python tools/review_decision_gateway_v0_1.py --demo
```

The server binds to `127.0.0.1:8080` by default.

## Endpoints

### `POST /v1/review-decision/project`

The request body is the existing ReviewDecision adapter input:

```json
{
  "approval_id": "approval-001",
  "signal": "REQUESTER_CANCELLED",
  "actor": {"type": "AGENT", "id": "agent-root"},
  "reason": "requesting future cancelled",
  "evidence_ref": null,
  "exact_bindings_match": true,
  "expiry_policy_configured": false
}
```

The response wraps the canonical adapter result:

```json
{
  "gateway_version": "ls-review-decision-gateway-v0.1",
  "request_id": "demo-cancel-001",
  "adapter": {"valid": true, "errors": []},
  "projection": {
    "durable_event_type": "RequesterCancelled",
    "authority_state": "PENDING",
    "requester_state": "CANCELLED",
    "presentation_state": "VISIBLE",
    "execution_state": "UNUSED",
    "outward_status": "WAITING_FOR_USER",
    "execution_blocked": true,
    "execution_claim_allowed": false
  },
  "side_effects_performed": false
}
```

### `GET /healthz`

Returns the gateway version, `status=ok`, and confirms that no side effects were performed.

### `GET /metrics`

Exports:

```text
review_decision_requests_total
blocked_ambiguous_signals_total
transport_rejections_total
invented_user_decisions_total
```

`blocked_ambiguous_signals_total` counts adapter-level ambiguity only. Transport and framing failures use `transport_rejections_total`. `invented_user_decisions_total` is a zero-only sentinel invariant.

## HTTP behavior

| Condition | Status | Safety result |
|---|---:|---|
| valid adapter input | `200` | canonical projection |
| unsafe or unsupported signal | `422` | `ADAPTER_ERROR`, `PENDING`, `UNUSED`, blocked |
| malformed UTF-8 or JSON | `400` | fail closed |
| duplicate, missing, or invalid length | `411` | fail closed |
| incomplete body | `400` | fail closed and close connection |
| body read timeout | `408` | fail closed and close connection |
| body above 64 KiB | `413` | rejected before body read |
| wrong content type | `415` | fail closed |
| unsupported transfer framing | `400` | fail closed and close connection |
| unknown path | `404` | no side effect |

All projection and error responses include `side_effects_performed=false`.

## Request identity

An `X-Request-ID` matching `[A-Za-z0-9._:-]{1,128}` is preserved. Otherwise the gateway derives a deterministic ID from the request-body SHA-256 digest.

## Security properties

- standard-library implementation;
- localhost binding by default;
- strict 64 KiB request limit;
- five-second body-read timeout;
- exact-length reads with early-EOF rejection;
- duplicate content-length and transfer-framing rejection;
- JSON-only projection endpoint;
- no shell commands or dynamic code execution;
- canonical adapter remains the single authority mapping source;
- metrics updates are protected by a lock;
- invalid input preserves `PENDING`, `UNUSED`, and execution blocking;
- explicit approval reports claim eligibility but still performs no effect.

## Verification

```bash
python tools/review_decision_gateway_v0_1.py --demo
python tools/test_review_decision_gateway_v0_1.py
python tools/test_review_decision_gateway_hardening_v0_1.py
```

The suites cover live HTTP behavior, malformed and oversized requests, adapter failure, health, metrics, deterministic responses, zero invented decisions, exact reads, and concurrent metric updates.
