import json
import logging
import re
import copy
import time
from collections import deque
from typing import Protocol, List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from .cte import CognitiveTimelineEngine

logger = logging.getLogger("CaPU_v3")

# Constants
HISTORY_BUFFER_SIZE = 10
MEMORY_SEARCH_LIMIT = 3
TRUNCATE_LIMIT_ANSWER = 200
TRUNCATE_LIMIT_HISTORY = 300

class MemoryInterface(Protocol):
    def search_similar(self, query: str, k: int) -> List[Dict[str, Any]]:
        ...

@dataclass
class CognitiveContext:
    # Base v2 layers
    facts: List[str]
    logic: List[Dict[str, Any]]
    memory: List[Dict[str, Any]]
    history: List[Dict[str, str]]

    # CaPU v3 Cognitive Layers
    intent: Optional[Dict[str, Any]] = None
    target: Optional[Dict[str, Any]] = None
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    durations: List[Dict[str, Any]] = field(default_factory=list)
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    consequences: List[Dict[str, Any]] = field(default_factory=list)

class CaPUv3:
    """
    CaPU v3: Cognitive Processing Unit with Timeline Engine.
    Implements a 7-layer cognitive architecture.
    """
    def __init__(self, memory_module: Optional[MemoryInterface] = None):
        self.memory = memory_module

        # Base Layers (Persistent/Session)
        self.facts: Dict[str, str] = {}
        self.logic: List[Dict[str, Any]] = []
        self.history = deque(maxlen=HISTORY_BUFFER_SIZE)

        # Cognitive Layers (Session/Working Memory)
        self._intent: Optional[Dict[str, Any]] = None
        self._target: Optional[Dict[str, Any]] = None
        self._procedures: List[Dict[str, Any]] = []
        self._durations: List[Dict[str, Any]] = []
        self._predictions: List[Dict[str, Any]] = []
        self._consequences: List[Dict[str, Any]] = []

        # CTE: Liminal transitions + insights
        self._cte = CognitiveTimelineEngine()

        self._loaded = False
        self.base_dir = self._resolve_data_dir()

    def _resolve_data_dir(self) -> Path:
        """Robustly find the data directory."""
        cwd = Path.cwd()
        candidates = [
            Path(__file__).resolve().parent.parent.parent.parent / "data",
            cwd / "data",
            cwd.parent / "data",
        ]
        for path in candidates:
            if path.exists() and path.is_dir():
                return path
        return Path("data")

    def _ensure_loaded(self):
        if not self._loaded:
            self._load_dmp("facts.json")
            self._load_cml("logic.json")
            self._loaded = True

    def _load_dmp(self, filename: str):
        path = self.base_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.facts = data.get("facts", {})
                        logger.info(f"🧠 DMP loaded from {path}")
                    else:
                        logger.warning(f"⚠️ Invalid DMP structure in {path}")
            except Exception as e:
                logger.error(f"❌ Error loading DMP: {e}")

    def _load_cml(self, filename: str):
        path = self.base_dir / filename
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.logic = data
                        logger.info(f"📐 CML loaded from {path}")
                    else:
                        logger.warning(f"⚠️ Invalid CML structure in {path}")
            except Exception as e:
                logger.error(f"❌ Error loading CML: {e}")

    # --- v3 Cognitive Interface ---

    def store_intent(self, intent: str, context: str):
        """Layer 1: Intent Memory (Why?)"""
        self._intent = {
            "intent": intent,
            "context": context,
            "timestamp": datetime.now().isoformat()
        }

    def store_target(self, for_whom: str, reason: str):
        """Layer 2: Target Memory (Who?)"""
        self._target = {
            "for_whom": for_whom,
            "reason": reason
        }

    def store_procedure(self, task: str, steps: List[str]):
        """Layer 3: Procedural Memory (How?)"""
        self._procedures.append({
            "task": task,
            "steps": steps,
            "timestamp": datetime.now().isoformat()
        })

    def store_duration(self, event: str, duration_sec: float):
        """Layer 4: Duration Memory (How Long?)"""
        self._durations.append({
            "event": event,
            "duration_sec": duration_sec
        })

    def store_prediction(self, condition: str, prediction: str, confidence: float):
        """Layer 5: Predictive Memory (How Soon?)"""
        self._predictions.append({
            "condition": condition,
            "prediction": prediction,
            "confidence": confidence
        })

    def store_consequence(self, if_cond: str, then_result: str, severity: str):
        """Layer 6: Consequence Engine (What If?)"""
        self._consequences.append({
            "if": if_cond,
            "then": then_result,
            "severity": severity
        })

    # --- v3.1 CTE Interface (Liminal Transitions) ---

    def commit_transition(self, decision: str, alternatives: Optional[List[str]] = None,
                          commitment: float = 0.9) -> str:
        """
        Wrapper for CTE: commits a choice (liminal anchor).
        """
        return self._cte.commit_transition(decision, alternatives, commitment)

    def register_outcome(self, content: str, outcome_type: str = "insight") -> Optional[str]:
        """
        Wrapper for CTE: registers an outcome (insight/conflict).
        """
        return self._cte.register_outcome(content, outcome_type)

    def update_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    # --- Engine Core ---

    def _matches_query(self, key: str, q_lower: str) -> bool:
        key_lower = key.lower()
        try:
            pattern = rf'\b{re.escape(key_lower)}\b'
            return bool(re.search(pattern, q_lower))
        except re.error:
            return key_lower in q_lower

    def build_cognitive_context(self, query: str) -> CognitiveContext:
        self._ensure_loaded()
        q_lower = query.lower()

        # 1. Facts (DMP)
        facts = [f"{k}: {v}" for k, v in self.facts.items() if self._matches_query(k, q_lower)]

        # 2. Logic (CML)
        triggers = ["why", "reason", "почему", "зачем", "tradeoff", "decision", "выбор"]
        logic: List[Dict[str, Any]] = []
        if any(t in q_lower for t in triggers):
            for item in self.logic:
                keywords = item.get("keywords", [])
                if any(self._matches_query(k, q_lower) for k in keywords):
                    logic.append(item)

        # 3. Dynamic Memory (Episodic)
        memory: List[Dict[str, Any]] = []
        if self.memory:
            try:
                raw = self.memory.search_similar(query, k=MEMORY_SEARCH_LIMIT)
                if isinstance(raw, list):
                    def score_of(x: Dict[str, Any]) -> float:
                        try:
                            return float(x.get("score", 0) or 0)
                        except (TypeError, ValueError):
                            return 0.0

                    raw_sorted = sorted(raw, key=score_of, reverse=True)
                    memory = copy.deepcopy(raw_sorted)
            except Exception as e:
                logger.warning(f"⚠️ Memory error: {e}")

        return CognitiveContext(
            facts=facts,
            logic=logic,
            memory=memory,
            history=list(self.history),
            intent=self._intent,
            target=self._target,
            procedures=self._procedures[-3:],  # Last 3
            durations=self._durations[-3:],    # Last 3
            predictions=self._predictions[-3:], # Last 3
            consequences=self._consequences[-3:] # Last 3
        )

    def render_cognitive_prompt(self, query: str, ctx: CognitiveContext) -> str:
        """
        Cognitive Timeline Engine (CTE).
        Organizes context into:
        1. Meta-Cognition (Intent, Target)
        2. Past (History, Durations, Memories)
        3. Present (Context: Facts, Logic)
        4. Future (Procedures, Predictions, Consequences)
        """
        sections: List[str] = []

        # --- 1. META-COGNITION ---
        meta_section = []
        if ctx.intent:
            meta_section.append(f"🧠 INTENT: {ctx.intent['intent']} (Context: {ctx.intent['context']})")
        if ctx.target:
            meta_section.append(f"🎯 TARGET: {ctx.target['for_whom']} (Reason: {ctx.target['reason']})")

        # CTE snapshot (Liminal Anchors + Insights)
        cte_summary = self._cte.export_summary()
        if "active_anchor" in cte_summary:
            a = cte_summary["active_anchor"]
            meta_section.append(
                f"🔒 ACTIVE CHOICE: {a['decision']} (commitment={a['commitment']:.2f}, status={a['status']})"
            )
        if "last_outcome" in cte_summary:
            o = cte_summary["last_outcome"]
            meta_section.append(
                f"💡 LAST OUTCOME: {o['content']} (type={o['type']})"
            )

        if meta_section:
            sections.append("### META-COGNITION ###\n" + "\n".join(meta_section))

        # --- 2. PAST (Timeline) ---
        past_section = []

        # History
        if ctx.history:
            past_section.append(
                "💬 RECENT HISTORY:\n" +
                "\n".join([f"{m['role'].upper()}: {m['content'][:TRUNCATE_LIMIT_HISTORY]}" for m in ctx.history])
            )

        # Episodic Memory
        if ctx.memory:
            snippets = []
            for m in ctx.memory:
                q = m.get("question") or m.get("q") or "?"
                a = m.get("answer") or m.get("a") or ""
                a_short = (a[:TRUNCATE_LIMIT_ANSWER] + "...") if len(a) > TRUNCATE_LIMIT_ANSWER else a
                snippets.append(f"• Q: {q} | A: {a_short}")
            past_section.append("📂 EPISODIC RECALL:\n" + "\n".join(snippets))

        # Durations
        if ctx.durations:
            dur_lines = [f"• {d['event']}: {d['duration_sec']}s" for d in ctx.durations]
            past_section.append("⏳ TIME TRACKING:\n" + "\n".join(dur_lines))

        if past_section:
            sections.append("### PAST TIMELINE ###\n" + "\n\n".join(past_section))

        # --- 3. PRESENT (Knowledge) ---
        present_section = []
        if ctx.facts:
            present_section.append("📚 RELEVANT FACTS (DMP):\n" + "\n".join(ctx.facts))
        if ctx.logic:
            present_section.append(
                "📐 LOGIC PATTERNS (CML):\n" +
                "\n".join([f"⚙️ {i.get('decision')} (Reason: {i.get('reason')})" for i in ctx.logic])
            )

        if present_section:
            sections.append("### PRESENT CONTEXT ###\n" + "\n\n".join(present_section))

        # --- 4. FUTURE (Planning) ---
        future_section = []
        if ctx.procedures:
            proc_lines = []
            for p in ctx.procedures:
                steps_str = " -> ".join(p['steps'])
                proc_lines.append(f"🛠 {p['task']}: {steps_str}")
            future_section.append("🛠 ACTIVE PROCEDURES:\n" + "\n".join(proc_lines))

        if ctx.predictions:
            pred_lines = [f"🔮 {p['condition']} -> {p['prediction']} ({p['confidence']*100:.0f}%)" for p in ctx.predictions]
            future_section.append("🔮 PREDICTIONS:\n" + "\n".join(pred_lines))

        if ctx.consequences:
            cons_lines = [f"⚠️ IF {c['if']} THEN {c['then']} (Severity: {c['severity']})" for c in ctx.consequences]
            future_section.append("⚠️ CONSEQUENCE ANALYSIS:\n" + "\n".join(cons_lines))

        if future_section:
            sections.append("### FUTURE PROJECTIONS ###\n" + "\n\n".join(future_section))

        # Final Assembly
        system_msg = "🚀 INSTRUCTION: You are CaPU v3. Use the provided Cognitive Timeline to reason effectively. Maintain the timeline continuity."

        final_prompt = (
            f"{system_msg}\n\n" +
            "\n\n---\n\n".join(sections) +
            f"\n\n❓ CURRENT QUERY: {query}"
        )
        return final_prompt

    def construct_prompt(self, query: str) -> str:
        """Backward compatibility wrapper."""
        ctx = self.build_cognitive_context(query)
        return self.render_cognitive_prompt(query, ctx)
