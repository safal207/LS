from __future__ import annotations

import json
from pathlib import Path

from generate_ci_exchange_health import (
    HEALTH_JSON_PATH,
    HEALTH_MARKDOWN_PATH,
    build_health_report,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def test_health_report_snapshot_matches_generator() -> None:
    generated = build_health_report(ROOT)
    committed = json.loads((ROOT / HEALTH_JSON_PATH).read_text(encoding="utf-8"))

    assert committed == generated


def test_health_markdown_snapshot_matches_generator() -> None:
    report = build_health_report(ROOT)
    generated_markdown = render_markdown(report)
    committed_markdown = (ROOT / HEALTH_MARKDOWN_PATH).read_text(encoding="utf-8")

    assert committed_markdown == generated_markdown


def test_health_report_is_pass_when_metadata_is_consistent() -> None:
    report = build_health_report(ROOT)

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert report["counts"]["nodes"] == 3
    assert report["counts"]["routes"] >= 1
    assert report["counts"]["known_working_routes"] >= 1
    assert "CI Exchange metadata is internally consistent" in report["summary"]
