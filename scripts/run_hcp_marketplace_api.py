"""Run HCP Marketplace HTTP API (internal credits, catalog, purchase/install)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from modules.hcp_marketplace.http_api import run_hcp_marketplace_api  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8781)
    p.add_argument("--state", default="hcp_marketplace.json")
    args = p.parse_args()
    run_hcp_marketplace_api(host=args.host, port=args.port, state_path=args.state)


if __name__ == "__main__":
    main()
