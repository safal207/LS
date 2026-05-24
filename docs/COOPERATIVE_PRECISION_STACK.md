# Cooperative Precision Stack

Status: **architecture map**.

The Cooperative Precision Stack is the six-layer map for turning model work into
repeatable, auditable, and reflective route memory.

It keeps the thesis narrow:

```text
models do not become magically smarter
the cooperative network becomes more precise
```

## Six Paths

| Path | Role | Question |
| --- | --- | --- |
| TTM DB | Immutable trace | What happened and which transition became irreversible? |
| LiminalDB | Adaptive living memory | Which routes should grow, decay, synchronize, or be replayed? |
| PythiaLabs | Evidence/action gate | Is this route or action backed by enough evidence to proceed? |
| LS | Cooperative route scoring | Which role route made the task more precise? |
| RINSE | Reflective interpretation | What did this experience mean and what should be tried next? |
| Human Operator | Goal, consent, meaning | What is the real goal, boundary, consent, and acceptance test? |

## Flow

```text
task
-> LS route proposal
-> TTM immutable trace
-> Pythia evidence/action gate
-> LiminalDB adaptive route memory
-> RINSE reflective interpretation
-> human boundary and next route decision
```

## Ant-Colony Analogy

Use the analogy internally, but keep public claims precise:

```text
agent/model      -> ant
role             -> ant function
task             -> food/search target
route            -> path
reward           -> pheromone
evidence         -> proof that food was real
TTM trace        -> irreversible footprint
LiminalDB memory -> living pheromone field
RINSE            -> colony reflection over experience
human operator   -> colony goal and safety boundary
```

This does not mean LS is a biological system. It means LS can preserve, score,
weaken, and repeat routes in a way that resembles cooperative trail formation.

## Precision Question

The stack should answer:

```text
How much more precise did the network become than a single answer?
```

The first proxy is:

```text
network_precision_score =
  route_reward
+ evidence_gate support
+ immutable_trace support
+ adaptive_memory support
+ reflective_clarity
+ human_boundary support
+ depth_fit
```

Run:

```bash
python scripts/run_network_precision_gain_demo.py
python scripts/run_network_precision_gain_demo.py --json
```

## Boundary

The first score is a deterministic proxy. It combines an already measured route
reward with modeled support from the surrounding stack.

It is not:

- a proof of general intelligence;
- a production-readiness claim;
- a claim that every layer is fully integrated today;
- a formal economic theorem.

It is useful because it gives the project a clear engineering question:

```text
Which layer increased route precision, and can we reproduce that gain?
```
