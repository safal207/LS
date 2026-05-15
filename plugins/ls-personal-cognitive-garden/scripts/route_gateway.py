from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
for candidate in (ROOT, Path.cwd()):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from ls.continuity import ContinuityInput, detect_continuity  # noqa: E402


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


def _write_jsonl(path: str, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _print_continuity_summary(event: dict[str, Any]) -> None:
    print(f"Session continuity: {event.get('continuity_status', 'unknown')}")
    print(f"Rupture detected: {event.get('rupture_detected', 'unknown')}")
    print(f"Rupture type: {event.get('rupture_type', 'unknown')}")
    print(f"Hallucination risk: {event.get('hallucination_risk', 'unknown')}")
    print(f"Decision: {event.get('governance_decision', 'unknown')}")
    print(f"Repair prompt: {event.get('repair_prompt', '')}")
    missing_context = event.get("missing_context") or []
    if missing_context:
        print("Missing context:")
        for item in missing_context:
            print(f"  - {item}")


def _print_summary(payload: dict[str, Any]) -> None:
    continuity = payload.get("session_continuity")
    if continuity:
        _print_continuity_summary(continuity)
        print("")

    gate = payload.get("action_evidence_gate") or {}
    pcg = payload.get("personal_cognitive_garden_update")
    acceptance = payload.get("personal_cognitive_garden_acceptance")
    rejection = payload.get("personal_cognitive_garden_rejection")
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
    if rejection:
        print(f"PCG rejected: {rejection.get('rejected')}")
        print(f"Rejected artifact: {rejection.get('artifact')}")


def _print_inbox(payload: dict[str, Any]) -> None:
    counts = payload.get("counts") or {}
    print(
        "PCG Inbox: "
        f"{counts.get('total', 0)} total, "
        f"{counts.get('proposed', 0)} proposed, "
        f"{counts.get('accepted', 0)} accepted, "
        f"{counts.get('rejected', 0)} rejected"
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
    parser.add_argument("--reject", action="store_true", help="Reject an emitted PCG proposal after routing.")
    parser.add_argument("--reviewer", default="operator", help="Reviewer name for --accept.")
    parser.add_argument("--review-note", default="", help="Optional note recorded with --accept or required with --reject.")
    parser.add_argument("--continuity", action="store_true", help="Run the local session-continuity check before routing.")
    parser.add_argument(
        "--emit-continuity-event",
        action="store_true",
        help="Include the session-continuity event in JSON output and summaries.",
    )
    parser.add_argument("--continuity-jsonl", help="Append the session-continuity event to a JSONL file.")
    parser.add_argument(
        "--skip-remote-gateway",
        action="store_true",
        help="Run local checks only and skip the remote /v1/chat request.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON response.")
    args = parser.parse_args()

    response: dict[str, Any] = {}
    continuity_event: dict[str, Any] | None = None

    if args.continuity or args.emit_continuity_event or args.continuity_jsonl:
        continuity_event = detect_continuity(
            ContinuityInput(
                prompt=args.prompt,
                raw_output=args.raw_output,
                agent_id=args.agent_id,
                agent_type=args.agent_type,
            )
        ).to_dict()
        if args.emit_continuity_event or args.continuity:
            response["session_continuity"] = continuity_event
        if args.continuity_jsonl:
            _write_jsonl(args.continuity_jsonl, continuity_event)

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

        if args.accept and args.reject:
            raise RuntimeError("Use either --accept or --reject, not both.")
        if not args.skip_remote_gateway:
            payload = {
                "prompt": args.prompt,
                "raw_output": args.raw_output,
                "agent_id": args.agent_id,
                "agent_type": args.agent_type,
            }
            remote_response = _request_json(f"{base_url}/v1/chat", payload)
            response.update(remote_response)
            if continuity_event and (args.emit_continuity_event or args.continuity):
                response["session_continuity"] = continuity_event

            if args.accept or args.reject:
                proposal = response.get("personal_cognitive_garden_update")
                if not proposal:
                    raise RuntimeError("No Personal Cognitive Garden proposal was emitted, so nothing can be reviewed.")
            if args.accept:
                response["personal_cognitive_garden_acceptance"] = _request_json(
                    f"{base_url}/v1/pcg/accept",
                    {
                        "proposal": proposal,
                        "reviewer": args.reviewer,
                        "review_note": args.review_note,
                    },
                )
            if args.reject:
                if not args.review_note.strip():
                    raise RuntimeError("--review-note is required when using --reject.")
                response["personal_cognitive_garden_rejection"] = _request_json(
                    f"{base_url}/v1/pcg/reject",
                    {
                        "proposal": proposal,
                        "reviewer": args.reviewer,
                        "review_note": args.review_note,
                    },
                )
        elif args.accept or args.reject:
            raise RuntimeError("--accept and --reject require the remote gateway; remove --skip-remote-gateway.")
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
