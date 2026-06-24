#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from wsgiref.simple_server import make_server


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_live_viewer import (  # noqa: E402
    build_signed_catalog_identity_viewer,
)


SECRET_ENV = "LS_IDENTITY_CATALOG_SECRET"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the signed read-only LS Identity Timeline viewer.",
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    secret = os.environ.get(SECRET_ENV, "").encode("utf-8")
    if not secret:
        raise SystemExit(f"{SECRET_ENV} must be set")
    app = build_signed_catalog_identity_viewer(
        args.data_root,
        args.catalog,
        secret=secret,
    )
    with make_server(args.host, args.port, app) as server:
        print(f"Read-only Identity Timeline viewer: http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
