from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import HcpItem

_DEFAULT_STARTING_CREDITS = 1_000.0


def _demo_catalog() -> list[HcpItem]:
    """8 seed items for closed MVP (plan W4)."""
    return [
        HcpItem("hcp-safety-pack", "Safety fellowship pack", "Policy hints + LTP review templates.", 50.0, "plugin.safety.fellowship"),
        HcpItem("hcp-benchmark-kit", "Benchmark kit", "Operator delta scorecard import helpers.", 30.0, "plugin.benchmark.kit"),
        HcpItem("hcp-resonance-tune", "Resonance tuner", "Aligns memory graph weights for local runs.", 75.0, "plugin.resonance.tune"),
        HcpItem("hcp-council-export", "Council export", "JSON export for council scorecards.", 20.0, "plugin.council.export"),
        HcpItem("hcp-mesh-observe", "Mesh observe", "Extra mesh observability hooks (Python).", 40.0, "plugin.mesh.observe"),
        HcpItem("hcp-reflection-ui", "Reflection UI pack", "Operator theming for reflection panel.", 25.0, "plugin.reflection.ui"),
        HcpItem("hcp-ledger-sim", "Ledger simulator", "Dry-run economic ledger for tasks.", 35.0, "plugin.ledger.sim"),
        HcpItem("hcp-privacy-stub", "Privacy review stub", "Checklist extension for PII review.", 15.0, "plugin.privacy.stub"),
    ]


class HcpMarketplaceStore:
    """JSON-backed store: catalog, per-instance credit balance, purchases, installed plugin ids."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {
            "items": {},
            "credits": {},
            "purchases": [],
            "installed": {},
        }
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(raw, dict):
            self._data.update(
                {
                    "items": raw.get("items") if isinstance(raw.get("items"), dict) else {},
                    "credits": raw.get("credits") if isinstance(raw.get("credits"), dict) else {},
                    "purchases": raw.get("purchases") if isinstance(raw.get("purchases"), list) else [],
                    "installed": raw.get("installed") if isinstance(raw.get("installed"), dict) else {},
                }
            )

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    def is_catalog_empty(self) -> bool:
        with self._lock:
            return len(self._data["items"]) == 0

    def list_items(self) -> list[HcpItem]:
        with self._lock:
            return [HcpItem.from_dict({"item_id": k, **v}) for k, v in self._data["items"].items()]

    def get_item(self, item_id: str) -> HcpItem | None:
        with self._lock:
            raw = self._data["items"].get(item_id)
            if not isinstance(raw, dict):
                return None
            return HcpItem.from_dict({"item_id": item_id, **raw})

    def put_item(self, item: HcpItem) -> None:
        d = asdict(item)
        iid = d.pop("item_id")
        with self._lock:
            self._data["items"][iid] = d
            self._save()

    def credits(self, instance_id: str) -> float:
        with self._lock:
            if instance_id not in self._data["credits"]:
                self._data["credits"][instance_id] = _DEFAULT_STARTING_CREDITS
            return float(self._data["credits"][instance_id])

    def set_credits(self, instance_id: str, value: float) -> None:
        with self._lock:
            self._data["credits"][instance_id] = max(0.0, value)
            self._save()

    def deduct_credits(self, instance_id: str, amount: float) -> bool:
        with self._lock:
            cur = float(self._data["credits"].get(instance_id, _DEFAULT_STARTING_CREDITS))
            if instance_id not in self._data["credits"]:
                self._data["credits"][instance_id] = cur
            if cur < amount:
                return False
            self._data["credits"][instance_id] = cur - amount
            self._save()
        return True

    def add_purchase(self, instance_id: str, item_id: str) -> None:
        with self._lock:
            self._data["purchases"].append(
                {
                    "instance_id": instance_id,
                    "item_id": item_id,
                }
            )
            self._save()

    def has_purchased(self, instance_id: str, item_id: str) -> bool:
        with self._lock:
            for p in self._data["purchases"]:
                if not isinstance(p, dict):
                    continue
                if p.get("instance_id") == instance_id and p.get("item_id") == item_id:
                    return True
        return False

    def is_installed(self, instance_id: str, item_id: str) -> bool:
        with self._lock:
            inst = self._data["installed"].get(instance_id, [])
            return isinstance(inst, list) and item_id in inst

    def mark_installed(self, instance_id: str, item_id: str) -> None:
        with self._lock:
            inst_list = self._data["installed"].setdefault(instance_id, [])
            if not isinstance(inst_list, list):
                inst_list = []
                self._data["installed"][instance_id] = inst_list
            if item_id not in inst_list:
                inst_list.append(item_id)
            self._save()


def load_store_with_seed(path: Path) -> HcpMarketplaceStore:
    store = HcpMarketplaceStore(path)
    if store.is_catalog_empty():
        for it in _demo_catalog():
            store.put_item(it)
    return store
