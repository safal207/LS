#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_control_plane_acceptance import (  # noqa: E402
    run_identity_control_plane_acceptance,
)
from modules.trusted_runtime.identity_control_plane_viewer import (  # noqa: E402
    IdentityControlPlaneStatusRepository,
)


KEYRING_ENV = "LS_IDENTITY_CATALOG_KEYRING_JSON"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the complete LS Identity Control Plane acceptance bundle.",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--active-key-id", required=True)
    parser.add_argument(
        "--signing-key-id",
        action="append",
        dest="signing_key_ids",
        required=True,
    )
    parser.add_argument("--audience", default="internal")
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keyring = _keyring_from_environment()
    result = run_identity_control_plane_acceptance(
        args.output_root,
        keyring=keyring,
        active_key_id=args.active_key_id,
        signing_key_ids=tuple(args.signing_key_ids),
        audience=args.audience,
        reset=args.reset,
    )
    dashboard_source = (
        PYTHON_ROOT / "modules" / "trusted_runtime" / "identity_control_plane_dashboard"
    )
    dashboard_target = result.output_root / "dashboard"
    if dashboard_target.exists():
        shutil.rmtree(dashboard_target)
    shutil.copytree(
        dashboard_source,
        dashboard_target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "__init__.py"),
    )

    status = IdentityControlPlaneStatusRepository(
        result.publisher_output_root,
        result.trigger_output_root,
        keyring=keyring,
        acceptance_manifest_path=result.manifest_path,
    ).status()
    api_root = result.output_root / "api"
    api_root.mkdir(parents=True, exist_ok=True)
    (api_root / "control-plane-status.json").write_text(
        json.dumps(status, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "result": "PASS",
        "output_root": str(result.output_root),
        "manifest": str(result.manifest_path),
        "dashboard": str(dashboard_target / "index.html"),
        "control_plane_status": str(api_root / "control-plane-status.json"),
        "first_generation": result.first_generation,
        "identical_replay_generation": result.repeated_generation,
        "second_generation": result.second_generation,
        "tamper_report": str(result.tamper_report_path),
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
    return {str(key): str(value).encode("utf-8") for key, value in payload.items()}


if __name__ == "__main__":
    raise SystemExit(main())
