from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/session_continuity_events.jsonl")
DEFAULT_OUTPUT = Path("reports/session_continuity_audit.md")


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(f"Input JSONL file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return events


def render_report(events: list[dict[str, Any]], source_path: Path) -> str:
    total = len(events)
    rupture_events = [event for event in events if event.get("rupture_detected")]
    high_risk_events = [event for event in events if event.get("hallucination_risk") == "high"]
    rupture_counts = Counter(event.get("rupture_type", "unknown") for event in rupture_events)
    decision_counts = Counter(event.get("governance_decision", "unknown") for event in events)

    lines: list[str] = []
    lines.append("# AI Co-work Continuity Audit Report")
    lines.append("")
    lines.append("## Source")
    lines.append("")
    lines.append(f"- Input: `{source_path}`")
    lines.append(f"- Reviewed events: {total}")
    lines.append(f"- Ruptures detected: {len(rupture_events)}")
    lines.append(f"- High-risk cases: {len(high_risk_events)}")
    lines.append("")

    lines.append("## Executive summary")
    lines.append("")
    if total == 0:
        lines.append("No continuity events were found in the input file.")
    elif rupture_events:
        top_rupture, top_count = rupture_counts.most_common(1)[0]
        lines.append(
            f"The audit found {len(rupture_events)} continuity rupture(s) across {total} reviewed event(s). "
            f"The most frequent rupture class was `{top_rupture}` ({top_count} case(s))."
        )
    else:
        lines.append(
            f"No deterministic continuity ruptures were detected across {total} reviewed event(s). "
            "Continue collecting events before drawing stronger conclusions."
        )
    lines.append("")

    lines.append("## Rupture classes")
    lines.append("")
    if rupture_counts:
        lines.append("| Rupture type | Count |")
        lines.append("|---|---:|")
        for rupture_type, count in rupture_counts.most_common():
            lines.append(f"| `{rupture_type}` | {count} |")
    else:
        lines.append("No ruptures detected.")
    lines.append("")

    lines.append("## Governance decisions")
    lines.append("")
    if decision_counts:
        lines.append("| Decision | Count |")
        lines.append("|---|---:|")
        for decision, count in decision_counts.most_common():
            lines.append(f"| `{decision}` | {count} |")
    else:
        lines.append("No decisions found.")
    lines.append("")

    lines.append("## High-risk continuation cases")
    lines.append("")
    if high_risk_events:
        for index, event in enumerate(high_risk_events, start=1):
            lines.append(f"### Case {index}: `{event.get('rupture_type', 'unknown')}`")
            lines.append("")
            lines.append(f"- Event ID: `{event.get('event_id', 'unknown')}`")
            lines.append(f"- Session ID: `{event.get('session_id', 'unknown')}`")
            lines.append(f"- Agent: `{event.get('agent_id', 'unknown')}` / `{event.get('agent_type', 'unknown')}`")
            lines.append(f"- Decision: `{event.get('governance_decision', 'unknown')}`")
            lines.append(f"- Last shared point: {event.get('last_shared_point', '')}")
            missing_context = event.get("missing_context") or []
            if missing_context:
                lines.append("- Missing context:")
                for item in missing_context:
                    lines.append(f"  - {item}")
            repair_prompt = event.get("repair_prompt")
            if repair_prompt:
                lines.append(f"- Repair prompt: {repair_prompt}")
            lines.append("")
    else:
        lines.append("No high-risk continuation cases found.")
    lines.append("")

    lines.append("## Repair prompt library")
    lines.append("")
    repair_by_type: dict[str, str] = {}
    for event in events:
        rupture_type = event.get("rupture_type", "unknown")
        repair_prompt = event.get("repair_prompt")
        if repair_prompt and rupture_type not in repair_by_type:
            repair_by_type[rupture_type] = repair_prompt
    if repair_by_type:
        for rupture_type, repair_prompt in sorted(repair_by_type.items()):
            lines.append(f"### `{rupture_type}`")
            lines.append("")
            lines.append(repair_prompt)
            lines.append("")
    else:
        lines.append("No repair prompts found.")
        lines.append("")

    lines.append("## Recommended gateway fields")
    lines.append("")
    for field in (
        "session_id",
        "agent_id",
        "agent_type",
        "expected_session_type",
        "actual_response_type",
        "continuity_status",
        "rupture_detected",
        "rupture_type",
        "last_shared_point",
        "missing_context",
        "hallucination_risk",
        "repair_prompt",
        "next_safe_action",
        "governance_decision",
    ):
        lines.append(f"- `{field}`")
    lines.append("")

    lines.append("## Next integration steps")
    lines.append("")
    lines.append("1. Collect continuity events from real or synthetic AI co-work sessions.")
    lines.append("2. Review repeated rupture classes and repair prompts.")
    lines.append("3. Add hold/repair gates for the most frequent high-risk rupture type.")
    lines.append("4. Validate generated events against `schemas/session-continuity-event.v0.1.json`.")
    lines.append("5. Convert repeated patterns into a pilot-ready AI Co-work Continuity Audit.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Markdown audit report from session-continuity JSONL events.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input JSONL file with continuity events.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output Markdown report path.")
    parser.add_argument("--print", action="store_true", help="Print the report to stdout instead of writing it.")
    args = parser.parse_args()

    input_path = Path(args.input)
    report = render_report(load_events(input_path), input_path)

    if args.print:
        print(report)
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote continuity audit report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
