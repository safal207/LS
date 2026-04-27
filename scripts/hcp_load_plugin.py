"""Load a purchased+installed HCP item into PluginManager (CLI)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "python"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from modules.hcp_marketplace.service import HcpMarketplaceService  # noqa: E402
from modules.hcp_marketplace.store import load_store_with_seed  # noqa: E402
from modules.shared.bootstrap import bootstrap_app  # noqa: E402
from modules.shared.plugin_manager import PluginManager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Load HCP item plugin via PluginManager")
    parser.add_argument("--item", required=True, help="item_id (e.g. hcp-runtime-echo)")
    parser.add_argument("--instance", default="default", help="instance_id (must have purchase+install)")
    parser.add_argument("--state", default="hcp_marketplace.json", help="HCP JSON state path")
    parser.add_argument(
        "--bootstrap",
        default=str(ROOT / "apps" / "console" / "main.py"),
        help="App entry for RuntimeContext",
    )
    parser.add_argument("--app", default="console", help="bootstrap app name")
    args = parser.parse_args()

    store = load_store_with_seed(Path(args.state))
    svc = HcpMarketplaceService(store)
    ctx = bootstrap_app(args.bootstrap, args.app)
    manager = PluginManager(ctx)
    out = svc.load_plugin_into_manager(args.item, args.instance, manager)
    print(out)
    return 0 if out.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
