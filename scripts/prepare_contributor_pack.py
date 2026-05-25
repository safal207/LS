from __future__ import annotations

import argparse
import json
import sys
import zipfile
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

from prepare_network_precision_contributor_report import (  # noqa: E402
    build_report_payload,
    render_markdown,
)


PACK_VERSION = "contributor_pack.v0.1"
DEFAULT_OUTPUT_DIR = Path("reports/contributor_pack")


def _runner_label(runner: str) -> str:
    return runner.strip() or "anonymous-runner"


def _issue_title(payload: dict[str, Any]) -> str:
    runner = _runner_label(str(payload.get("runner") or ""))
    system = payload.get("environment", {}).get("system") or "unknown-os"
    mode = payload.get("summary", {}).get("live_model_pilot", {}).get("mode") or "sample"
    return f"[CONTRIBUTOR RUN] LS Network Precision / {runner} / {system} / {mode}"


def _readme(payload: dict[str, Any], *, include_full_json: bool) -> str:
    summary = payload["summary"]
    live = summary["live_model_pilot"]
    conductor_noise = summary["conductor_noise"]
    return "\n".join(
        [
            "# LS Contributor Pack",
            "",
            f"Pack version: `{PACK_VERSION}`",
            f"Report version: `{payload['report_version']}`",
            "",
            "## What To Submit",
            "",
            "Open a new GitHub issue with the `Network Precision Contributor Run` template.",
            "",
            "Suggested title:",
            "",
            "```text",
            _issue_title(payload),
            "```",
            "",
            "Copy this file into the issue body:",
            "",
            "```text",
            "issue_body.md",
            "```",
            "",
            "Keep `network_precision_contributor_report.json` for exact machine-readable details.",
            "",
            "## Quick Summary",
            "",
            f"- full_stack_score: {summary['full_stack_score']}",
            f"- network_precision_gain_over_baseline: {summary['network_precision_gain_over_baseline']}",
            f"- observer_velocity_multiplier: {summary['network_trajectory']['observer_velocity_multiplier']}x",
            f"- conductor_noise_decision: {conductor_noise['decision']}",
            f"- live_model_pilot_decision: {live['decision']}",
            f"- live_model_pilot_score: {live['pilot_precision_proxy']}",
            f"- route_memory_persisted: {live['route_memory_persisted']}",
            "",
            "## Files",
            "",
            "- `issue_body.md`: copy-paste issue body.",
            "- `network_precision_contributor_report.md`: readable report.",
            "- `network_precision_contributor_report.json`: full structured payload.",
            "- `pack_summary.json`: small index for tools.",
            "",
            "## Boundary",
            "",
            payload["boundary"],
            "",
            "Full JSON embedded in Markdown: "
            + ("yes" if include_full_json else "no"),
            "",
        ]
    )


def build_pack_payload(
    *,
    runner: str = "",
    live: bool = False,
    max_tokens: int = 180,
    include_full_json: bool = False,
) -> dict[str, Any]:
    report = build_report_payload(
        runner=runner,
        live_roster=live,
        max_tokens=max_tokens,
    )
    issue_body = render_markdown(report, include_full_json=include_full_json)
    readme = _readme(report, include_full_json=include_full_json)
    return {
        "pack_version": PACK_VERSION,
        "issue_title": _issue_title(report),
        "runner": report["runner"],
        "created_at_utc": report["created_at_utc"],
        "live": live,
        "report": report,
        "issue_body": issue_body,
        "readme": readme,
        "summary": {
            "report_version": report["report_version"],
            "network_precision_gain_over_baseline": report["summary"]["network_precision_gain_over_baseline"],
            "conductor_noise_decision": report["summary"]["conductor_noise"]["decision"],
            "live_model_pilot_decision": report["summary"]["live_model_pilot"]["decision"],
            "route_memory_persisted": report["summary"]["live_model_pilot"]["route_memory_persisted"],
        },
    }


def write_pack(
    payload: dict[str, Any],
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    make_zip: bool = False,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = payload["report"]
    files = {
        "README.md": payload["readme"],
        "issue_body.md": payload["issue_body"],
        "network_precision_contributor_report.md": payload["issue_body"],
        "network_precision_contributor_report.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        "pack_summary.json": json.dumps(
            {
                "pack_version": payload["pack_version"],
                "issue_title": payload["issue_title"],
                "runner": payload["runner"],
                "created_at_utc": payload["created_at_utc"],
                "summary": payload["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    }
    written: dict[str, str] = {}
    for name, content in files.items():
        path = output_dir / name
        path.write_text(content, encoding="utf-8")
        written[name] = str(path)

    if make_zip:
        zip_path = output_dir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(output_dir / name, arcname=name)
        written["zip"] = str(zip_path)
    return written


def _print_text(payload: dict[str, Any], written: dict[str, str]) -> None:
    print("LS Contributor Pack")
    print(f"Pack version: {payload['pack_version']}")
    print(f"Issue title: {payload['issue_title']}")
    print()
    print("Files:")
    for name, path in written.items():
        print(f"- {name}: {path}")
    print()
    print("Summary:")
    for key, value in payload["summary"].items():
        print(f"- {key}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a complete LS contributor pack.")
    parser.add_argument("--runner", default="", help="GitHub handle or pseudonym.")
    parser.add_argument("--live", action="store_true", help="Call configured live routes.")
    parser.add_argument("--max-tokens", type=int, default=180)
    parser.add_argument("--include-full-json", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--zip", action="store_true", help="Also create a zip archive.")
    parser.add_argument("--json", action="store_true", help="Print pack metadata as JSON.")
    args = parser.parse_args()

    payload = build_pack_payload(
        runner=args.runner,
        live=args.live,
        max_tokens=args.max_tokens,
        include_full_json=args.include_full_json,
    )
    written = write_pack(payload, output_dir=args.output_dir, make_zip=args.zip)
    result = {
        "pack_version": payload["pack_version"],
        "report_version": payload["summary"]["report_version"],
        "issue_title": payload["issue_title"],
        "summary": payload["summary"],
        "files": written,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(payload, written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
