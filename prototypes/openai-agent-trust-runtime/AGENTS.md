# Seven-Agent Council

The reference workflow uses seven durable peer roles. Every role has its own thread identity, bounded authority, required outputs, and explicit prohibitions.

| Role | Russian name | Purpose | May do | Must never do |
|---|---|---|---|---|
| Idea | Агент Идея | Form a falsifiable product hypothesis | Propose direction | Claim validation or authorize implementation |
| Customer | Агент Заказчик | Define scope, constraints, and acceptance | Define requirements | Silently change the goal or approve unverified completion |
| Consumer | Агент Потребитель | Represent the end-user experience | Evaluate usability and trust | Invent customer approval or hide user risk |
| Designer | Агент Проектировщик | Design the smallest compliant system | Design and request bounded implementation | Bypass constraints or treat claims as evidence |
| Executor | Агент Исполнитель | Implement and test the bounded design | Write a patch and run tests | Merge, deploy, or claim completion without evidence |
| Stabilizer | Агент Стабилизатор | Attack correctness, safety, and recovery | Review evidence and block release | Waive missing evidence or turn advice into approval |
| Innovator | Агент Новатор | Find a 10x next step without weakening invariants | Propose experiments | Expand authority or replace the stable baseline on intuition |

## Flow

```text
Idea
  -> Customer
  -> Consumer
  -> Designer
  -> Executor
  -> Stabilizer
  -> Innovator
  -> Idea (next iteration)
```

The flow is a reference, not a hard-coded organizational requirement. The protocol allows other topologies, but each edge must have an explicit `CapabilityGrant`.

## Shared invariants

1. Delivery is not verification.
2. Verification is not state acceptance.
3. State acceptance is not action authorization.
4. Action authorization is not execution.
5. State-bearing results require checked evidence.
6. The receiver owns the capability and authority ceiling.
7. Replayed event IDs are idempotent.
8. Stale state cannot overwrite newer accepted state.
9. Archived or revoked peers fail closed.
10. Both sides retain an auditable disposition receipt.
