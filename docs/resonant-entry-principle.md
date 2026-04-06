# Resonant Entry Principle (LS)

## Core thesis

Meaningful contact starts through a charged fragment, not full context.
The system should detect the most *alive* and *ethically safe* entry node first,
then expand context progressively.

> Do not load the whole. Find the live entry point. Build depth through it.

## Resonant Entry Module (REM)

`python/ls/cognition/resonant_entry.py`

### Purpose

Before advising, planning, persuading, analyzing, or retrieving memory,
REM identifies **where contact should start now**.

### Supported node types

- `interest_node`
- `pain_node`
- `goal_node`
- `risk_node`
- `conflict_node`
- `unfinished_node`
- `identity_node`
- `care_node`
- `novelty_node`

### Pipeline

1. **Signal collection**: repeated words, emotional density, tension, unfinished loops, values/fears.
2. **Resonance scoring**: intensity, relevance, repetition, openness.
3. **Entry-node selection**: pick not the loudest node, but the safest productive node.
4. **Soft contact**: formulate first response style and movement.
5. **Feedback check**: verify openness before deepening.
6. **Progressive deepening**: expand context around the selected node.

### Ethical constraint

REM includes a safety multiplier and must not optimize for manipulation.

- Do not exploit trauma or panic markers.
- Do not force contact through fear if safer nodes are available.
- Good resonance increases clarity and safety.
- Bad resonance increases dependence and confusion.

## Public output schema

REM returns structured output via `ResonantEntryResult`:

- `entry_node_type`
- `entry_node_label`
- `resonance_score`
- `openness_estimate`
- `emotional_charge`
- `task_relevance`
- `identity_proximity`
- `recommended_entry_style`
- `avoid_styles`
- `next_contact_move`
- `confidence`
- `supporting_signals`
- `contra_signals`
- `deepening_risk`

## Example

Input utterance:

> "Хочу сделать стартап, но распыляюсь и устаю."

Possible entry:

- `entry_node_type = goal_node`
- `recommended_entry_style = supportive_precision`
- `next_contact_move = connect immediate blocker to long-term ambition`

This keeps the entry focused, safe, and actionable.
