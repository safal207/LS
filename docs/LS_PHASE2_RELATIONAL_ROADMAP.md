# LS Phase 2 Relational Roadmap

This document defines the next major layer for `LS` after the current risk, review, and SLA oversight stack.

The goal of `Phase 2` is to move from:

- detect
- review
- escalate

to:

- remember
- adapt
- prevent
- learn

## Phase 2.1: Relation Memory

Goal:
- retain the relational context of prior council cycles so similar situations can be recognized later

What to build:
- relation-memory artifacts derived from `relational_episode`
- compact pattern summaries:
  - tension
  - alignment
  - dominant signal
  - receiver response
  - review outcome
- lookup by recent similarity or simple heuristic buckets

Expected effect:
- `LS` can treat the current cycle as part of a pattern, not as an isolated event

## Phase 2.2: Relation-Aware Routing

Goal:
- let relational context influence route selection before the outcome is produced

What to build:
- route selection rules that consider:
  - prior tension
  - prior low alignment
  - prior poor receiver resonance
  - repeated escalations for similar cases
- route modes such as:
  - `continue_current_route`
  - `validate_current_route`
  - `repair_then_reroute`
  - `freeze_and_escalate`

Expected effect:
- the system chooses safer or more evidence-heavy routes earlier

## Phase 2.3: Preemptive Safety Modes

Goal:
- switch system posture before a failure or escalation happens

Modes:
- `normal`
- `watch`
- `repair`
- `escalate`
- future optional extensions:
  - `evidence_first`
  - `human_first`
  - `freeze`

Expected effect:
- safety becomes proactive rather than purely reactive

## Phase 2.4: Relational Policy Engine

Goal:
- centralize relational safety decisions in an explicit policy layer

Example rules:
- if `tension` is high and `alignment` is low, move to `repair`
- if `receiver_resonance` is low, require stronger review
- if repeated escalation crosses a threshold, freeze the route
- if the same pattern has a stable history of successful review, relax to `normal_review`

Expected effect:
- route and approval decisions become easier to explain, test, and audit

## Phase 2.5: Relational Learning

Goal:
- learn from completed council cycles and review outcomes

What to build:
- pattern summaries of:
  - approved cycles
  - rejected cycles
  - incident-producing cycles
  - repeated escalation paths
- heuristics that can refine:
  - route recommendations
  - posture recommendations
  - review thresholds

Expected effect:
- `LS` improves future council behavior from prior oversight outcomes

## Summary

`Phase 2` turns the relational layer from passive analytics into active control:

- memory
- routing
- posture
- policy
- learning

The main transition is:

- from `notice and react`
- to `anticipate and adapt`
