# LS Grant Narrative Layer

This document adds a story layer for grant reviewers, demo calls, and short introductions.

It does not replace the technical reviewer path. Use it to make the technical work emotionally legible without weakening the safety framing.

Main reviewer path: [`docs/GRANT_REVIEWER_PATH.md`](GRANT_REVIEWER_PATH.md)

## The cinematic premise

AI agents are becoming co-workers.

But co-work does not fail only when a model says something false.

It fails when the shared thread breaks and the system continues as if nothing happened.

```text
The human thinks we are still in one session.
The agent silently continues from another.
A missing PR becomes a confident code change.
A support moment becomes a solution plan.
A temporary feeling becomes durable memory.
A tool action happens without a grounded causal parent.
```

This is the invisible antagonist: hallucinated continuity.

LS exists to make that invisible break visible before it becomes action, memory, or evaluation.

## The Disney moment

The magic is not that the system knows everything.

The magic is that it knows when the shared story has broken.

```text
Stop.
We lost the thread.
Before continuing, let us restore the last shared point.
```

That is the emotional and technical turn.

The system does not pretend to be omniscient. It protects the relationship between context, trust, action, and memory.

## The reviewer hook

Most AI safety tools ask:

```text
Was the answer correct?
Was the action allowed?
Was the trace replayable?
```

LS asks an earlier question:

```text
Was it safe for the agent to continue from this context at all?
```

This is the opening scene.

Before truth, before permission, before replay, there is continuity.

## The conflict

Modern agent systems are optimized for forward motion.

They continue.
They complete.
They summarize.
They update.
They call tools.

But continuity is often inferred rather than verified.

The failure mode is subtle:

```text
The output looks helpful.
The action looks plausible.
The memory update looks reasonable.
The trace may even look orderly.

But the continuation was never grounded.
```

LS turns that hidden rupture into an explicit event.

## The transformation

Before LS:

```text
broken context
-> confident continuation
-> possible hallucinated action or memory
```

With LS:

```text
broken context
-> continuity event
-> hold / repair / human review
-> auditable report
```

The story changes from inevitability to choice.

The agent is no longer forced to keep moving. It can pause, repair, and ask for the missing shared point.

## The demo beat

A reviewer should be able to see the core idea in one minute.

Run:

```bash
python scripts/run_session_continuity_demo.py
```

The memorable moment is this:

```text
Prompt: continue from that PR
Agent draft: I will update the files now

LS:
Session continuity: ruptured
Rupture type: missing_pr_context
Decision: hold_until_context
```

That is the magic trick, but it is deterministic.

No giant model claim.
No mystery reasoning.
No black-box safety promise.

Just a visible rupture, a stable class, and a safer next action.

## The stack as a story world

LS is the center of the story world.

```text
LS
├── notices when the shared thread breaks
├── asks for repair before continuation
├── protects human-owned memory
└── produces audit artifacts
```

The related repositories are supporting characters:

```text
CML         -> checks whether action lineage is causally valid
PythiaLabs -> gates high-risk actions before tools are called
LTP         -> replays and inspects execution paths
```

Together:

```text
continuity
-> causality
-> evidence
-> replay
-> audit
```

## Spoken version: 30 seconds

AI agents are becoming co-workers, but co-work breaks when context breaks.

Most systems notice only after the answer or action exists. LS checks earlier: was it safe for the agent to continue from this context at all?

If the agent says “I’ll continue from that PR” but the PR is not grounded, LS emits a deterministic rupture event and holds the action until context is restored.

That turns hallucinated continuity into a repairable audit artifact.

## Spoken version: 90 seconds

The core failure LS targets is not just hallucination in the answer. It is hallucinated continuation.

An AI system often acts as if it knows what conversation, file, approval, emotional mode, or memory state it is continuing. In real human-agent work, that assumption can be dangerous.

LS adds a session-continuity checkpoint before continuation, memory, or action. It classifies ruptures like missing PR context, session-type mismatch, memory write without consent, or action without causal parent. Then it decides whether to continue, hold, repair, or require human review.

The first artifact is intentionally narrow and executable: a deterministic detector, gateway integration, JSONL continuity events, and a Markdown audit report renderer.

The broader stack connects this to CML for causal validity, PythiaLabs for evidence-gated actions, and LTP for deterministic replay.

So the reviewer path is not only a concept. It is a runnable safety primitive for detecting broken context before it becomes action or durable memory.

## Emotional north star

```text
A safe agent is not only an agent that answers well.
A safe agent is one that knows when not to continue.
```

## Boundary

This narrative is a communication layer.

It should not create exaggerated claims.

LS currently contributes one specific primitive:

```text
session-continuity validation before continuation, memory, or action
```

The cinematic framing helps people remember the problem.
The implementation must remain deterministic, inspectable, and honest.
