from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for candidate in (SCRIPTS_ROOT, PYTHON_ROOT, MODULES_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from run_model_roster_depth_probe import build_probe_payload as build_roster_payload  # noqa: E402
from run_nash_route_stability_demo import build_demo_payload as build_nash_payload  # noqa: E402
from run_network_precision_gain_demo import build_demo_payload as build_network_payload  # noqa: E402


REPORT_VERSION = "network_precision_contributor_report.v0.1"


def _platform_payload() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
    }


def _commands(*, live_roster: bool, max_tokens: int) -> list[str]:
    commands = [
        "python scripts/run_network_precision_gain_demo.py --json",
        "python scripts/run_model_roster_depth_probe.py --json",
        "python scripts/run_nash_route_stability_demo.py --json",
    ]
    if live_roster:
        commands.append(f"python scripts/run_model_roster_depth_probe.py --live --json --max-tokens {max_tokens}")
    return commands


def _extract_temporal(network: dict, variant_label: str) -> dict:
    for v in network.get("variants", []):
        if v.get("label") == variant_label:
            detail = v.get("temporal_observer_detail", {})
            return {
                "temporal_product": detail.get("temporal_product", 0.0),
                "drift": detail.get("drift_score", 0.0),
                "cycle": detail.get("cycle_detection", 0.0),
                "lag": detail.get("lag_between_levels", 0.0),
                "resonance": detail.get("resonance", 0.0),
            }
    return {}


def _extract_scope(network: dict, variant_label: str) -> dict:
    for v in network.get("variants", []):
        if v.get("label") == variant_label:
            detail = v.get("scope_bridge_detail", {})
            return {
                "propagation_product": detail.get("propagation_product", 0.0),
                "individual_to_aquarium": detail.get("individual_to_aquarium", 0.0),
                "aquarium_to_environment": detail.get("aquarium_to_environment", 0.0),
                "individual_to_environment": detail.get("individual_to_environment", 0.0),
            }
    return {}


def build_report_payload(
    *,
    runner: str = "",
    live_roster: bool = False,
    max_tokens: int = 180,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ls-contributor-report-") as tmp:
        tmp_path = Path(tmp)
        network = build_network_payload(
            tmp_path / "network_routes.json",
            tmp_path / "network_events.jsonl",
        )
        route_stability = build_nash_payload(
            tmp_path / "route_stability_routes.json",
            tmp_path / "route_stability_events.jsonl",
        )

    roster = build_roster_payload(live=live_roster, max_tokens=max_tokens)
    precision = network["network_precision"]
    temporal_coop = _extract_temporal(network, "cooperative_route")
    temporal_full = _extract_temporal(network, "cooperative_precision_stack")
    scope_coop = _extract_scope(network, "cooperative_route")
    scope_full = _extract_scope(network, "cooperative_precision_stack")
    summary = {
        "single_baseline_score": precision["baseline_score"],
        "cooperative_route_score": precision["cooperative_score"],
        "full_stack_score": precision["full_stack_score"],
        "measured_route_reward_gain": network["measured_route_reward_gain"],
        "network_precision_gain_over_baseline": precision["network_precision_gain_over_baseline"],
        "stack_added_gain_over_cooperation": precision["stack_added_gain_over_cooperation"],
        "score_ratio_vs_baseline": precision["score_ratio_vs_baseline"],
        "scope_bridge_propagation": {
            "cooperative": scope_coop,
            "full_stack": scope_full,
        },
        "temporal_coherence": {
            "cooperative": temporal_coop,
            "full_stack": temporal_full,
        },
        "network_decision": precision["decision"],
        "route_stability_decision": route_stability["stability"]["decision"],
        "ready_actors": roster["interpretation"]["available_now"],
        "unavailable_actors": roster["interpretation"]["unavailable_now"],
    }
    return {
        "report_version": REPORT_VERSION,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "runner": runner,
        "environment": _platform_payload(),
        "commands": _commands(live_roster=live_roster, max_tokens=max_tokens),
        "summary": summary,
        "network_precision": network,
        "model_roster": roster,
        "route_stability": route_stability,
        "boundary": (
            "This contributor report is not a model leaderboard, not a formal Nash proof, "
            "and not a production-safety claim. It is a reproducible probe for cooperative "
            "route precision across environments."
        ),
    }


def _bullet_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values)


