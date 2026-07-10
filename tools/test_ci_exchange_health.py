from __future__ import annotations

import json
from pathlib import Path

from generate_ci_exchange_health import JSON_OUTPUT, MARKDOWN_OUTPUT, build_health_report, render_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_ci_exchange_health_report_is_passing() -> None:
    report = build_health_report(ROOT)

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert {check["status"] for check in report["checks"]} == {"pass"}


def test_committed_health_json_matches_generator() -> None:
    generated = build_health_report(ROOT)
    committed = json.loads((ROOT / JSON_OUTPUT).read_text(encoding="utf-8"))

    assert committed == generated


def test_committed_health_markdown_matches_generator() -> None:
    generated_markdown = render_markdown(build_health_report(ROOT))
    committed_markdown = (ROOT / MARKDOWN_OUTPUT).read_text(encoding="utf-8")

    assert committed_markdown == generated_markdown


def test_health_report_boundary_is_advisory() -> None:
    report = build_health_report(ROOT)

    assert "static CI Exchange metadata health only" in report["boundary"]
    assert "approve pull requests" in report["boundary"]
