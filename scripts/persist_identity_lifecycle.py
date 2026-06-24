#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_timeline import (  # noqa: E402
    persist_identity_lifecycle,
    replay_identity_timeline,
)
from modules.trusted_runtime.persistence import JsonlEventStoreAdapter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist and replay one governed identity lifecycle.",
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-id", default="agent:trusted-reviewer")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    event_store_path = output / "identity-events.jsonl"
    if event_store_path.exists():
        event_store_path.unlink()
    store = JsonlEventStoreAdapter(event_store_path)

    records = {
        "profile_v1": _read(source / "identity-profile-v1.json"),
        "proposal": _read(source.parent / "governance-proposal" / "identity-update-proposal.json"),
        "approval": _read(source / "identity-update-approval.json"),
        "patch": _optional_read(source / "identity-profile-patch.json"),
        "commit": _optional_read(source / "identity-patch-commit.json"),
        "application": _optional_read(source / "identity-application.json"),
        "profile_v2": _optional_read(source / "identity-profile-v2.json"),
        "rollback": _optional_read(source / "identity-rollback.json"),
        "profile_v3": _optional_read(source / "identity-profile-v3-rollback.json"),
    }
    refs = persist_identity_lifecycle(
        store,
        agent_id=args.agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
        patch=records["patch"],
        commit=records["commit"],
        application=records["application"],
        profile_v2=records["profile_v2"],
        rollback=records["rollback"],
        profile_v3=records["profile_v3"],
    )
    timeline = replay_identity_timeline(store, agent_id=args.agent_id)
    timeline_payload = timeline.to_dict()
    _write(output / "identity-timeline.json", timeline_payload)
    summary = {
        "agent_id": args.agent_id,
        "status": timeline.status.value,
        "event_count": len(timeline.events),
        "profile_version_count": len(timeline.profile_versions),
        "active_profile_version": timeline.active_profile["version"],
        "application_count": len(timeline.application_refs),
        "rollback_count": len(timeline.rollback_refs),
        "side_effects_applied_during_replay": timeline.side_effects_applied,
        "event_refs": list(refs),
        "event_store_path": str(event_store_path),
        "timeline_path": str(output / "identity-timeline.json"),
        "timeline_digest": timeline_payload["integrity"]["timeline_digest"],
    }
    _write(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def _read(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _optional_read(path: Path) -> Optional[Mapping[str, Any]]:
    return _read(path) if path.exists() else None


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
