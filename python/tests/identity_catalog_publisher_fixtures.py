from __future__ import annotations

from pathlib import Path
from typing import Any

from identity_timeline_api_fixtures import build_timeline_bundle


OLD_KEY = b"publisher-old-key-material"
NEW_KEY = b"publisher-new-key-material"
KEYRING = {"key-old": OLD_KEY, "key-new": NEW_KEY}


def build_publisher_fixture(
    root: Path,
    *,
    agent_ids: tuple[str, ...] = ("agent:publisher-alpha", "agent:publisher-beta"),
) -> dict[str, Any]:
    data_root = root / "data"
    output_root = root / "published"
    bundles = [build_timeline_bundle(data_root, agent_id) for agent_id in agent_ids]
    visibility = {agent_id: ("internal",) for agent_id in agent_ids}
    return {
        "data_root": data_root,
        "output_root": output_root,
        "bundles": bundles,
        "visibility": visibility,
        "keyring": dict(KEYRING),
    }