def render_markdown(payload: dict[str, Any], *, include_full_json: bool = False) -> str:
    env = payload["environment"]
    summary = payload["summary"]
    runner = payload["runner"] or "<GitHub handle or pseudonym>"
    commands = "\n".join(payload["commands"])
    lines = [
        "# LS Network Precision Contributor Report",
        "",
        "## Environment",
        "",
        f"- Runner: {runner}",
        f"- Date UTC: {payload['created_at_utc']}",
        f"- OS: {env['os']}",
        f"- Python: {env['python_version']}",
        f"- Machine: {env['machine']}",
        f"- Processor: {env['processor'] or 'not reported'}",
        "",
        "## Commands",
        "",
        "```bash",
        commands,
        "```",
        "",
        "## Results",
        "",
        f"- single_baseline_score: {summary['single_baseline_score']}",
        f"- cooperative_route_score: {summary['cooperative_route_score']}",
        f"- full_stack_score: {summary['full_stack_score']}",
        f"- measured_route_reward_gain: {summary['measured_route_reward_gain']}",
        f"- network_precision_gain_over_baseline: {summary['network_precision_gain_over_baseline']}",
        f"- stack_added_gain_over_cooperation: {summary['stack_added_gain_over_cooperation']}",
        f"- score_ratio_vs_baseline: {summary['score_ratio_vs_baseline']}",
        f"- scope_bridge_propagation (cooperative): {summary['scope_bridge_propagation']['cooperative']['propagation_product']}",
        f"- scope_bridge_propagation (full_stack): {summary['scope_bridge_propagation']['full_stack']['propagation_product']}",
        f"- temporal_coherence (cooperative): {summary['temporal_coherence']['cooperative']['temporal_product']} (drift={summary['temporal_coherence']['cooperative']['drift']}, cycle={summary['temporal_coherence']['cooperative']['cycle']}, lag={summary['temporal_coherence']['cooperative']['lag']}, resonance={summary['temporal_coherence']['cooperative']['resonance']})",
        f"- temporal_coherence (full_stack): {summary['temporal_coherence']['full_stack']['temporal_product']} (drift={summary['temporal_coherence']['full_stack']['drift']}, cycle={summary['temporal_coherence']['full_stack']['cycle']}, lag={summary['temporal_coherence']['full_stack']['lag']}, resonance={summary['temporal_coherence']['full_stack']['resonance']})",
        f"- network_decision: {summary['network_decision']}",
        f"- route_stability_decision: {summary['route_stability_decision']}",
        "",
        "## Ready Actors",
        "",
        _bullet_list(summary["ready_actors"]),
        "",
        "## Unavailable Actors",
        "",
        _bullet_list(summary["unavailable_actors"]),
        "",
        "## Notes",
        "",
        "Add anything surprising, slow, brittle, useful, or different about your model/runtime.",
        "",
        "## Boundary",
        "",
        payload["boundary"],
    ]
    if include_full_json:
        lines.extend(
            [
                "",
                "<details>",
                "<summary>Full JSON payload</summary>",
                "",
                "```json",
                json.dumps(payload, ensure_ascii=False, indent=2),
                "```",
                "",
                "</details>",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a copy-paste LS network precision contributor report.")
    parser.add_argument("--runner", default="", help="GitHub handle or pseudonym to include in the report.")
    parser.add_argument("--live-roster", action="store_true", help="Call the configured live model route.")
    parser.add_argument("--max-tokens", type=int, default=180, help="Generation max tokens for --live-roster.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--include-full-json", action="store_true", help="Include full JSON details in Markdown output.")
    parser.add_argument("--output", type=Path, default=None, help="Optional output file path.")
    args = parser.parse_args()

    payload = build_report_payload(runner=args.runner, live_roster=args.live_roster, max_tokens=args.max_tokens)
    output = (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.json
        else render_markdown(payload, include_full_json=args.include_full_json)
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
