from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import DerivedModule


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
    return normalized.strip("-") or "generic"


class DerivedModuleRegistry:
    def __init__(self, path: str | Path = "data/graph_memory/derived_modules.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_modules(self) -> list[DerivedModule]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [DerivedModule.from_dict(item) for item in raw if isinstance(item, dict)]

    def get_module(self, module_id: str) -> Optional[DerivedModule]:
        for module in self.list_modules():
            if module.module_id == module_id:
                return module
        return None

    def save_module(self, module: DerivedModule) -> DerivedModule:
        modules = self.list_modules()
        updated = False
        for idx, current in enumerate(modules):
            if current.module_id == module.module_id:
                modules[idx] = module
                updated = True
                break
        if not updated:
            modules.append(module)
        self.path.write_text(
            json.dumps([item.to_dict() for item in modules], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return module

    def find_best(
        self,
        *,
        available_backends: list[str],
        domain: str | None = None,
        task_type: str | None = None,
        min_quality: float = 0.65,
        min_trust: float = 0.55,
    ) -> Optional[DerivedModule]:
        backend_set = set(available_backends)
        candidates: list[DerivedModule] = []
        for module in self.list_modules():
            if module.preferred_backend not in backend_set:
                continue
            if module.quality_score < min_quality or module.trust_score < min_trust:
                continue
            if domain and module.domain not in {"", "generic", domain}:
                continue
            if task_type and module.task_type not in {"", "generic", task_type}:
                continue
            candidates.append(module)
        if not candidates:
            return None
        candidates.sort(
            key=lambda item: (item.trust_score, item.quality_score, item.usage_count, item.successes),
            reverse=True,
        )
        return candidates[0]

    def create_or_update_from_success(
        self,
        *,
        parent_coalition_id: str,
        source_route_key: str,
        domain: str,
        task_type: str,
        preferred_backend: str,
        policy_type: str,
        policy_text: str,
        quality_score: float,
    ) -> DerivedModule:
        module_id = f"derived-{_slug(domain)}-{_slug(task_type)}-{_slug(preferred_backend)}"
        module = self.get_module(module_id)
        if module is None:
            module = DerivedModule(
                module_id=module_id,
                parent_coalition_id=parent_coalition_id,
                domain=domain or "generic",
                task_type=task_type or "generic",
                policy_type=policy_type,
                policy_text=policy_text,
                preferred_backend=preferred_backend,
                source_route_key=source_route_key,
                trust_score=max(0.55, round(quality_score, 4)),
                quality_score=round(quality_score, 4),
                usage_count=0,
                runs=0,
                successes=0,
                last_used_at=_utc_now(),
            )
            return self.save_module(module)

        runs = module.runs
        module.parent_coalition_id = parent_coalition_id or module.parent_coalition_id
        module.source_route_key = source_route_key or module.source_route_key
        module.policy_type = policy_type or module.policy_type
        module.policy_text = policy_text or module.policy_text
        module.preferred_backend = preferred_backend or module.preferred_backend
        module.quality_score = round(((module.quality_score * runs) + quality_score) / (runs + 1), 4)
        module.trust_score = round((module.trust_score * 0.9) + (0.1 * quality_score), 4)
        module.last_used_at = _utc_now()
        return self.save_module(module)

    def mark_used(self, module_id: str, *, quality_score: float, success: bool) -> Optional[DerivedModule]:
        module = self.get_module(module_id)
        if module is None:
            return None
        runs = module.runs
        module.usage_count += 1
        module.runs = runs + 1
        module.successes += 1 if success else 0
        module.quality_score = round(((module.quality_score * runs) + quality_score) / (runs + 1), 4)
        module.trust_score = round((module.trust_score * 0.9) + (0.1 * quality_score), 4)
        module.last_used_at = _utc_now()
        return self.save_module(module)
