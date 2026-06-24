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

from modules.trusted_runtime.identity_catalog_publisher import (  # noqa: E402
    publish_identity_catalog,
)


KEYRING_ENV = "LS_IDENTITY_CATALOG_KEYRING_JSON"
VISIBILITY_ENV = "LS_IDENTITY_VISIBILITY_JSON"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Atomically publish a monotonic signed LS identity catalog.",
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--active-key-id", required=True)
    parser.add_argument(
        "--signing-key-id",
        action="append",
        dest="signing_key_ids",
        required=True,
        help="Key ID used to sign the publication. Repeat during rotation.",
    )
    parser.add_argument("--audience", required=True)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--stale-after-seconds", type=int, default=86400)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keyring = _keyring_from_environment()
    visibility = _visibility_from_environment()
    result = publish_identity_catalog(
        args.data_root,
        args.output_root,
        keyring=keyring,
        active_key_id=args.active_key_id,
        signing_key_ids=tuple(args.signing_key_ids),
        audience=args.audience,
        visibility_policy=visibility,
        published_at=args.published_at,
        stale_after_seconds=args.stale_after_seconds,
    )
    publication = result.publication
    print(
        json.dumps(
            {
                "changed": result.changed,
                "generation": publication.generation,
                "publication_digest": publication.publication_digest,
                "entry_count": len(publication.entries),
                "authoritative_entry_count": sum(
                    1 for entry in publication.entries if entry.authoritative
                ),
                "active_key_id": publication.active_key_id,
                "accepted_key_ids": list(publication.accepted_key_ids),
                "publication_path": str(result.publication_path),
                "legacy_catalog_path": str(result.legacy_catalog_path),
                "history_path": str(result.history_path),
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def _keyring_from_environment() -> Mapping[str, bytes]:
    raw = os.environ.get(KEYRING_ENV, "")
    if not raw:
        raise SystemExit(f"{KEYRING_ENV} must be set")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not payload:
        raise SystemExit(f"{KEYRING_ENV} must contain a non-empty JSON object")
    return {str(key): str(value).encode("utf-8") for key, value in payload.items()}


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
