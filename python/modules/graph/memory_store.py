# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .models import MemoryCase, RelationalFieldSnapshot, ResonanceKnowledgeUnit

_STORE_LOCKS: dict[str, threading.RLock] = {}
_STORE_LOCKS_GUARD = threading.Lock()


def _get_store_lock(path: Path) -> threading.RLock:
    """Return a process-wide reentrant lock for a concrete store path."""
    key = str(path.resolve())
    with _STORE_LOCKS_GUARD:
        lock = _STORE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _STORE_LOCKS[key] = lock
        return lock


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
        self._lock = _get_store_lock(self.path)

    def list_cases(self) -> list[MemoryCase]:
        with self._lock:
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
        with self._lock:
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

    def _atomic_write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass

    def _write_cases(self, cases: list[MemoryCase]) -> None:
        self._atomic_write_jsonl(
            self.path,
            [case.to_dict() for case in cases],
        )

    # ──────────────────────────────────────────────────────────────
    # ResonanceKnowledgeUnit — хранилище проверенных маршрутов мышления
    # ──────────────────────────────────────────────────────────────

    def _resonance_path(self) -> Path:
        """Отдельный JSONL-файл для когнитивных маршрутов."""
        return self.path.with_name("resonance_units.jsonl")

    def store_resonance_unit(
        self,
        unit: ResonanceKnowledgeUnit,
    ) -> ResonanceKnowledgeUnit:
        """Сохраняет или обновляет единицу проверенного когнитивного маршрута."""
        with self._lock:
            units = self._load_resonance_units()

            if not unit.unit_id:
                unit.unit_id = str(uuid4())
            if not unit.timestamp:
                unit.timestamp = _utc_now()

            updated = False
            for i, existing in enumerate(units):
                if existing.unit_id == unit.unit_id:
                    units[i] = unit
                    updated = True
                    break

            if not updated:
                units.append(unit)

            self._write_resonance_units(units)
            return unit

    def list_resonance_units(self) -> list[ResonanceKnowledgeUnit]:
        return self._load_resonance_units()

    def find_relevant_units(
        self,
        *,
        intent: str | None = None,
        why: str | None = None,
        goal_vector: list[float] | None = None,
        query_text: str | None = None,
        top_k: int = 5,
    ) -> list[ResonanceKnowledgeUnit]:
        """Heuristic retrieval для проверенных когнитивных маршрутов.

        MVP-версия пока не использует embeddings / graph traversal —
        только простое совпадение.
        """
        units = self._load_resonance_units()
        scored: list[tuple[ResonanceKnowledgeUnit, float]] = []

        top_k = max(1, int(top_k or 1))
        _ = goal_vector  # TODO: add cosine similarity in follow-up
        query_text_lower = query_text.lower() if query_text else None

        for u in units:
            score = 0.0

            if intent and u.intent and intent.lower() in u.intent.lower():
                score += 0.4
            if why and u.why and why.lower() in u.why.lower():
                score += 0.4

            query_match = (
                query_text_lower
                and u.source_question
                and query_text_lower in u.source_question.lower()
            )
            if query_match:
                score += 0.3

            # TODO: add goal_vector cosine similarity.
            # TODO: add evolve-oriented route scoring.
            if score > 0.0:
                scored.append((u, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [u for u, _ in scored[:top_k]]

    def _load_resonance_units(self) -> list[ResonanceKnowledgeUnit]:
        with self._lock:
            path = self._resonance_path()
            if not path.exists():
                return []

            units: list[ResonanceKnowledgeUnit] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        units.append(ResonanceKnowledgeUnit.from_dict(json.loads(line)))
            return units

    def _write_resonance_units(self, units: list[ResonanceKnowledgeUnit]) -> None:
        """MVP-only storage.

        Atomic file replace is used; graph-store backend can come later.
        """
        path = self._resonance_path()
        self._atomic_write_jsonl(
            path,
            [unit.to_dict() for unit in units],
        )

    # ──────────────────────────────────────────────────────────────
    # RelationalFieldSnapshot — observational interaction field layer
    # ──────────────────────────────────────────────────────────────

    def _relational_snapshots_path(self) -> Path:
        return self.path.with_name("relational_field_snapshots.jsonl")

    def store_relational_snapshot(
        self,
        snapshot: RelationalFieldSnapshot,
    ) -> RelationalFieldSnapshot:
        with self._lock:
            snapshots = self._load_relational_snapshots()
            if not snapshot.field_id:
                snapshot.field_id = str(uuid4())
            if not snapshot.timestamp:
                snapshot.timestamp = _utc_now()
            snapshots.append(snapshot)
            self._write_relational_snapshots(snapshots)
            return snapshot

    def list_relational_snapshots(self) -> list[RelationalFieldSnapshot]:
        return self._load_relational_snapshots()

    def _load_relational_snapshots(self) -> list[RelationalFieldSnapshot]:
        with self._lock:
            path = self._relational_snapshots_path()
            if not path.exists():
                return []

            snapshots: list[RelationalFieldSnapshot] = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        snapshots.append(
                            RelationalFieldSnapshot.from_dict(json.loads(line))
                        )
            return snapshots

    def _write_relational_snapshots(
        self,
        snapshots: list[RelationalFieldSnapshot],
    ) -> None:
        self._atomic_write_jsonl(
            self._relational_snapshots_path(),
            [snapshot.to_dict() for snapshot in snapshots],
        )
