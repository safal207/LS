# Reflection Approve -> Publish to CEL (Integration Example)

This example shows how a reflection-approved insight can be published as a CEL proposal.

## Flow

1. Reflection Dashboard marks an insight as `approved`.
2. Runtime builds a proposal payload.
3. CEL `DecisionListingAPI.create()` publishes the proposal.
4. CEM emits `proposal_created`.
5. CTL receives stake/payment events through wallet callbacks.

## Example (Python)

```python
from decimal import Decimal

from modules.cel import CELWalletAPI, DecisionListingAPI, ProposalCreateRequest

# Reflection-approved signal (output of dashboard/workflow)
reflection_output = {
    "approved": True,
    "agent_id": "energy-98231",
    "asset": "oil",
    "prediction": "price_up_5pct_7d",
    "confidence": 0.87,
}

ctl_events = []
cem_events = []

wallet = CELWalletAPI(append_ctl_event=ctl_events.append)
wallet.create_wallet("energy-98231", Decimal("100"))

api = DecisionListingAPI(
    wallet_api=wallet,
    publish_cem_event=cem_events.append,
)

if reflection_output["approved"]:
    proposal = api.create(
        ProposalCreateRequest(
            trace_id="trace_reflect_publish_001",
            proposal_id="prop_reflect_001",
            agent_id=reflection_output["agent_id"],
            asset=reflection_output["asset"],
            prediction=reflection_output["prediction"],
            confidence=reflection_output["confidence"],
            price_ct=Decimal("10"),
            ttl_sec=3600,
        )
    )

    print(proposal["proposal_id"], proposal["status"])
```

## Notes

- Ensure stake wallet funding before publish (min stake: 5 CT).
- In production, use `EventSigner` for cryptographic CTL signatures.
- Connect settlement output to `ReputationEngine.update()` for closed-loop repricing.
