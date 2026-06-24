#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_catalog_trigger import (  # noqa: E402
    process_identity_catalog_triggers,
    reconcile_timeline_commit_receipts,
)


KEYRING_ENV = "LS_IDENTITY_CATALOG_KEYRING_JSON"
VISIBILITY_ENV = "LS_IDENTITY_VISIBILITY_JSON"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process durable identity timeline commit publication requests.",
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, required=True)
    parser.add_argument("--publisher-output-root", type=Path, required=True)
    parser.add_argument("--trigger-output-root", type=Path, required=True)
    parser.add_argument("--active-key-id", required=True)
    parser.add_argument(
        "--signing-key-id",
        action="append",
        dest="signing_key_ids",
        required=True,
    )
    parser.add_argument("--audience", required=True)
    parser.add_argument("--processed-at", required=True)
    parser.add_argument("--stale-after-seconds", type=int, default=86400)
    parser.add_argument(
        "--skip-reconcile",
        action="store_true",
        help="Do not recover complete bundles that missed outbox delivery.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.skip_reconcile:
        reconcile_timeline_commit_receipts(
            args.data_root,
            args.outbox,
            reconciled_at=args.processed_at,
        )
    result = process_identity_catalog_triggers(
        args.data_root,
        args.outbox,
        args.publisher_output_root,
        args.trigger_output_root,
        keyring=_keyring_from_environment(),
        active_key_id=args.active_key_id,
        signing_key_ids=tuple(args.signing_key_ids),
        audience=args.audience,
        visibility_policy=_visibility_from_environment(),
        processed_at=args.processed_at,
        stale_after_seconds=args.stale_after_seconds,
    )
    publication = result.publication.publication if result.publication else None
    summary = {
        "published": publication is not None,
        "publication_changed": (
            result.publication.changed if result.publication is not None else False
        ),
        "generation": publication.generation if publication else None,
        "publication_digest": (
            publication.publication_digest if publication else None
        ),
        "processed_request_ids": list(result.processed_request_ids),
        "pending_request_ids": list(result.pending_request_ids),
        "quarantined": list(result.quarantined),
        "trigger_batch_path": (
            str(result.trigger_batch_path) if result.trigger_batch_path else None
        ),
        "health_path": str(result.health_path),
        "state_path": str(result.state_path),
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


def _keyring_from_environment() -> Mapping[str, bytes]:
    raw = os.environ.get(KEYRING_ENV, "")
    if not raw:
        raise SystemExit(f"{KEYRING_ENV} must be set")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not payload:
        raise SystemExit(f"{KEYRING_ENV} must contain a non-empty JSON object")
    return {
        str(key): str(value).encode("utf-8")
        for key, value in payload.items()
    }


def _visibility_from_environment() -> Mapping[str, Sequence[str]]:
    raw = os.environ.get(VISIBILITY_ENV, "{}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SystemExit(f"{VISIBILITY_ENV} must contain a JSON object")
    result = {}
    for agent_id, audiences in payload.items():
        if not isinstance(audiences, list) or not audiences:
            raise SystemExit(
                f"visibility for {agent_id!r} must be a non-empty JSON array"
            )
        result[str(agent_id)] = tuple(str(value) for value in audiences)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
