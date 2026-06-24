#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_catalog import (  # noqa: E402
    build_signed_identity_catalog,
    write_signed_identity_catalog,
)


SECRET_ENV = "LS_IDENTITY_CATALOG_SECRET"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a signed read-only LS identity catalog.",
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    secret = os.environ.get(SECRET_ENV, "").encode("utf-8")
    if not secret:
        raise SystemExit(f"{SECRET_ENV} must be set")
    catalog = build_signed_identity_catalog(
        args.data_root,
        secret=secret,
        key_id=args.key_id,
        generated_at=args.generated_at,
    )
    write_signed_identity_catalog(args.output, catalog)
    print(
        f"catalog={args.output} agents={len(catalog.entries)} "
        f"key_id={catalog.key_id} signature={catalog.signature}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
