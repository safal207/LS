from __future__ import annotations

from typing import Any

from .store import HcpMarketplaceStore


class HcpMarketplaceService:
    """Catalog, purchase with internal credits, install into runtime (manifest handoff)."""

    def __init__(self, store: HcpMarketplaceStore) -> None:
        self._store = store

    def list_items(self) -> list[dict[str, Any]]:
        return [i.to_dict() for i in self._store.list_items()]

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        it = self._store.get_item(item_id)
        return it.to_dict() if it else None

    def get_credits(self, instance_id: str) -> dict[str, Any]:
        return {
            "instance_id": instance_id,
            "credits": self._store.credits(instance_id),
        }

    def purchase(self, item_id: str, instance_id: str) -> dict[str, Any]:
        item = self._store.get_item(item_id)
        if item is None:
            return {"status": "error", "reason": "unknown_item"}
        if self._store.has_purchased(instance_id, item_id):
            return {"status": "ok", "dedup": True, "item_id": item_id, "credits": self._store.credits(instance_id)}
        price = item.price_credits
        if not self._store.deduct_credits(instance_id, price):
            return {
                "status": "error",
                "reason": "insufficient_credits",
                "required": price,
                "credits": self._store.credits(instance_id),
            }
        self._store.add_purchase(instance_id, item_id)
        return {
            "status": "ok",
            "item_id": item_id,
            "credits": self._store.credits(instance_id),
        }

    def install(self, item_id: str, instance_id: str) -> dict[str, Any]:
        """Record install; returns plugin id for PluginManager (caller loads module)."""
        if not self._store.has_purchased(instance_id, item_id):
            return {"status": "error", "reason": "not_purchased"}
        item = self._store.get_item(item_id)
        if item is None:
            return {"status": "error", "reason": "unknown_item"}
        if self._store.is_installed(instance_id, item_id):
            return {
                "status": "ok",
                "idempotent": True,
                "plugin_id": item.plugin_id,
                "version": item.version,
            }
        self._store.mark_installed(instance_id, item_id)
        return {
            "status": "ok",
            "plugin_id": item.plugin_id,
            "version": item.version,
            "load_hint": f"importlib metadata entry: {item.plugin_id}",
        }
