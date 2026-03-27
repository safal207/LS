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

    def _build_draft_prompt(self, thread_context: str | None) -> str:
        thread_block = f"\n\nКонтекст разговора:\n{thread_context}" if thread_context else ""
        return (
            "Роль: draft.\n"
            "Дай первичный ответ на вопрос собеседования.\n"
            "Требования:\n"
            "- отвечай по существу\n"
            "- не выдумывай цифры и кейсы\n"
            "- не уходи в лишнюю теорию\n"
            "- держи ответ в 4-7 предложениях\n"
            f"{thread_block}"
        )

    def _build_critic_prompt(self, draft_answer: str, thread_context: str | None) -> str:
        thread_block = f"\n\nКонтекст разговора:\n{thread_context}" if thread_context else ""
        return (
            "Роль: critic.\n"
            "Проверь draft-ответ и верни только краткие буллеты критики.\n"
            "Ищи:\n"
            "- off-topic\n"
            "- выдуманные факты\n"
            "- пропущенные trade-offs\n"
            "- слабую связь с вопросом и нитью разговора\n"
            "- лишнюю воду\n"
            f"{thread_block}\n\nDraft:\n{draft_answer}"
        )

    def _build_compressor_prompt(self, draft_answer: str, critique_answer: str | None, thread_context: str | None) -> str:
        thread_block = f"\n\nКонтекст разговора:\n{thread_context}" if thread_context else ""
        prompt = (
            "Роль: compressor.\n"
            "Собери финальный ответ на интервью-вопрос.\n"
            "Требования:\n"
            "- используй сильные части draft\n"
            "- исправь замечания из critique\n"
            "- сделай ответ плотным и естественным\n"
            "- не упоминай draft или critique\n"
            "- не выдумывай детали\n"
            f"{thread_block}\n\nDraft:\n{draft_answer}"
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

    def run(self, item: dict, route_key: str, thread_context: str | None = None) -> CooperativeExecutionResult:
        text = str(item.get("text", "") or "")
        if not text:
            return CooperativeExecutionResult(
                route_key=route_key,
                success=False,
                metadata={"error": "empty-question"},
            )

        result = CooperativeExecutionResult(route_key=route_key)

        draft_prompt = self._build_draft_prompt(thread_context)
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

        critique_prompt = self._build_critic_prompt(result.draft_answer, thread_context)
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

        compressor_prompt = self._build_compressor_prompt(
            result.draft_answer,
            result.critique_answer,
            thread_context,
        )

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
            "degraded": not bool(result.critique_answer and result.compressed_answer),
        }
        return result
