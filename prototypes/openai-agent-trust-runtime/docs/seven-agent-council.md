# Seven-Agent Council Reference Workflow

The council turns one project brief into seven evidence-linked artifacts.

## Stage contract

1. **Idea Agent** produces a problem and value hypothesis with a measurable outcome.
2. **Customer Agent** defines scope, constraints, non-goals, and acceptance criteria.
3. **Consumer Agent** describes the user journey, friction, trust needs, and adoption threshold.
4. **Designer Agent** produces components, data flow, invariants, trade-offs, and test seams.
5. **Executor Agent** implements the bounded design and returns evidence and limitations.
6. **Stabilizer Agent** runs negative tests and issues a fail-closed stability verdict.
7. **Innovator Agent** proposes a falsifiable 10x experiment while preserving all accepted invariants.

Each stage receives its own `DispatchReceipt`, submits an evidence-bound `ResultReceipt`, emits a `CrossThreadEvent`, and receives a `DecisionReceipt` from the next thread.

## Offline demonstration

```bash
ls-cross-thread-demo \
  --brief 'Build a safe protocol for durable AI-agent thread coordination.'
```

Expected properties:

- seven stages;
- seven accepted event dispositions;
- valid trust ledger;
- valid cross-thread audit chain;
- no external effect execution.

## Live SDK profiles

`build_openai_agents_team()` creates the seven OpenAI Agents SDK profiles and sequential handoffs without making an API call. The deterministic runtime remains the source of authority and evidence policy; model output alone never grants permission.
