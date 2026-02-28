from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    import lthread
except ImportError:
    # Fallback if not installed or during testing without full path setup
    try:
        from python.modules import lthread
    except ImportError:
        lthread = None

from . import with_file_lock


class MemoryService:
    """Persistent storage for Amygdala long-term state using JSON and file lock."""

    def __init__(self, user_id: str = "default", base_dir: str | Path = "~/.ghostgpt/memory") -> None:
        self.user_id = user_id or "default"
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / f"user_{self.user_id}.json"

    def load(self) -> dict[str, Any]:
        try:
            if not self.path.exists():
                return {}
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
            return {}

    def save(self, data: dict[str, Any]) -> None:
        def _write() -> None:
            safe_payload = dict(data)
            safe_payload["user_id"] = self.user_id
            self.path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with_file_lock(str(self.path), _write)

    def export_soul_secure(self, target_device_id: str) -> str:
        """Экспорт души через L-THREAD с постквантовым шифрованием и ZK-proof."""
        if not lthread:
            raise ImportError("lthread module not available")

        data = self.load()

        # Build manifest for export metadata (PR #226 requirement)
        manifest = {
            "user_id": self.user_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "version": "1.0",
            "source_device": "default_device" # Placeholder
        }

        # Package the soul data with the manifest metadata
        payload = {
            "manifest": manifest,
            "soul": data
        }

        encrypted_package = lthread.encrypt_and_sign(
            data=payload,
            target_device=target_device_id,
            protocol_version="1.0"
        )

        # Support optional base_dir redirection if testing
        base_dir = str(self.base_dir.parent) if self.base_dir else None
        return lthread.send_package(encrypted_package, target_device_id, base_dir=base_dir)

    def import_soul_secure(self, package_path: str, amygdala: Any = None) -> bool:
        """Импорт с верификацией через L-THREAD."""
        if not lthread:
            raise ImportError("lthread module not available")

        verified, payload = lthread.verify_and_decrypt(package_path, current_device_id=self.user_id)
        if not verified:
            raise ValueError("Soul integrity verification failed")

        # Extract soul data and manifest from the payload
        # Handle both flat and nested payloads for robustness
        if isinstance(payload, dict) and "soul" in payload:
            data = payload["soul"]
            # manifest = payload.get("manifest", {})
        else:
            data = payload

        self.save(data)
        if amygdala:
            amygdala.restore_state(data)
        return True
