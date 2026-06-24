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

from modules.trusted_runtime.identity_catalog_trigger import (  # noqa: E402
    finalize_identity_timeline_commit,
)
from modules.trusted_runtime.identity_timeline import (  # noqa: E402
    persist_identity_lifecycle,
)
from modules.trusted_runtime.persistence import JsonlEventStoreAdapter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Persist one governed identity lifecycle, commit its projection, "
            "and enqueue catalog publication."
        ),
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--agent-id", default="agent:trusted-reviewer")
    parser.add_argument("--catalog-data-root", type=Path)
    parser.add_argument("--publication-outbox", type=Path)
    parser.add_argument("--committed-at")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    data_root = (args.catalog_data_root or output.parent).resolve()
    outbox_path = args.publication_outbox or (
        data_root / "identity-catalog-publication-outbox.jsonl"
    )
    event_store_path = output / "identity-events.jsonl"
    if event_store_path.exists():
        event_store_path.unlink()
    store = JsonlEventStoreAdapter(event_store_path)

    records = {
        "profile_v1": _read(source / "identity-profile-v1.json"),
        "proposal": _read(
            source.parent
            / "governance-proposal"
            / "identity-update-proposal.json"
        ),
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
    committed_at = args.committed_at or _latest_record_time(records)
    receipt, outbox_event_ref = finalize_identity_timeline_commit(
        store,
        agent_id=args.agent_id,
        bundle_root=output,
        data_root=data_root,
        outbox_path=outbox_path,
        committed_at=committed_at,
    )
    timeline_payload = _read(output / "identity-timeline.json")
    summary = {
        "agent_id": args.agent_id,
        "status": timeline_payload["status"],
        "event_count": timeline_payload["integrity"]["event_count"],
        "profile_version_count": len(timeline_payload["profile_versions"]),
        "active_profile_version": timeline_payload["active_profile"]["version"],
        "application_count": len(timeline_payload["application_refs"]),
        "rollback_count": len(timeline_payload["rollback_refs"]),
        "side_effects_applied_during_replay": timeline_payload[
            "side_effects_applied"
        ],
        "event_refs": list(refs),
        "event_store_path": str(event_store_path),
        "timeline_path": str(output / "identity-timeline.json"),
        "timeline_commit_path": str(output / "identity-timeline-commit.json"),
        "timeline_digest": receipt.timeline_digest,
        "publication_request_id": receipt.request_id,
        "publication_outbox_path": str(outbox_path),
        "publication_outbox_event_ref": outbox_event_ref,
    }
    _write(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def _latest_record_time(records: Mapping[str, Optional[Mapping[str, Any]]]) -> str:
    candidates = (
        ("profile_v3", "created_at"),
        ("rollback", "rolled_back_at"),
        ("profile_v2", "created_at"),
        ("application", "activated_at"),
        ("commit", "committed_at"),
        ("approval", "decided_at"),
        ("proposal", "created_at"),
        ("profile_v1", "created_at"),
    )
    for record_name, key in candidates:
        record = records.get(record_name)
        if record is not None and record.get(key):
            return str(record[key])
    raise ValueError("identity lifecycle contains no commit timestamp")


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
