from __future__ import annotations

import json
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

from modules.hcp_marketplace.http_api import create_handler
from modules.hcp_marketplace.service import HcpMarketplaceService
from modules.hcp_marketplace.store import load_store_with_seed
from modules.shared.bootstrap import bootstrap_app
from modules.shared.plugin_manager import PluginManager

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSOLE_MAIN = _REPO_ROOT / "apps" / "console" / "main.py"


def test_seed_has_catalog_items(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    store = load_store_with_seed(p)
    items = store.list_items()
    assert len(items) >= 8


def test_purchase_install_flow(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    store = load_store_with_seed(p)
    svc = HcpMarketplaceService(store)
    item_id = "hcp-privacy-stub"
    inst = "ls-test-1"
    price = svc.get_item(item_id)["price_credits"]
    before = svc.get_credits(inst)["credits"]
    r1 = svc.purchase(item_id, inst)
    assert r1["status"] == "ok"
    assert pytest.approx(before - price) == r1["credits"]
    r2 = svc.install(item_id, inst)
    assert r2["status"] == "ok"
    assert r2["plugin_id"]
    r3 = svc.install(item_id, inst)
    assert r3.get("idempotent") is True


def test_http_catalog_and_purchase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    state = Path("hcp.json")
    store = load_store_with_seed(state)
    service = HcpMarketplaceService(store)
    handler = create_handler(lambda: service)
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        base = f"http://127.0.0.1:{port}"

        def get(url: str) -> dict:
            with urllib.request.urlopen(url, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))

        def post(url: str, body: dict) -> dict:
            raw = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=raw,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))

        items = get(f"{base}/api/hcp/items")["items"]
        assert len(items) >= 8
        item_id = items[0]["item_id"]
        cred0 = get(f"{base}/api/hcp/credits?instance=t1")["credits"]
        out = post(f"{base}/api/hcp/purchase", {"item_id": item_id, "instance_id": "t1"})
        assert out["status"] == "ok"
        assert out["credits"] < cred0
        ins = post(f"{base}/api/hcp/install", {"item_id": item_id, "instance_id": "t1"})
        assert ins["status"] == "ok"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


def test_load_plugin_into_manager_echo_demo(tmp_path: Path) -> None:
    """After purchase+install, load_plugin_into_manager loads echo_plugin from python/plugins."""
    state = tmp_path / "m.json"
    store = load_store_with_seed(state)
    svc = HcpMarketplaceService(store)
    item_id = "hcp-runtime-echo"
    inst = "ls-demo"
    assert svc.purchase(item_id, inst)["status"] == "ok"
    assert svc.install(item_id, inst)["status"] == "ok"

    ctx = bootstrap_app(str(_CONSOLE_MAIN), "console")
    manager = PluginManager(ctx)
    out = svc.load_plugin_into_manager(item_id, inst, manager)
    assert out["status"] == "ok"
    assert out["loaded"] == "echo_plugin"
    assert "echo_plugin" in manager.list_loaded()
    manager.unload("echo_plugin")
