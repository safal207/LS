from __future__ import annotations

import os

import httpx

from .models import Task


def _mock_landing(task: Task) -> str:
    headline = task.title.strip() or "AI Landing"
    body = task.description.strip() or "Generate more revenue with AI automation."
    return f"""<!doctype html>
<html lang=\"en\">
  <head><meta charset=\"utf-8\"><title>{headline}</title></head>
  <body>
    <main>
      <h1>{headline}</h1>
      <p>{body}</p>
      <p>Trusted by modern teams. Fast setup. Measurable outcomes.</p>
      <a href=\"#contact\" class=\"cta\">Start Free Trial</a>
    </main>
  </body>
</html>"""


def _mock_generic(task: Task) -> str:
    return f"Result for task '{task.title}': {task.description}"


def call_llm(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": os.getenv("MARKET_LAYER_LLM_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def execute_task(task: Task) -> str:
    if task.use_case == "landing_generator":
        prompt = (
            "Generate production-ready HTML landing page with CTA for this task:\n"
            f"title={task.title}\ndescription={task.description}"
        )
        llm_out = call_llm(prompt)
        return llm_out or _mock_landing(task)
    return _mock_generic(task)
