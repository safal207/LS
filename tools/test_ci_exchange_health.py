from __future__ import annotations

import json
from pathlib import Path

from generate_ci_exchange_health import JSON_OUTPUT, MARKDOWN_OUTPUT, build_health_report, render_markdown

ROOT = Path(__file__).resolve().parents[1]
REVIEWER_WEIGHTS = Path(".ci_exchange/reviewer_weights.latest.json")


def test_ci_exchange_health_report_is_passing() -> None:
    report = build_health_report(ROOT)

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert {check["status"] for check in report["checks"]} == {"pass"}
    assert all(check["errors"] == [] for check in report["checks"])


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


def test_reviewer_weights_compare_distinct_signal_roles() -> None:
    weights = json.loads((ROOT / REVIEWER_WEIGHTS).read_text(encoding="utf-8"))
    reviewers = {reviewer["reviewer_id"]: reviewer for reviewer in weights["reviewers"]}

    assert reviewers["security_ci_pipeline"]["weights"]["gate_strength"] > reviewers["grok_advisory_review"]["weights"]["gate_strength"]
    assert reviewers["grok_advisory_review"]["weights"]["causal_reasoning"] > reviewers["security_ci_pipeline"]["weights"]["causal_reasoning"]
    assert reviewers["reflection_http_e2e"]["weights"]["runtime_confidence"] > reviewers["coderabbit"]["weights"]["runtime_confidence"]
    assert "Required CI gates" in weights["decision_rule"]
