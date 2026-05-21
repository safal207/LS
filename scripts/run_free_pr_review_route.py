from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pr_review_trail_artifact import build_pr_review_artifact  # noqa: E402


ROLE_DEFINITIONS = [
    {
        "role": "draft_reviewer",
        "purpose": "Summarize the diff surface and likely intent using only visible evidence.",
        "return_fields": ["intent", "changed_surface", "uncertainties"],
    },
    {
        "role": "risk_critic",
        "purpose": "Look for risky state changes, missing tests, unsafe commands, and unsupported assumptions.",
        "return_fields": ["findings", "severity", "evidence"],
    },
    {
        "role": "evidence_verifier",
        "purpose": "Verify whether each finding is grounded in the diff, stat, or explicit artifact signal.",
        "return_fields": ["supported_findings", "unsupported_findings", "missing_evidence"],
    },
    {
        "role": "final_reviewer",
        "purpose": "Produce a concise human-facing review decision and next action.",
        "return_fields": ["decision", "summary", "next_action"],
    },
]


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _role_prompt(role: dict[str, Any], artifact: dict[str, Any]) -> str:
    signals = artifact.get("signals") or []
    files = artifact.get("files") or []
    diff_excerpt = artifact.get("diff_excerpt") or ""
    output_schema = {field: "..." for field in role["return_fields"]}
    return "\n".join(
        [
            f"You are the `{role['role']}` in an LS free-only PR review route.",
            "",
            "Do not call paid APIs. Do not invent evidence. Use only the artifact below.",
            role["purpose"],
            "",
            f"Diff source: {artifact.get('diff_source')}",
            f"Selected route: {artifact.get('selected_route', {}).get('route_key')}",
            f"Current LS decision: {artifact.get('decision')}",
            "",
            "Files:",
            _compact_json(files),
            "",
            "Signals:",
            _compact_json(signals),
            "",
            "Git stat:",
            artifact.get("stat") or "(none)",
            "",
            "Diff excerpt:",
            "```diff",
            diff_excerpt[:6000],
            "```",
            "",
            "Return JSON only with this shape:",
            _compact_json(output_schema),
        ]
    )


def build_free_route_packet(artifact: dict[str, Any]) -> dict[str, Any]:
    role_prompts = []
    for role in ROLE_DEFINITIONS:
        role_prompts.append(
            {
                "role": role["role"],
                "purpose": role["purpose"],
                "free_execution": [
                    "paste into the current Codex session",
                    "paste into a local Ollama model",
                    "use as a checklist for human review",
                ],
                "prompt": _role_prompt(role, artifact),
            }
        )

    return {
        "artifact_type": "ls.free_pr_review_route_packet.v0.1",
        "no_paid_model_api_calls": True,
        "free_options": [
            {
                "name": "current_codex_session",
                "description": "Use the active Codex session as one role in the route, then let LS score the artifact.",
            },
            {
                "name": "local_model",
                "description": "Paste a role prompt into a local model such as Ollama; LS still owns the artifact and scoring.",
            },
            {
                "name": "deterministic_only",
                "description": "Use only LS diff signals, route selection, and human review without a model call.",
            },
        ],
        "source_artifact": {
            "artifact_type": artifact.get("artifact_type"),
            "diff_source": artifact.get("diff_source"),
            "decision": artifact.get("decision"),
            "selected_route": artifact.get("selected_route"),
            "route_reward": artifact.get("route_reward"),
            "signals": artifact.get("signals"),
            "human_summary": artifact.get("human_summary"),
        },
        "role_prompts": role_prompts,
        "operator_next_steps": [
            "Run one or more role prompts in the current Codex session or a local model.",
            "Paste role outputs into the PR, report, or a future contribution-ledger scorer.",
            "Keep LS advisory-only until a human accepts the review decision.",
        ],
    }


def render_markdown(packet: dict[str, Any]) -> str:
    source = packet["source_artifact"]
    lines = [
        "# LS Free PR Review Route Packet",
        "",
        "This packet uses no paid model API calls inside LS.",
        "",
        "## Source",
        "",
        f"- Diff source: `{source['diff_source']}`",
        f"- LS decision: `{source['decision']}`",
        f"- Selected route: `{source['selected_route']['route_key']}`",
        f"- Route reward: `{source['route_reward']}`",
        "",
        "## Free Options",
        "",
    ]
    for option in packet["free_options"]:
        lines.append(f"- `{option['name']}`: {option['description']}")

    lines.extend(["", "## LS Summary", "", source["human_summary"], "", "## Signals", ""])
    for signal in source.get("signals") or []:
        lines.append(f"- `{signal['severity']}` `{signal['code']}`: {signal['message']}")

    lines.extend(["", "## Role Prompts", ""])
    for item in packet["role_prompts"]:
        lines.extend(
            [
                f"### {item['role']}",
                "",
                item["purpose"],
                "",
                "```text",
                item["prompt"],
                "```",
                "",
            ]
        )

    lines.extend(["## Operator Next Steps", ""])
    for step in packet["operator_next_steps"]:
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build a free-only LS PR review route packet.")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path.")
    parser.add_argument("--base", default="HEAD~1", help="Base revision.")
    parser.add_argument("--head", default="HEAD", help="Head revision.")
    parser.add_argument("--diff-file", type=Path, default=None, help="Read a saved diff instead of running git diff.")
    parser.add_argument("--store-path", type=Path, default=None, help="Route stats JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON packet.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown packet.")
    parser.add_argument("--json", action="store_true", help="Print full JSON packet.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-free-pr-review-") as tmp:
            artifact = build_pr_review_artifact(
                repo=args.repo.resolve(),
                base=args.base,
                head=args.head,
                diff_file=args.diff_file,
                store_path=Path(tmp) / "routes.json",
                max_diff_chars=12000,
            )
    else:
        artifact = build_pr_review_artifact(
            repo=args.repo.resolve(),
            base=args.base,
            head=args.head,
            diff_file=args.diff_file,
            store_path=args.store_path,
            max_diff_chars=12000,
        )

    packet = build_free_route_packet(artifact)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(packet), encoding="utf-8")

    if args.json:
        print(json.dumps(packet, ensure_ascii=False, indent=2))
    else:
        source = packet["source_artifact"]
        print("LS free PR review route packet")
        print("No paid model API calls: true")
        print(f"Diff source: {source['diff_source']}")
        print(f"Selected route: {source['selected_route']['route_key']}")
        print(f"LS decision: {source['decision']}")
        print("Free roles: " + ", ".join(item["role"] for item in packet["role_prompts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
