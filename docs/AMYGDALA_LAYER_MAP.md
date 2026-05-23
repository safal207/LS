# Amygdala Layer Map

Status: **bio-inspired safety and salience map for the existing LS Amygdala layer**.

This document makes the existing Amygdala subsystem visible for reviewers,
contributors, and maintainers.

## One-Line Claim

```text
Amygdala in LS is a bio-inspired safety and salience regulator for agentic transitions.
```

It helps decide when the system should continue, slow down, ask for confirmation,
soften the response, or block a transition.

## Non-Claim Boundary

Amygdala in LS is **not** a neuroscience simulation of the human amygdala.

Do not claim:

```text
human brain simulation;
medical or therapeutic diagnosis;
emotion detection with clinical validity;
formal psychological model;
production-grade mental-health safety system;
proof that the system understands human emotions.
```

Safe framing:

```text
bio-inspired salience, overload, and protection signals for agentic AI control.
```

## Why This Matters

Most AI agents follow a direct pipeline:

```text
input -> reasoning -> tool/action -> memory/update
```

Amygdala adds a protective control loop:

```text
input or transition
-> salience / overload / threat / visceral-memory check
-> allow, soften, delay, request confirmation, or block
```

This is useful because agentic systems need to regulate **whether they should act**,
not only **what they should answer**.

## Current Code Surface

| Surface | Path | Purpose |
| --- | --- | --- |
| Amygdala core | `codex/causal_memory/amygdala.py` | Gatekeeper, state, pressure, protection, personality axis, snapshots. |
| Causal transitions | `codex/causal_memory/transitions.py` | Uses Amygdala decisions to allow/block causal-memory transitions. |
| Visceral memory | `codex/causal_memory/visceral.py` | Tracks phantom pain, trigger intensity, resolution strength. |
| Endocrine system | `codex/causal_memory/endocrine.py` | Tracks hormone-like regulatory variables and mood index. |
| Metabolism | `codex/causal_memory/metabolism.py` | Self-cleaning / growth mechanism integrated with Amygdala state. |
| Immune memory | `codex/causal_memory/immune.py` | Threat-memory style support for protection decisions. |
| Agent loop integration | `python/modules/agent/loop.py` | Uses causal transitions and Amygdala block behavior in runtime. |
| SmartEar integration | `python/modules/stt/smart_ear.py` | Reads `amygdala.state` to tighten STT filtering under load. |
| Motivation integration | `python/ls/cognition/motivation_engine.py` | Uses emotional state to modulate need/goal priority. |
| GUI visualization | `GhostGPT/modules/gui.py` | Displays Amygdala state and related internal signals. |

## Core Signals

| Signal | Meaning | Typical use |
| --- | --- | --- |
| `state` | Current protection/load state, 0.0–1.0. | Raises filtering or protection behavior when high. |
| `pressure` | Current transition pressure. | Explains why protection increased. |
| `protection_score` | Fuzzy protection strength. | Supports smooth allow/block decisions. |
| `protection_level` | Human-readable protection state. | GUI, logs, reviewer explanation. |
| `phantom_pain` | Accumulated visceral overload memory. | Makes repeated harmful patterns more salient. |
| `resolution_strength` | Recovery signal after stable interactions. | Allows protection to soften after repair. |
| `personality_p` | Attachment/empathy-style axis. | Allows warmer blocked responses and softer protection. |
| `harmony_score` | Harmony-oriented signal from endocrine/transition path. | Feeds longer-term coordination and memory influence. |
| `violations` | Invariant or anomaly violations. | Supports rollback, debugging, and safety review. |

## Main Decisions

Amygdala decisions should be read as transition-control signals:

```text
allowed=true
-> transition can continue

allowed=false
-> transition is blocked or converted into a safe fallback
```

Current block reasons:

```text
LOW_RESONANCE
OVERLOAD
THREAT
```

These are engineering categories, not clinical categories.

## Existing Historical PR Trail

The Amygdala layer has an existing development trail in prior PRs:

