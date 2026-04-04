# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Optional


@dataclass
class CooperativeExecutionResult:
    route_key: str
    draft_answer: Optional[str] = None
    critique_answer: Optional[str] = None
    compressed_answer: Optional[str] = None
    final_answer: Optional[str] = None
    participants: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CooperativeGraphEngine:
    """Minimal cooperative execution for one coalition route."""

    _TECH_TERMS = (
        "node.js",
        "nodejs",
        "react",
        "express",
        "mongodb",
        "mongo",
        "spring",
        "spring boot",
        "asp.net",
        "asp.net core",
        ".net",
        "python",
        "java",
        "c#",
        "go",
        "golang",
        "redis",
        "kafka",
        "postgres",
        "postgresql",
        "mysql",
        "django",
        "flask",
        "fastapi",
        "angular",
        "vue",
        "next.js",
        "nestjs",
    )

    def __init__(self, backends: dict[str, Any]) -> None:
        self.backends = backends

    def _grounding_guardrails(self, item: dict[str, Any], thread_context: str | None) -> str:
        known_facts: list[str] = []
        for key in ("clean_text", "text", "thread_context"):
            value = item.get(key) if isinstance(item, dict) else None
            if value:
                known_facts.append(str(value))
        if thread_context:
            known_facts.append(str(thread_context))
        context_block = "\n".join(f"- {fact}" for fact in known_facts if fact) or "- no explicit project facts were provided"
        return (
            "Grounding rules:\n"
            "- Use only facts explicitly present in the user question or conversation context.\n"
            "- Do not name concrete technologies, companies, team size, benchmarks, or architecture choices unless they are explicitly given.\n"
            "- If the stack or alternatives are not specified, answer conditionally using phrases like 'в таком случае', 'если приоритет был ...', 'я бы объяснил выбор через компромиссы', not fabricated specifics.\n"
            "- If information is missing, state the uncertainty briefly instead of filling gaps.\n"
            "- Remove any invented examples from the final answer.\n"
            "- Answer in Russian.\n"
            "Known context:\n"
            f"{context_block}"
        )

    def _goal_guidance(self, goal_vector: dict[str, Any] | None) -> str:
        if not goal_vector:
            return ""
        style = goal_vector.get("style")
        strategy_bias = goal_vector.get("strategy_bias")
        lines = [
            "Target answer profile:",
            f"- style={style}",
            f"- strategy_bias={strategy_bias}",
            f"- target_relevance={goal_vector.get('target_relevance')}",
            f"- target_thread_alignment={goal_vector.get('target_thread_alignment')}",
            f"- target_hallucination_max={goal_vector.get('target_hallucination_max')}",
            f"- target_latency_ms={goal_vector.get('target_latency_ms')}",
        ]
        if style == "concise":
            lines.append("- Keep the answer short and dense.")
        elif style == "careful":
            lines.append("- Keep the answer careful and do not invent details.")
        elif style == "structured":
            lines.append("- Keep the answer structured and show reasoning.")
        if strategy_bias == "speed_first":
            lines.append("- Prefer speed and clarity.")
        elif strategy_bias == "verify_first":
            lines.append("- Prefer verifiability and groundedness.")
        elif strategy_bias == "cooperative_reasoning":
            lines.append("- Show trade-offs and decision logic.")
        elif strategy_bias == "grounded":
            lines.append("- Do not invent metrics, projects, or facts.")
        return "\n".join(lines)

    def _build_draft_prompt(self, thread_context: str | None, goal_vector: dict[str, Any] | None) -> str:
        thread_block = f"\n\nConversation context:\n{thread_context}" if thread_context else ""
        goal_block = f"\n\n{self._goal_guidance(goal_vector)}" if goal_vector else ""
        return (
            "Role: draft.\n"
            "Give a first-pass interview answer.\n"
            "Requirements:\n"
            "- stay on point\n"
            "- do not invent metrics or case studies\n"
            "- avoid unnecessary theory\n"
            "- if the question does not specify the stack, do not guess the stack\n"
            "- answer in Russian\n"
            "- keep the answer within 4-7 sentences\n"
            f"{thread_block}{goal_block}"
        )

    def _build_critic_prompt(self, draft_answer: str, thread_context: str | None, goal_vector: dict[str, Any] | None) -> str:
        thread_block = f"\n\nConversation context:\n{thread_context}" if thread_context else ""
        goal_block = f"\n\n{self._goal_guidance(goal_vector)}" if goal_vector else ""
        return (
            "Role: critic.\n"
            "Review the draft answer and return short critique bullets only.\n"
            "Look for:\n"
            "- off-topic content\n"
            "- invented facts\n"
            "- invented technology names or architecture details not present in the question\n"
            "- missing trade-offs\n"
            "- weak connection to the question or thread\n"
            "- excess verbosity\n"
            "- any place where the draft sounds too specific without evidence\n"
            f"{thread_block}{goal_block}\n\nDraft:\n{draft_answer}"
        )

    def _build_compressor_prompt(self, draft_answer: str, critique_answer: str | None, thread_context: str | None, goal_vector: dict[str, Any] | None) -> str:
        thread_block = f"\n\nConversation context:\n{thread_context}" if thread_context else ""
        goal_block = f"\n\n{self._goal_guidance(goal_vector)}" if goal_vector else ""
        prompt = (
            "Role: compressor.\n"
            "Build the final interview answer.\n"
            "Requirements:\n"
            "- keep the strongest parts of the draft\n"
            "- fix issues from the critique\n"
            "- make the answer compact and natural\n"
            "- do not mention draft or critique\n"
            "- do not invent details\n"
            "- if the stack was not explicitly named, do not name a stack in the final answer\n"
            "- prefer trade-off framing over fabricated specifics\n"
            "- answer in Russian\n"
            f"{thread_block}{goal_block}\n\nDraft:\n{draft_answer}"
        )
        if critique_answer:
            prompt += f"\n\nCritique:\n{critique_answer}"
        return prompt

    def _call_backend(
        self,
        backend_name: str,
        *,
        user_text: str,
        system_prompt: str,
        metadata: Optional[dict[str, Any]] = None,
    ):
        backend = self.backends.get(backend_name)
        if backend is None:
            return None
        return backend.generate(
            messages=[{"role": "user", "content": user_text}],
            system_prompt=system_prompt,
            metadata=metadata or {},
        )

    def _combined_context(self, item: dict[str, Any], thread_context: str | None) -> str:
        parts = []
        for key in ("clean_text", "text", "thread_context"):
            value = item.get(key) if isinstance(item, dict) else None
            if value:
                parts.append(str(value))
        if thread_context:
            parts.append(str(thread_context))
        return "\n".join(parts).lower()

    def _stack_is_unspecified(self, item: dict[str, Any], thread_context: str | None) -> bool:
        context = self._combined_context(item, thread_context)
        return not any(term in context for term in self._TECH_TERMS)

    def _fabricated_terms(self, answer: str, item: dict[str, Any], thread_context: str | None) -> list[str]:
        context = self._combined_context(item, thread_context)
        answer_lower = str(answer or "").lower()
        fabricated = []
        for term in self._TECH_TERMS:
            if term in answer_lower and term not in context:
                fabricated.append(term)
        return fabricated

    def _rewrite_generic_tradeoff_answer(self, question: str, thread_context: str | None) -> str:
        thread_hint = ""
        if thread_context:
            thread_hint = " В таком объяснении я бы опирался на обсуждаемые компромиссы скорости разработки, стоимости поддержки и устойчивости решения."
        return (
            "Я бы не привязывал ответ к конкретному стеку, если он не был явно назван в вопросе. "
            "В таком случае правильнее объяснить выбор через компромиссы: почему этот набор технологий лучше подходит по скорости разработки, "
            "поддержке, управляемости сложности и допустимому риску ошибок, а также в каких условиях более простой стек мог бы быть разумнее."
            f"{thread_hint}"
        )

    def _deterministic_rewrite(self, answer: str, item: dict[str, Any], thread_context: str | None) -> str:
        text = " ".join(str(answer or "").split())
        if not text:
            return self._rewrite_generic_tradeoff_answer(str(item.get("text", "") or ""), thread_context)
        sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", text) if chunk.strip()]
        compact = " ".join(sentences[:3]).strip()
        for phrase in (
            "Плюсами этого стека являются",
            "Таким образом, выбор этого стека",
            "Вместо более простого набора технологий, мы выбрали этот стек из-за",
        ):
            compact = re.sub(re.escape(phrase), "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\s+", " ", compact).strip(" ,.-")
        if self._stack_is_unspecified(item, thread_context):
            return self._rewrite_generic_tradeoff_answer(str(item.get("text", "") or ""), thread_context)
        return compact or self._rewrite_generic_tradeoff_answer(str(item.get("text", "") or ""), thread_context)

    def run(self, item: dict, route_key: str, thread_context: str | None = None, goal_vector: dict[str, Any] | None = None) -> CooperativeExecutionResult:
        text = str(item.get("text", "") or "")
        if not text:
            return CooperativeExecutionResult(route_key=route_key, success=False, metadata={"error": "empty-question"})

        result = CooperativeExecutionResult(route_key=route_key)
        grounding_block = self._grounding_guardrails(item, thread_context)

        draft_prompt = self._build_draft_prompt(thread_context, goal_vector) + "\n\n" + grounding_block
        draft_response = self._call_backend("local", user_text=text, system_prompt=draft_prompt, metadata={"role": "draft", "route_key": route_key})
        if draft_response and draft_response.ok:
            result.draft_answer = draft_response.text
            result.participants.append({"backend": draft_response.provider, "model": draft_response.model, "role": "draft", "ok": True})
        else:
            fallback = self._call_backend("gonka", user_text=text, system_prompt=draft_prompt, metadata={"role": "draft-fallback", "route_key": route_key}) or self._call_backend("mimo", user_text=text, system_prompt=draft_prompt, metadata={"role": "draft-fallback", "route_key": route_key})
            if fallback and fallback.ok:
                result.draft_answer = fallback.text
                result.participants.append({"backend": fallback.provider, "model": fallback.model, "role": "draft-fallback", "ok": True})

        if not result.draft_answer:
            return CooperativeExecutionResult(route_key=route_key, success=False, metadata={"error": "no-draft"})

        critique_prompt = self._build_critic_prompt(result.draft_answer, thread_context, goal_vector) + "\n\n" + grounding_block
        critique_response = self._call_backend("gonka", user_text=text, system_prompt=critique_prompt, metadata={"role": "critic", "route_key": route_key})
        if critique_response and critique_response.ok:
            result.critique_answer = critique_response.text
            result.participants.append({"backend": critique_response.provider, "model": critique_response.model, "role": "critic", "ok": True})

        compressor_prompt = self._build_compressor_prompt(result.draft_answer, result.critique_answer, thread_context, goal_vector) + "\n\n" + grounding_block
        compressor_response = self._call_backend("mimo", user_text=text, system_prompt=compressor_prompt, metadata={"role": "compressor", "route_key": route_key})
        if compressor_response and compressor_response.ok:
            result.compressed_answer = compressor_response.text
            result.final_answer = compressor_response.text
            result.participants.append({"backend": compressor_response.provider, "model": compressor_response.model, "role": "compressor", "ok": True})
        else:
            result.final_answer = result.draft_answer

        scrubbed_terms: list[str] = []
        if result.final_answer and self._stack_is_unspecified(item, thread_context):
            scrubbed_terms = self._fabricated_terms(result.final_answer, item, thread_context)
            if scrubbed_terms:
                result.final_answer = self._rewrite_generic_tradeoff_answer(text, thread_context)

        rewrite_used = bool(result.final_answer and not result.compressed_answer)
        if rewrite_used:
            result.final_answer = self._deterministic_rewrite(result.final_answer or "", item, thread_context)

        result.success = bool(result.final_answer)
        result.metadata = {
            "cooperative_route_key": route_key,
            "draft_backend": next((p["backend"] for p in result.participants if p["role"] in {"draft", "draft-fallback"}), None),
            "critic_backend": next((p["backend"] for p in result.participants if p["role"] == "critic"), None),
            "compressor_backend": next((p["backend"] for p in result.participants if p["role"] == "compressor"), None),
            "final_source": "compressor" if result.compressed_answer else "draft",
            "degraded": not bool(result.critique_answer and result.compressed_answer),
            "goal_style": (goal_vector or {}).get("style"),
            "goal_strategy_bias": (goal_vector or {}).get("strategy_bias"),
            "grounding_scrubbed": bool(scrubbed_terms),
            "grounding_scrubbed_terms": scrubbed_terms,
            "deterministic_rewrite_used": rewrite_used,
        }
        return result
