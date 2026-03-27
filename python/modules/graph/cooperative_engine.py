from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    """Minimal cooperative execution for one coalition route.

    MVP coalition:
    - local -> draft
    - gonka -> critic
    - mimo -> compressor
    """

    def __init__(self, backends: dict[str, Any]) -> None:
        self.backends = backends

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

    def run(self, item: dict, route_key: str, thread_context: str | None = None) -> CooperativeExecutionResult:
        text = str(item.get("text", "") or "")
        if not text:
            return CooperativeExecutionResult(
                route_key=route_key,
                success=False,
                metadata={"error": "empty-question"},
            )

        thread_block = f"\n\nThread context:\n{thread_context}" if thread_context else ""
        result = CooperativeExecutionResult(route_key=route_key)

        draft_prompt = (
            "Role: draft.\n"
            "Answer the interview question directly, clearly, and without filler."
            f"{thread_block}"
        )
        draft_response = self._call_backend(
            "local",
            user_text=text,
            system_prompt=draft_prompt,
            metadata={"role": "draft", "route_key": route_key},
        )
        if draft_response and draft_response.ok:
            result.draft_answer = draft_response.text
            result.participants.append(
                {
                    "backend": draft_response.provider,
                    "model": draft_response.model,
                    "role": "draft",
                    "ok": True,
                }
            )
        else:
            fallback = self._call_backend(
                "gonka",
                user_text=text,
                system_prompt=draft_prompt,
                metadata={"role": "draft-fallback", "route_key": route_key},
            ) or self._call_backend(
                "mimo",
                user_text=text,
                system_prompt=draft_prompt,
                metadata={"role": "draft-fallback", "route_key": route_key},
            )
            if fallback and fallback.ok:
                result.draft_answer = fallback.text
                result.participants.append(
                    {
                        "backend": fallback.provider,
                        "model": fallback.model,
                        "role": "draft-fallback",
                        "ok": True,
                    }
                )

        if not result.draft_answer:
            return CooperativeExecutionResult(
                route_key=route_key,
                success=False,
                metadata={"error": "no-draft"},
            )

        critique_prompt = (
            "Role: critic.\n"
            "Review the draft answer. Point out weak reasoning, hallucinations, missing trade-offs, "
            "and thread mismatch. Return concise critique bullets only."
            f"{thread_block}\n\nDraft:\n{result.draft_answer}"
        )
        critique_response = self._call_backend(
            "gonka",
            user_text=text,
            system_prompt=critique_prompt,
            metadata={"role": "critic", "route_key": route_key},
        )
        if critique_response and critique_response.ok:
            result.critique_answer = critique_response.text
            result.participants.append(
                {
                    "backend": critique_response.provider,
                    "model": critique_response.model,
                    "role": "critic",
                    "ok": True,
                }
            )

        compressor_prompt = (
            "Role: compressor.\n"
            "Produce the final interview answer using the question, draft, and critique. "
            "Make it tighter, clearer, and aligned with the thread context. "
            "Do not mention that there was a draft or critique."
            f"{thread_block}\n\nDraft:\n{result.draft_answer}"
        )
        if result.critique_answer:
            compressor_prompt += f"\n\nCritique:\n{result.critique_answer}"

        compressor_response = self._call_backend(
            "mimo",
            user_text=text,
            system_prompt=compressor_prompt,
            metadata={"role": "compressor", "route_key": route_key},
        )
        if compressor_response and compressor_response.ok:
            result.compressed_answer = compressor_response.text
            result.final_answer = compressor_response.text
            result.participants.append(
                {
                    "backend": compressor_response.provider,
                    "model": compressor_response.model,
                    "role": "compressor",
                    "ok": True,
                }
            )
        else:
            result.final_answer = result.draft_answer

        result.success = bool(result.final_answer)
        result.metadata = {
            "cooperative_route_key": route_key,
            "draft_backend": next((p["backend"] for p in result.participants if p["role"] in {"draft", "draft-fallback"}), None),
            "critic_backend": next((p["backend"] for p in result.participants if p["role"] == "critic"), None),
            "compressor_backend": next((p["backend"] for p in result.participants if p["role"] == "compressor"), None),
            "final_source": "compressor" if result.compressed_answer else "draft",
        }
        return result
