from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """You are the risk reasoning layer for an AI-agent action gateway.
Return one JSON object only, with keys:
risk_level (LOW|MEDIUM|HIGH|CRITICAL),
decision (ALLOW|HUMAN_APPROVAL|BLOCK),
confidence (number 0..1),
reasons (array of concise strings),
required_controls (array of concise strings).
Be conservative with irreversible, financial, credential, production, privacy, or external side effects.
Never claim an action was executed. You only assess a proposed action.
"""


class QwenRiskReasoner:
    def __init__(self) -> None:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is not configured")
        self.model = os.getenv("QWEN_MODEL", "qwen3.7-plus")
        self.client = OpenAI(
            api_key=api_key,
            base_url=os.getenv(
                "QWEN_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
            timeout=float(os.getenv("QWEN_TIMEOUT_SECONDS", "25")),
        )

    def assess(self, payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        completion = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"proposed_action": payload, "deterministic_policy": policy},
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        content = completion.choices[0].message.content or ""
        return _parse_json_object(content)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Qwen did not return a JSON object")
    result = json.loads(text[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("Qwen response must be an object")
    return result
