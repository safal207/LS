from __future__ import annotations

import re
from html.parser import HTMLParser

from .models import Task


class _TagTracker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: set[str] = set()

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        self.tags.add(tag.lower())


def evaluate_artifact(task: Task, content: str) -> dict[str, float | bool | str]:
    content = content or ""
    text_len = len(re.sub(r"<[^>]+>", "", content))

    parser = _TagTracker()
    parser.feed(content)
    has_html = "html" in parser.tags and "body" in parser.tags
    has_cta = bool(re.search(r"(start|buy|signup|trial|contact)", content, re.IGNORECASE))
    auto_pass = has_html and text_len >= 80
    reviewer_pass = has_cta and text_len >= 100

    if task.use_case == "landing_generator":
        impact = min(1.0, max(0.0, text_len / 500))
    else:
        impact = min(1.0, max(0.0, text_len / 400))

    quality = round((0.4 if auto_pass else 0) + (0.4 if reviewer_pass else 0) + 0.2 * impact, 4)
    return {
        "auto_pass": auto_pass,
        "reviewer_pass": reviewer_pass,
        "impact_score": round(impact, 4),
        "quality_score": quality,
        "note": f"len={text_len}, has_html={has_html}, has_cta={has_cta}",
    }
