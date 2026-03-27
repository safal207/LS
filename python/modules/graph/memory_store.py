from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .models import MemoryCase


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryGraphStore:
    """Simple JSONL-backed storage for cooperative network memory.

    This is intentionally minimal for MVP-1. It keeps the persistence layer
    cheap and inspectable before introducing a heavier graph store.
    """

    def __init__(self, path: str | Path = "data/graph_memory/cases.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_cases(self) -> list[MemoryCase]:
        if not self.path.exists():
            return []
        cases: list[MemoryCase] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                cases.append(MemoryCase.from_dict(json.loads(line)))
        return cases

    def get_case(self, case_id: str) -> Optional[MemoryCase]:
        for case in self.list_cases():
            if case.case_id == case_id:
                return case
        return None

    def save_case(self, case: MemoryCase) -> MemoryCase:
        cases = self.list_cases()
        if not case.case_id:
            case.case_id = str(uuid4())
        if not case.created_at:
            case.created_at = _utc_now()
        updated = False
        for index, existing in enumerate(cases):
            if existing.case_id == case.case_id:
                cases[index] = case
                updated = True
                break
        if not updated:
            cases.append(case)
        self._write_cases(cases)
        return case

    def remember(
        self,
        *,
        question_text: str,
        clean_text: str,
        answer_text: str,
        intent: str | None = None,
        why: str | None = None,
        thread_context: str | None = None,
        answer_quality: dict | None = None,
        contributors: list[dict] | None = None,
    ) -> MemoryCase:
        case = MemoryCase(
            case_id=str(uuid4()),
            question_text=question_text,
            clean_text=clean_text,
            intent=intent,
            why=why,
            thread_context=thread_context,
            answer_text=answer_text,
            answer_quality=dict(answer_quality or {}),
            contributors=list(contributors or []),
            created_at=_utc_now(),
        )
        return self.save_case(case)

    def mark_reused(self, case_id: str) -> Optional[MemoryCase]:
        case = self.get_case(case_id)
        if case is None:
            return None
        case.reuse_count += 1
        case.last_reused_at = _utc_now()
        return self.save_case(case)

    def _write_cases(self, cases: list[MemoryCase]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")
