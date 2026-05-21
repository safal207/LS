# -*- coding: utf-8 -*-
"""BodyAwareCopilot — Stage 8 of the SmartEar cognitive pipeline.

Assembles the final, ready-to-use copilot output for each question cycle:

  * ``BodyCues``   — pause, breath, intonation, micro_expression
  * ``pre_prompt`` — one-line trigger visible to the user in < 0.3 s
  * ``final_prompt`` — full LLM system-prompt block (pre-assembled, replaces
                       the piecemeal construction in AgentLoop)
  * Full structured JSON output matching the spec:

    {
      "cycle_id": "...",
      "pre_prompt": "🧠 Сейчас: объясни причину + добавь кейс + пауза 1.2 с",
      "anchor_context": [...],
      "empathy_cues": {
        "pause": 1.2,
        "breath": "inhale",
        "intonation": "slow + calm",
        "micro_expression": ["smile", "nod"]
      },
      "operator_profile": {...},
      "final_prompt": "...full LLM block..."
    }

Design goals
------------
* Zero hard dependencies — stateless, no I/O, no ML.
* < 0.5 ms per call.
* Thread-safe — pure function, no shared mutable state.
* ``final_prompt`` is the single source of truth for both the UI overlay
  and the LLM system-prompt injection.  AgentLoop uses it directly;
  if Stage 8 is unavailable the loop falls back to its own piecemeal build.

Usage::

    copilot = BodyAwareCopilot()
    item = copilot.process(item)         # item["_copilot_output"] populated
    output = item["_copilot_output"]
    # output["final_prompt"]  → inject into LLM
    # output["empathy_cues"]  → send to UI overlay
    # output["pre_prompt"]    → show on screen first
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# BodyCues
# ---------------------------------------------------------------------------

@dataclass
class BodyCues:
    """Physical / physiological coaching signals for one question cycle.

    Attributes:
        pause:            Seconds to pause *before* the first word (0 = no pause).
        breath:           "inhale" | "exhale" | "none" — what to do during pause.
        intonation:       Short label for speaking style shown in UI overlay.
        micro_expression: Body-language cues as short imperative strings.
    """
    pause:            float      = 0.5
    breath:           str        = "none"
    intonation:       str        = "steady"
    micro_expression: List[str]  = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pause":            round(self.pause, 2),
            "breath":           self.breath,
            "intonation":       self.intonation,
            "micro_expression": list(self.micro_expression),
        }

    def format_ui_line(self) -> str:
        """Single line for UI overlay, readable in 0.3 s."""
        parts = [f"⏸ {self.pause}с"]
        if self.breath != "none":
            parts.append(f"→ {self.breath}")
        parts.append(f"→ {self.intonation}")
        if self.micro_expression:
            parts.append("→ " + ", ".join(self.micro_expression))
        return "  ".join(parts)


# ---------------------------------------------------------------------------
# CopilotOutput
# ---------------------------------------------------------------------------

@dataclass
class CopilotOutput:
    """Complete output of one BodyAwareCopilot cycle.

    This is the single JSON object sent to both the UI overlay and AgentLoop.
    """
    cycle_id:            str
    pre_prompt:          str                  # ← shown on screen first
    anchor_context:      List[str]
    empathy_cues:        BodyCues
    operator_profile: dict
    final_prompt:        str                  # ← injected into LLM system prompt
    # internal metadata
    intervention_level:  str  = "low"         # low | medium | high
    active_rules:        List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cycle_id":            self.cycle_id,
            "pre_prompt":          self.pre_prompt,
            "anchor_context":      self.anchor_context,
            "empathy_cues":        self.empathy_cues.to_dict(),
            "operator_profile": self.operator_profile,
            "operator_profile":    self.operator_profile,
            "final_prompt":        self.final_prompt,
            "intervention_level":  self.intervention_level,
            "active_rules":        self.active_rules,
        }


# ---------------------------------------------------------------------------
# Body-cue rule engine
# ---------------------------------------------------------------------------

def _build_body_cues(
    pressure: float,
    tone: str,
    answer_type: str,
    interrupted: bool,
) -> tuple[BodyCues, str, list[str]]:
    """Return (BodyCues, intervention_level, active_rules)."""
    pause       = 0.5
    breath      = "none"
    intonation  = "steady"
    expressions: List[str] = []
    rules:       List[str] = []
    level       = "low"

    # ---- high pressure ----
    if pressure >= 0.80:
        level      = "high"
        pause      = 1.5
        breath     = "inhale"
        intonation = "slow + calm"
        expressions = ["smile", "open_posture"]
        rules.append("high_pressure_body")

    elif pressure >= 0.60:
        level      = "medium"
        pause      = 1.0
        breath     = "inhale"
        intonation = "calm"
        expressions = ["nod"]
        rules.append("medium_pressure_body")

    # ---- tone overrides ----
    if tone == "assertive":
        intonation = "confident + direct"
        if "eye_contact" not in expressions:
            expressions.append("eye_contact")
        rules.append("assertive_tone")

    elif tone == "grounded":
        intonation = "warm + grounded"
        if "smile" not in expressions:
            expressions.append("smile")
        rules.append("grounded_tone")

    elif tone == "brief":
        pause  = max(pause, 0.3)
        breath = "none"
        intonation = "steady + brief"
        rules.append("brief_tone")

    elif tone == "warm":
        intonation = "slow + warm"
        if "smile" not in expressions:
            expressions.append("smile")
        if "nod" not in expressions:
            expressions.append("nod")
        rules.append("warm_tone")

    # ---- answer type specialisation ----
    if answer_type == "experiential":
        if "eye_contact" not in expressions:
            expressions.append("eye_contact")
        rules.append("experiential_eye_contact")

    elif answer_type == "defense":
        intonation = "confident + steady"
        pause = max(pause, 0.8)
        rules.append("defense_posture")

    # ---- interrupted by counterparty → cut the pause ----
    if interrupted:
        pause  = 0.3
        breath = "none"
        rules.append("interrupted_brief_pause")

    return BodyCues(pause=pause, breath=breath,
                    intonation=intonation, micro_expression=expressions), level, rules


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def _build_final_prompt(
    strategy:   dict,
    anchor_ctx: List[str],
    counterparty: dict,
    empathy:    dict,
    cues:       BodyCues,
) -> str:
    """Assemble the complete LLM system-prompt block from all pipeline outputs."""
    sections: List[str] = []

    # 1 — Cognitive micro-trigger (top, most visible)
    micro_trigger = strategy.get("micro_trigger", "")
    if micro_trigger:
        cue_line = cues.format_ui_line()
        sections.append(f"🧠 Сейчас: {micro_trigger}\n{cue_line}")

    # 2 — Strategy block
    answer_type = strategy.get("answer_type", "")
    pressure_label = strategy.get("pressure", "")
    hints = strategy.get("hints") or []
    if hints:
        hints_text = "\n".join(f"- {h}" for h in hints)
        sections.append(
            f"Стратегия: {answer_type}  |  Давление: {pressure_label}\n"
            f"Подсказки:\n{hints_text}"
        )

    # 3 — Anchor context
    if anchor_ctx:
        force = answer_type == "experiential"
        label = "ОБЯЗАТЕЛЬНО используй этот опыт:" if force else "Используй контекст:"
        anchor_lines = "\n".join(f"- {x}" for x in anchor_ctx)
        sections.append(f"{label}\n{anchor_lines}")

    # 4 — OperatorSessioner profile summary (after ≥ 2 questions)
    if counterparty.get("questions_seen", 0) >= 2:
        p = counterparty.get("pressure_level", 0.0)
        flags = []
        if counterparty.get("prefers_examples"):
            flags.append("любит кейсы")
        if counterparty.get("prefers_reasoning"):
            flags.append("любит рассуждения")
        if counterparty.get("prefers_theory"):
            flags.append("любит теорию")
        if counterparty.get("interrupt_count", 0) > 0:
            flags.append("перебивает")
        if flags:
            sections.append(f"Контрагент (давление {p:.0%}): {', '.join(flags)}.")

    # 5 — Empathy & negotiation
    tone_trigger  = empathy.get("tone_trigger", "")
    empathy_hints = empathy.get("hints") or []
    nego_move     = empathy.get("negotiation_move")
    if tone_trigger or empathy_hints:
        emp_parts: List[str] = []
        if tone_trigger:
            emp_parts.append(f"💬 Тон: {tone_trigger}")
        if empathy_hints:
            emp_parts.append("Эмпатия:\n" + "\n".join(f"- {h}" for h in empathy_hints))
        if nego_move:
            emp_parts.append(f'Открой с: "{nego_move}"')
        sections.append("\n".join(emp_parts))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# BodyAwareCopilot
# ---------------------------------------------------------------------------

class BodyAwareCopilot:
    """Stage 8: assemble the complete copilot output for one question cycle.

    Reads all prior stage outputs from *item* and populates
    ``item["_copilot_output"]`` with a :class:`CopilotOutput` dict.

    Always returns *item* — never raises.
    """

    def process(self, item: dict) -> dict:
        try:
            output = self._build(item)
        except Exception:
            output = CopilotOutput(
                cycle_id=str(uuid.uuid4())[:8],
                pre_prompt="🧠 Сейчас: ответь кратко",
                anchor_context=[],
                empathy_cues=BodyCues(),
                operator_profile={},
                final_prompt="ответь по существу",
            )
        output_dict = output.to_dict()
        item["_copilot_output"] = dict(output_dict)
        item["_operator_response_output"] = dict(output_dict)
        return item

    # ------------------------------------------------------------------

    def _build(self, item: dict) -> CopilotOutput:
        strategy    = item.get("_why_strategy")    or {}
        empathy     = item.get("_empathy_result")  or {}
        counterparty = item.get("_operator_profile") or {}
        anchor_ctx  = item.get("_anchor_context")  or []

        pressure    = empathy.get("pressure_score", 0.0)
        tone        = empathy.get("tone", "calm")
        answer_type = strategy.get("answer_type", "short")
        interrupted = counterparty.get("interrupt_count", 0) > 0
        micro_trigger = strategy.get("micro_trigger", "ответь кратко")

        cues, level, rules = _build_body_cues(
            pressure=pressure,
            tone=tone,
            answer_type=answer_type,
            interrupted=interrupted,
        )

        # pre_prompt = micro_trigger + cue summary (one line, UI overlay)
        pre_prompt = f"🧠 Сейчас: {micro_trigger}  {cues.format_ui_line()}"

        final_prompt = _build_final_prompt(
            strategy=strategy,
            anchor_ctx=list(anchor_ctx),
            counterparty=counterparty,
            empathy=empathy,
            cues=cues,
        )

        return CopilotOutput(
            cycle_id=str(uuid.uuid4())[:8],
            pre_prompt=pre_prompt,
            anchor_context=list(anchor_ctx),
            empathy_cues=cues,
            operator_profile=dict(counterparty),
            final_prompt=final_prompt,
            intervention_level=level,
            active_rules=rules + (empathy.get("active_rules") or []),
        )
