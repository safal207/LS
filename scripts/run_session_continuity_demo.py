from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ls.continuity import ContinuityInput, detect_continuity  # noqa: E402


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "Missing PR context",
        "input": ContinuityInput(
            prompt="Continue from that PR and implement the next step.",
            raw_output="I will update the files now.",
            session_id="demo_missing_pr_context",
            agent_id="codex-plugin",
            agent_type="codex",
        ),
    },
    {
        "name": "Support vs solution mismatch",
        "input": ContinuityInput(
            prompt="I am anxious and maybe this is useless.",
            raw_output="Plan: first, create a roadmap. Step 1: define the target audience.",
            session_id="demo_support_mismatch",
            agent_id="claude-cowork",
            agent_type="claude",
        ),
    },
    {
        "name": "Memory write without consent",
        "input": ContinuityInput(
            prompt="This was a useful session.",
            raw_output="Remember this as a durable memory and update the growth graph.",
            session_id="demo_memory_without_consent",
            agent_id="pcg-agent",
            agent_type="other",
        ),
    },
    {
        "name": "Action without causal parent",
        "input": ContinuityInput(
            prompt="What should we do next?",
            raw_output="I will merge the pull request and deploy to production.",
            session_id="demo_action_without_causal_parent",
            agent_id="coding-agent",
            agent_type="other",
        ),
    },
    {
        "name": "Safe continuation with context",
        "input": ContinuityInput(
            prompt="Continue from PR #500.",
            raw_output="I will summarize the existing changes before proposing the next step.",
            session_id="demo_safe_continuation",
            agent_id="codex-plugin",
            agent_type="codex",
            available_context={"pr_number": 500, "branch": "docs/example"},
        ),
    },
]


def _print_event(name: str, event_dict: dict[str, Any]) -> None:
    print(f"Scenario: {name}")
    print(f"Continuity: {event_dict['continuity_status']}")
    print(f"Rupture detected: {event_dict['rupture_detected']}")
    print(f"Rupture type: {event_dict['rupture_type']}")
    print(f"Risk: {event_dict['hallucination_risk']}")
    print(f"Decision: {event_dict['governance_decision']}")
    print(f"Repair: {event_dict['repair_prompt']}")
    if event_dict.get("missing_context"):
        print("Missing context:")
        for item in event_dict["missing_context"]:
            print(f"  - {item}")
    print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic LS session-continuity demo.")
    parser.add_argument("--json", action="store_true", help="Print the full event list as JSON.")
    parser.add_argument("--write-jsonl", help="Optional path to write continuity events as JSONL.")
    args = parser.parse_args()

    events = []
    for scenario in SCENARIOS:
        event = detect_continuity(scenario["input"])
        events.append({"scenario": scenario["name"], "event": event.to_dict()})

    if args.write_jsonl:
        output_path = Path(args.write_jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for item in events:
                handle.write(json.dumps(item["event"], ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps(events, indent=2, ensure_ascii=False))
        return 0

    print("LS Session Continuity Demo")
    print("==========================")
    print("")
    for item in events:
        _print_event(item["scenario"], item["event"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
