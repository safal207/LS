from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HcpItem:
    """Marketplace item (plugin / capability pack) addressable at runtime."""

    item_id: str
    title: str
    description: str
    price_credits: float
    plugin_id: str
    version: str = "0.1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "price_credits": self.price_credits,
            "plugin_id": self.plugin_id,
            "version": self.version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HcpItem":
        return cls(
            item_id=str(data.get("item_id", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            price_credits=float(data.get("price_credits", 0.0) or 0.0),
            plugin_id=str(data.get("plugin_id", "")),
            version=str(data.get("version", "0.1.0")),
            metadata=dict(data.get("metadata") or {}),
        )