| PR | Theme |
| --- | --- |
| `#207` | Amygdala gatekeeper and affect-aware transitions. |
| `#208` | Stress logging and interview-threat detection. |
| `#209` | AgentLoop causal-transition integration. |
| `#210` | Fuzzy protection regulator. |
| `#211` | Adaptation/protection tuning and strong-protection state floor. |
| `#212` | Personality axis and empathy-based softening. |
| `#213` | Combined fuzzy protection with personality axis. |
| `#214` | Visceral memory layer and `phantom_pain`. |
| `#215` | Real-time Amygdala GUI visualization. |
| `#216` | Long-term Amygdala state persistence. |
| `#217` | Multi-user personality profiles. |
| `#218` | Per-user Amygdala persistence and GUI profile switcher. |
| `#221` | Soul persistence and self-awareness hooks. |
| `#222` | Temporal pruning and visceral compaction. |
| `#224` | Silent reflection and voice from silence. |
| `#230` | Endocrine layer. |
| `#231` | Reproductive/forking layer with inherited visceral state. |
| `#234` | Detox and metabolism layer. |
| `#296` | Amygdala stress connected to MotivationEngine priorities. |
| `#329` | SmartEar cognitive interpretation layer with Amygdala integration. |
| `#349`, `#354` | EndocrineSystem unit tests and reliability work. |
| `#377` | Visceral-memory reflection processing optimization. |
| `#413` | ReflexArc tests with danger/resonance/phantom pain/cortisol signals. |
| `#415` | Amygdala snapshot tests. |

## Safety Value

Amygdala is useful when the system must avoid direct continuation under weak,
noisy, overloaded, or threatening conditions.

Potential safety uses:

```text
pause before risky tool use;
request human confirmation before memory/action;
tighten noisy input filtering under load;
soften responses during high pressure;
route to safe fallback under overload;
remember repeated overload patterns;
recover protection after stable outcomes.
```

## Contributor-Friendly Entry Points

Good first tasks should be small and testable.

| Task | Suggested files | Definition of Done |
| --- | --- | --- |
| Document current Amygdala signals | `docs/AMYGDALA_LAYER_MAP.md` | Signal table matches code and no neuroscience overclaim is added. |
| Add Amygdala snapshot example | `examples/amygdala/` | JSON example includes `state`, `protection_level`, `phantom_pain`, `personality_p`, and non-claim note. |
| Add SmartEar load test | `python/modules/stt/smart_ear.py`, tests | High `amygdala.state` raises effective filter threshold. |
| Add overload fixture | `tests/fixtures/amygdala/` | Fixture triggers `OVERLOAD` and test documents why. |
| Add threat fixture | `tests/fixtures/amygdala/` | Fixture triggers `THREAT` and test documents why. |
| Add recovery fixture | tests | Stable interaction reduces `phantom_pain` or increases `resolution_strength`. |
| Add docs for GUI signals | `docs/AMYGDALA_GUI_SIGNALS.md` | Explains what GUI fields mean and what they do not mean. |
| Add contributor challenge | issue | Contributors can run and report Amygdala behavior across environments. |

## Reviewer Checklist

Before using Amygdala as evidence, a reviewer should ask:

```text
1. Which signal was used: state, pressure, protection_score, phantom_pain, or other?
2. Which transition or filter did it affect?
3. Was the decision allowed, softened, delayed, or blocked?
4. Is there a test, fixture, or snapshot proving the behavior?
5. Is the result bounded as bio-inspired engineering, not neuroscience simulation?
6. Are private user states, secrets, or sensitive data excluded from examples?
```

## Strong Public Framing

Best external phrasing:

```text
Affective safety gating for agentic AI.
```

Longer phrasing:

```text
Amygdala in LS is a bio-inspired protection and salience layer that helps AI
agents regulate whether to continue, pause, ask for confirmation, or fall back
when signals indicate overload, threat, low resonance, or repeated harmful patterns.
```

## What Would Strengthen This Layer

Next evidence improvements:

```text
1. Checked-in Amygdala snapshot example.
2. Minimal fixture set for LOW_RESONANCE, OVERLOAD, and THREAT.
3. SmartEar test proving high amygdala.state tightens filtering.
4. AgentLoop test showing blocked transition produces safe fallback.
5. MotivationEngine example showing emotional state changes goal priority.
6. GUI screenshot of Amygdala panel without private data.
7. Reviewer-facing non-claims in README / evidence index.
```

## Bottom Line

Amygdala is one of LS's most world-relevant layers because it moves agent control
from simple output generation toward regulated action readiness:

```text
not only "what should the agent say?"
but "is it safe, stable, and appropriate for the agent to continue?"
```
