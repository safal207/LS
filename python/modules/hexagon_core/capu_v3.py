import json
import logging
import re
import copy
import time
from collections import deque
from typing import Protocol, List, Optional, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from .cte import CognitiveTimelineEngine
from .missionstate import MissionState
from .homeostasis import HomeostasisMonitor
from .compression import ActiveCompressionEngine
from .belief_system import BeliefLifecycleManager, Convict

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
    CaPU v3.1: Cognitive Processing Unit with Timeline Engine & Mission State.
    Implements a 7-layer cognitive architecture with cold storage and prioritization.
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

        # Phase 2: Convict Dynamics (Belief System)
        self.lifecycle = BeliefLifecycleManager()

        # Mission State: Goals, Values, Priorities
        self.mission = MissionState()

        # Phase 1: Cognitive Homeostasis & Compression
        self.homeostasis = HomeostasisMonitor(self)
        self.compression = ActiveCompressionEngine(self)

        # Cold Storage
        self.cold_storage: List[Dict[str, Any]] = []
        self.archive_threshold: int = 100

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

    # --- Cold Storage Management ---

    def _archive_old_data(self) -> None:
        """
        Moves old elements from working memory layers to cold storage
        if they exceed the threshold.
        """
        layers_to_check = [
            ("procedure", self._procedures),
            ("duration", self._durations),
            ("prediction", self._predictions),
            ("consequence", self._consequences)
        ]

        for layer_type, layer_list in layers_to_check:
            while len(layer_list) > self.archive_threshold:
                old_item = layer_list.pop(0)
                self.cold_storage.append({
                    "type": layer_type,
                    "data": old_item,
                    "archived_at": datetime.now().isoformat()
                })

    # --- v3 Cognitive Interface ---

    def store_intent(self, intent: str, context: str):
        """Layer 1: Intent Memory (Why?)"""
        # Check alignment with Mission
        alignment = self.mission.check_alignment(intent)
        if alignment["recommendation"] == "reject":
            logger.warning(f"⚠️ Intent rejected by Mission: {alignment['reason']}")

        self._intent = {
            "intent": intent,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "alignment": alignment
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
        self._archive_old_data()

    def store_duration(self, event: str, duration_sec: float):
        """Layer 4: Duration Memory (How Long?)"""
        self._durations.append({
            "event": event,
            "duration_sec": duration_sec
        })
        self._archive_old_data()

    def store_prediction(self, condition: str, prediction: str, confidence: float):
        """Layer 5: Predictive Memory (How Soon?)"""
        self._predictions.append({
            "condition": condition,
            "prediction": prediction,
            "confidence": confidence
        })
        self._archive_old_data()

    def store_consequence(self, if_cond: str, then_result: str, severity: str):
        """Layer 6: Consequence Engine (What If?)"""
        self._consequences.append({
            "if": if_cond,
            "then": then_result,
            "severity": severity
        })
        self._archive_old_data()

    # --- v3.1 CTE Interface (Liminal Transitions) ---

    def commit_transition(self, decision: str, alternatives: Optional[List[str]] = None,
                          commitment: float = 0.9) -> Dict[str, Any]:
        """Wrapper for CTE: commits a choice (liminal anchor)."""
        return self._cte.commit_transition(decision, alternatives, commitment)

    def register_outcome(self, content: str, outcome_type: str = "insight") -> Dict[str, Any]:
        """Wrapper for CTE: registers an outcome and integrates with Belief System."""
        result = self._cte.register_outcome(content, outcome_type)

        if result["status"] == "success" and result.get("convict"):
            candidate = result["convict"]
            # Check if belief exists to decide register or reinforce
            # Simpler: just call register which handles existence check internally
            # (or returns existing), then reinforce.

            # Phase 2 spec: "register_belief(text, metadata)"
            meta = {
                "origin": candidate["origin"],
                "context_id": candidate.get("context_id")
            }
            convict = self.lifecycle.register_belief(candidate["belief"], meta)

            # Initial reinforcement or subsequent reinforcement
            self.lifecycle.reinforce(
                convict.id,
                source="cte_outcome",
                context=candidate["evidence"],
                strength=1.0 # strong reinforcement from direct insight
            )

            # Add updated info to result
            result["convict_id"] = convict.id
            result["convict_status"] = convict.status.value

        return result

    def register_belief(self, text: str, metadata: Dict[str, Any]) -> Convict:
        """Expose lifecycle method."""
        return self.lifecycle.register_belief(text, metadata)

    def reinforce_belief(self, convict_id: str, source: str, context: Dict[str, Any], strength: float) -> bool:
        """Expose lifecycle method."""
        return self.lifecycle.reinforce(convict_id, source, context, strength)

    def update_cognitive_state(self):
        """Triggers decay and contradiction detection."""
        self.lifecycle.decay_all()
        self.lifecycle.detect_contradictions()

    def sync_convicts_to_mission(self) -> None:
        """Syncs active beliefs to Mission State."""
        # Get active beliefs from lifecycle
        active_beliefs = self.lifecycle.get_active_beliefs()
        for c in active_beliefs:
            # Minimal mapping to dict for MissionState
            c_dict = {
                "belief": c.belief,
                "confidence": c.confidence,
                "strength": c.strength,
                "origin": c.metadata.get("origin", "unknown"),
                "last_validated": c.last_reinforced_at.timestamp() if c.last_reinforced_at else c.created_at.timestamp()
            }
            self.mission.add_convict(c_dict)

    def monitor_homeostasis(self) -> Dict[str, Any]:
        """Runs the homeostasis monitor and returns the report."""
        return self.homeostasis.auto_adjust()

    def compress_cognition(self) -> None:
        """Triggers cognitive compression."""
        self.compression.compress_cognition()

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

        # Trigger maintenance
        self.update_cognitive_state()

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
        Cognitive Timeline Engine (CTE) & Belief System.
        Organizes context into prioritized sections based on Mission weights.
        """
        weights = self.mission.weights

        # --- 1. META-COGNITION ---
        meta_lines = []

        # Intent (Always First)
        if ctx.intent:
            align_pct = int(ctx.intent["alignment"]["score"] * 100)
            meta_lines.append(
                f"🧠 INTENT: {ctx.intent['intent']} "
                f"(Context: {ctx.intent['context']}) "
                f"[Mission alignment: {align_pct}%]"
            )

        # Stability Status (Homeostasis)
        try:
            h_report = self.homeostasis.monitor()
            stab_status = f"Stability: {h_report.stability_score:.2f}"
            if h_report.is_locked:
                stab_status += " [LOCKED]"
            meta_lines.append(f"⚖️ HOMEOSTASIS: {stab_status}")
        except Exception as e:
            logger.warning(f"Failed to read homeostasis: {e}")

        # Mission Summary
        ms = self.mission.get_summary()
        meta_lines.append(
            f"📜 MISSION: core={ms['core_principles_count']} values, "
            f"adaptive={ms['adaptive_beliefs_count']} beliefs, "
            f"changes={ms['total_changes']}"
        )

        # Target (Weighted)
        if ctx.target:
            meta_lines.append(
                (weights.get("target", 0.9), 2, f"🎯 TARGET: {ctx.target['for_whom']} (Reason: {ctx.target['reason']})")
            )

        # CTE snapshot
        cte_summary = self._cte.export_summary()
        if "active_anchor" in cte_summary:
            a = cte_summary["active_anchor"]
            meta_lines.append(
                (2.0, 3, f"🔒 ACTIVE CHOICE: {a['decision']} (commitment={a['commitment']:.2f}, status={a['status']})")
            )
        if "last_outcome" in cte_summary:
            o = cte_summary["last_outcome"]
            meta_lines.append(
                (2.0, 4, f"💡 LAST OUTCOME: {o['content']} (type={o['type']})")
            )

        # Sort META lines (except forced ones)
        # Separate forced (already strings) from weighted (tuples)
        meta_final = [line for line in meta_lines if isinstance(line, str)]
        weighted_meta = [line for line in meta_lines if isinstance(line, tuple)]
        weighted_meta.sort(key=lambda x: (-x[0], x[1]))
        meta_final.extend([x[2] for x in weighted_meta])

        sections: List[str] = []
        if meta_final:
            sections.append("### META-COGNITION ###\n" + "\n".join(meta_final))

        # --- 2. PAST (Timeline) ---
        past_blocks = []

        # History
        if ctx.history:
            h_str = "💬 RECENT HISTORY:\n" + "\n".join([f"{m['role'].upper()}: {m['content'][:TRUNCATE_LIMIT_HISTORY]}" for m in ctx.history])
            past_blocks.append((weights.get("history", 0.8), 1, h_str))

        # Memory
        if ctx.memory:
            snippets = []
            for m in ctx.memory:
                q = m.get("question") or m.get("q") or "?"
                a = m.get("answer") or m.get("a") or ""
                a_short = (a[:TRUNCATE_LIMIT_ANSWER] + "...") if len(a) > TRUNCATE_LIMIT_ANSWER else a
                snippets.append(f"• Q: {q} | A: {a_short}")
            m_str = "📂 EPISODIC RECALL:\n" + "\n".join(snippets)
            past_blocks.append((weights.get("memory", 0.7), 2, m_str))

        # Durations
        if ctx.durations:
            dur_lines = [f"• {d['event']}: {d['duration_sec']}s" for d in ctx.durations]
            d_str = "⏳ TIME TRACKING:\n" + "\n".join(dur_lines)
            past_blocks.append((weights.get("durations", 0.3), 3, d_str))

        past_blocks.sort(key=lambda x: (-x[0], x[1]))
        if past_blocks:
            sections.append("### PAST TIMELINE ###\n" + "\n\n".join([b[2] for b in past_blocks]))

        # --- 3. PRESENT (Knowledge) ---
        present_blocks = []
        if ctx.facts:
            f_str = "📚 RELEVANT FACTS (DMP):\n" + "\n".join(ctx.facts)
            present_blocks.append((weights.get("facts", 0.6), 1, f_str))
        if ctx.logic:
            l_str = "📐 LOGIC PATTERNS (CML):\n" + "\n".join([f"⚙️ {i.get('decision')} (Reason: {i.get('reason')})" for i in ctx.logic])
            present_blocks.append((weights.get("logic", 0.6), 2, l_str))

        present_blocks.sort(key=lambda x: (-x[0], x[1]))
        if present_blocks:
            sections.append("### PRESENT CONTEXT ###\n" + "\n\n".join([b[2] for b in present_blocks]))

        # --- 4. FUTURE (Planning) ---
        future_blocks = []
        if ctx.procedures:
            proc_lines = []
            for p in ctx.procedures:
                steps_str = " -> ".join(p['steps'])
                proc_lines.append(f"🛠 {p['task']}: {steps_str}")
            p_str = "🛠 ACTIVE PROCEDURES:\n" + "\n".join(proc_lines)
            future_blocks.append((weights.get("procedures", 0.5), 1, p_str))

        if ctx.consequences:
            cons_lines = [f"⚠️ IF {c['if']} THEN {c['then']} (Severity: {c['severity']})" for c in ctx.consequences]
            c_str = "⚠️ CONSEQUENCE ANALYSIS:\n" + "\n".join(cons_lines)
            future_blocks.append((weights.get("consequences", 0.5), 2, c_str))

        if ctx.predictions:
            pred_lines = [f"🔮 {p['condition']} -> {p['prediction']} ({p['confidence']*100:.0f}%)" for p in ctx.predictions]
            pr_str = "🔮 PREDICTIONS:\n" + "\n".join(pred_lines)
            future_blocks.append((weights.get("predictions", 0.4), 3, pr_str))

        future_blocks.sort(key=lambda x: (-x[0], x[1]))
        if future_blocks:
            sections.append("### FUTURE PROJECTIONS ###\n" + "\n\n".join([b[2] for b in future_blocks]))

        # --- 5. CONVICTS ---
        convicts = self.lifecycle.get_active_beliefs()
        # Sort by confidence desc
        convicts.sort(key=lambda x: x.confidence, reverse=True)

        if convicts:
            c_lines = [f"• {c.belief} (confidence={c.confidence:.2f}, strength={c.strength:.2f})" for c in convicts[:5]]
            sections.append("### CONVICTS (FORMED BELIEFS) ###\n" + "\n".join(c_lines))

        # Final Assembly
        system_msg = "🚀 INSTRUCTION: You are CaPU v3.1. Use the provided Cognitive Timeline and Mission values to reason effectively."

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
