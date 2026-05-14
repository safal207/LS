from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _request_json(url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gateway returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gateway is not reachable: {exc.reason}") from exc


def _print_summary(payload: dict[str, Any]) -> None:
    gate = payload.get("action_evidence_gate") or {}
    pcg = payload.get("personal_cognitive_garden_update")
    acceptance = payload.get("personal_cognitive_garden_acceptance")
    print(f"LS decision: {gate.get('decision', 'unknown')}")
    print(f"Reason: {gate.get('stop_reason', 'unknown')}")
    print(f"Gateway mode: {payload.get('gateway_mode', 'unknown')}")
    print(f"PCG proposal: {'yes' if pcg else 'no'}")
    if pcg:
        governance = pcg.get("governance") or {}
        effect = pcg.get("development_effect") or {}
        print(f"PCG status: {pcg.get('status')}")
        print(f"Session class: {pcg.get('session_development_class')}")
        print(f"Human review required: {pcg.get('requires_human_review')}")
        print(f"Durable state allowed: {governance.get('durable_state_allowed')}")
        print("Skill delta:")
        for skill in effect.get("human_skill_delta") or []:
            print(f"  - {skill}")
    if acceptance:
        print(f"PCG accepted: {acceptance.get('accepted')}")
        print(f"Accepted artifact: {acceptance.get('artifact')}")


def _print_inbox(payload: dict[str, Any]) -> None:
    counts = payload.get("counts") or {}
    print(
        "PCG Inbox: "
        f"{counts.get('total', 0)} total, "
        f"{counts.get('proposed', 0)} proposed, "
        f"{counts.get('accepted', 0)} accepted"
    )
    for item in payload.get("items") or []:
        print("")
        print(f"- {item.get('garden_update_id')} [{item.get('status')}]")
        print(f"  class: {item.get('session_development_class')} / {item.get('node_family')}")
        print(f"  claim: {item.get('claim')}")
        print(f"  review required: {item.get('requires_human_review')}")
        print(f"  artifact: {item.get('artifact')}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Route an agent draft through the local LS gateway.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787", help="LS Web Agent Gateway base URL.")
    parser.add_argument("--health", action="store_true", help="Only check gateway health.")
    parser.add_argument("--inbox", action="store_true", help="List the local Personal Cognitive Garden inbox.")
    parser.add_argument(
        "--status",
        choices=("proposed", "accepted", "rejected"),
        help="Optional PCG inbox status filter.",
    )
    parser.add_argument("--prompt", default="Review this agent draft before showing it to the user.")
    parser.add_argument("--raw-output", default="")
    parser.add_argument("--agent-id", default="codex-plugin")
    parser.add_argument("--agent-type", default="codex")
    parser.add_argument("--accept", action="store_true", help="Accept an emitted PCG proposal after routing.")
    parser.add_argument("--reviewer", default="operator", help="Reviewer name for --accept.")
    parser.add_argument("--review-note", default="", help="Optional note recorded with --accept.")
    parser.add_argument("--json", action="store_true", help="Print full JSON response.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    try:
        if args.health:
            print(json.dumps(_request_json(f"{base_url}/health"), indent=2))
            return 0
        if args.inbox:
            suffix = f"?status={args.status}" if args.status else ""
            inbox = _request_json(f"{base_url}/v1/pcg/inbox{suffix}")
            if args.json:
                print(json.dumps(inbox, indent=2, ensure_ascii=False))
            else:
                _print_inbox(inbox)
            return 0

        payload = {
            "prompt": args.prompt,
            "raw_output": args.raw_output,
            "agent_id": args.agent_id,
            "agent_type": args.agent_type,
        }
        response = _request_json(f"{base_url}/v1/chat", payload)
        if args.accept:
            proposal = response.get("personal_cognitive_garden_update")
            if not proposal:
                raise RuntimeError("No Personal Cognitive Garden proposal was emitted, so nothing can be accepted.")
            response["personal_cognitive_garden_acceptance"] = _request_json(
                f"{base_url}/v1/pcg/accept",
                {
                    "proposal": proposal,
                    "reviewer": args.reviewer,
                    "review_note": args.review_note,
                },
            )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        _print_summary(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
