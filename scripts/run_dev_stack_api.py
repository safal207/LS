"""Run Reflection (8780) and HCP (8781) HTTP APIs in a single process (one terminal)."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from dataclasses import dataclass
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))


@dataclass
class ServerContext:
    host: str
    port: int
    state_path: str
    servers: list[HTTPServer]
    bootstrap_entry: str | None = None
    bootstrap_app_name: str = "console"


def _serve_reflection(ctx: ServerContext) -> None:
    from agent.reflection_dashboard_api import create_handler, create_service

    service = create_service(state_path=ctx.state_path)
    handler = create_handler(lambda: service)
    httpd = HTTPServer((ctx.host, ctx.port), handler)
    ctx.servers.append(httpd)
    print(f"Reflection API http://{ctx.host}:{ctx.port} (state: {ctx.state_path})")
    httpd.serve_forever()


def _serve_hcp(ctx: ServerContext) -> None:
    from modules.hcp_marketplace.http_api import create_handler
    from modules.hcp_marketplace.service import HcpMarketplaceService
    from modules.hcp_marketplace.store import load_store_with_seed

    store = load_store_with_seed(Path(ctx.state_path))
    service = HcpMarketplaceService(store)
    plugin_manager = None
    if ctx.bootstrap_entry:
        from modules.shared.bootstrap import bootstrap_app
        from modules.shared.plugin_manager import PluginManager

        bt_ctx = bootstrap_app(ctx.bootstrap_entry, ctx.bootstrap_app_name)
        plugin_manager = PluginManager(bt_ctx)
    handler = create_handler(lambda: service, plugin_manager=plugin_manager)
    httpd = HTTPServer((ctx.host, ctx.port), handler)
    ctx.servers.append(httpd)
    mode = "with PluginManager" if plugin_manager else "catalog-only"
    print(f"HCP API http://{ctx.host}:{ctx.port} (state: {ctx.state_path}, {mode})")
    httpd.serve_forever()


def main() -> None:
    p = argparse.ArgumentParser(description="Reflection + HCP dev APIs in one process")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--reflection-port", type=int, default=8780)
    p.add_argument("--hcp-port", type=int, default=8781)
    p.add_argument("--reflection-state", default="reflection_state.json")
    p.add_argument("--hcp-state", default="hcp_marketplace.json")
    p.add_argument("--bootstrap", default=None, help="HCP: app main.py for PluginManager (optional)")
    p.add_argument("--app", default="console", help="bootstrap app name for HCP --bootstrap")
    args = p.parse_args()

    servers: list[HTTPServer] = []
    ctx_ref = ServerContext(
        host=args.host,
        port=args.reflection_port,
        state_path=args.reflection_state,
        servers=servers,
    )
    ctx_hcp = ServerContext(
        host=args.host,
        port=args.hcp_port,
        state_path=args.hcp_state,
        servers=servers,
        bootstrap_entry=args.bootstrap,
        bootstrap_app_name=args.app,
    )
    t_ref = threading.Thread(
        target=_serve_reflection,
        args=(ctx_ref,),
        name="reflection-api",
        daemon=True,
    )
    t_hcp = threading.Thread(
        target=_serve_hcp,
        args=(ctx_hcp,),
        name="hcp-api",
        daemon=True,
    )
    t_ref.start()
    t_hcp.start()
    time.sleep(0.3)
    if not t_ref.is_alive() or not t_hcp.is_alive():
        print("A server thread exited early — check the log above for bind errors.", file=sys.stderr)
        for s in servers:
            s.shutdown()
        raise SystemExit(1)

    print("Ctrl+C to stop both APIs.", flush=True)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down…", flush=True)
    for s in servers:
        try:
            s.shutdown()
        except Exception:
            pass
    t_ref.join(timeout=3.0)
    t_hcp.join(timeout=3.0)


if __name__ == "__main__":
    main()
