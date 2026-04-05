from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from ls.agent_shell.schemas.artifact import Artifact
from ls.agent_shell.storage.sqlite_store import SQLiteStore, to_json


class ArtifactManager:
    def __init__(self, store: SQLiteStore, artifacts_root: Path):
        self.store = store
        self.artifacts_root = artifacts_root
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def create_text_artifact(self, task_id: str, title: str, rel_name: str, content: str) -> Artifact:
        task_dir = self.artifacts_root / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        path = task_dir / rel_name
        path.write_text(content, encoding="utf-8")
        artifact = Artifact(
            id=f"artifact-{uuid4().hex[:8]}",
            task_id=task_id,
            type="report",
            title=title,
            path_or_url=str(path),
            metadata={"bytes": len(content.encode('utf-8'))},
        )
        payload = asdict(artifact)
        payload["metadata_json"] = to_json(payload.pop("metadata"))
        self.store.insert("artifacts", payload)
        return artifact
