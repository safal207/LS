# Deterministic Workflow Orchestrator

Status: **reference implementation for issue #592**

The LS Trusted Runtime includes a local provider-neutral orchestrator that turns
a task envelope into a bounded multi-role workflow without calling a model or
depending on an agent framework.

## Core interface

```python
from modules.trusted_runtime import DeterministicWorkflowOrchestrator

orchestrator = DeterministicWorkflowOrchestrator()
plan = orchestrator.create_plan(task, context)
plan = orchestrator.assign_roles(plan, available_capabilities)
plan = orchestrator.revise_plan(plan, results, reason)
trail = orchestrator.revision_trail(plan)
```

The implementation conforms to `WorkflowOrchestrator`, so another planner can
replace it later without changing the Trusted Runtime contracts.

## Supported roles

| Role | Capability |
| --- | --- |
| `researcher` | `research` |
| `implementer` | `implementation` |
| `critic` | `risk_critique` |
| `verifier` | `evidence_verification` |
| `summarizer` | `summarization` |

Actors may be selected by role name or capability name through
`available_capabilities`. Missing actors fall back to deterministic local role
identifiers such as `local:verifier`.

## Deterministic planning

The orchestrator does not generate timestamps, UUIDs, or provider output.
It uses values already present in the task envelope and stable ordered IDs:

```text
step-01-researcher
step-02-implementer
step-03-critic
```

The same task and context therefore produce the same `WorkflowPlan`.

## Causal ordering

The first sub-task descends from the root task. Each later sub-task descends
from and depends on the preceding step:

```text
task
-> step-01-researcher
-> step-02-implementer
-> step-03-critic
-> step-04-verifier
-> step-05-summarizer
```

This keeps every sub-task connected to the original intent while satisfying the
append-only causal ordering rules of the contract layer.

## Bounded decomposition

`OrchestratorConfig.max_steps` limits how many sub-tasks may enter one plan.
Callers may use the built-in simple or multi-role workflows, or provide explicit
bounded sub-task specifications in `context["subtasks"]`.

## Recursive revision

`OrchestratorConfig.max_depth` limits recursive revisions. Each accepted
revision:

1. increments `task.metadata["orchestration_depth"]`;
2. appends one bounded revision step;
3. carries forward result and evidence references;
4. appends a `PLAN_REVISED` event to the Cognitive Trail.

A revision beyond the configured depth raises `OrchestrationDepthError` before
any plan or trail mutation occurs.

## Explicit non-goals

- no Sakana Fugu dependency or equivalence claim;
- no CrewAI, LangGraph, AutoGen, OpenAI Agents, or provider SDK dependency;
- no live model calls;
- no hidden chain-of-thought storage;
- no execution permission or side effect.

The orchestrator produces a proposal. Evidence gates and execution control
remain separate downstream responsibilities.

## Validation

```bash
python -m pip install jsonschema pytest
PYTHONPATH=.:python:python/modules \
  python -m pytest python/tests/test_trusted_runtime_orchestrator.py
```

Fixtures cover simple, multi-role, and recursive workflows under:

```text
python/tests/fixtures/trusted-runtime/orchestrator/
```
