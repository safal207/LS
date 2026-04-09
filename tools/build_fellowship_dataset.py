from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "artifacts" / "council-ledger"
QUALITY_DIR = ROOT / "artifacts" / "council-quality"
OUTPUT_DIR = ROOT / "artifacts" / "fellowship-dataset"
OUTPUT_LEDGER_DIR = OUTPUT_DIR / "ledgers"
OUTPUT_QUALITY_DIR = OUTPUT_DIR / "council-quality"
OUTPUT_TRACE_DIR = OUTPUT_DIR / "traces"


@dataclass
class LedgerRow:
    path: Path
    cycle_id: str
    model_id: str
    success: bool
    resonance: float
    contribution: float
    goal_summary: str
    route: str
    source_type: str

    @property
    def score(self) -> float:
        return (0.45 * float(self.success)) + (0.25 * self.resonance) + (0.30 * self.contribution)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_row(path: Path, payload: dict) -> LedgerRow | None:
    participants = payload.get("participants") or []
    first = participants[0] if participants else {}
    model_id = str(first.get("model_id") or "")
    if not model_id or model_id == "dry_run:unknown":
        return None
    if path.name.startswith("demo-") or path.name.startswith("cid"):
        return None

    outcome = payload.get("outcome") or {}
    attribution = payload.get("attribution") or {}
    return LedgerRow(
        path=path,
        cycle_id=str(payload.get("cycle_id") or path.stem),
        model_id=model_id,
        success=bool(outcome.get("success")),
        resonance=float(outcome.get("receiver_resonance_score", outcome.get("operator_feedback_score", 0.0)) or 0.0),
        contribution=float(attribution.get("best_contributor_score", 0.0) or 0.0),
        goal_summary=str((payload.get("goal") or {}).get("summary") or ""),
        route=str((payload.get("final_decision") or {}).get("selected_route") or "unknown"),
        source_type="real_local_cycle",
    )


def load_rows() -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    for path in sorted(LEDGER_DIR.glob("*.json")):
        try:
            payload = read_json(path)
        except Exception:
            continue
        row = classify_row(path, payload)
        if row is not None:
            rows.append(row)
    return rows


def select_rows(rows: list[LedgerRow], limit: int = 8) -> list[LedgerRow]:
    ordered = sorted(rows, key=lambda row: (row.score, row.resonance, row.contribution), reverse=True)
    selected: list[LedgerRow] = []
    seen_goals: set[str] = set()
    for row in ordered:
        goal_key = row.goal_summary.strip().lower()
        if goal_key in seen_goals and len(selected) >= max(4, limit // 2):
            continue
        selected.append(row)
        seen_goals.add(goal_key)
        if len(selected) >= limit:
            break

    if selected and not any(not row.success for row in selected):
        failure = next((row for row in reversed(ordered) if not row.success), None)
        if failure is not None and failure not in selected:
            if len(selected) >= limit:
                selected[-1] = failure
            else:
                selected.append(failure)
    return selected


def build_manifest(selected: list[LedgerRow]) -> dict:
    quality_by_cycle: dict[str, dict] = {}
    for path in QUALITY_DIR.glob("*.json"):
        try:
            payload = read_json(path)
        except Exception:
            continue
        cycle_id = str(payload.get("cycle_id") or "")
        if cycle_id:
            quality_by_cycle[cycle_id] = payload

    success_count = sum(1 for row in selected if row.success)
    risky_cycle_count = sum(
        1
        for row in selected
        if str(((quality_by_cycle.get(row.cycle_id) or {}).get("operator_guidance") or {}).get("risk_state") or "watch")
        in {"repair", "escalate"}
    )
    incident_count = sum(
        1
        for row in selected
        if bool((((quality_by_cycle.get(row.cycle_id) or {}).get("liminalqa") or {}).get("incident") or {}).get("published"))
    )
    quality_scores = [
        float((quality_by_cycle.get(row.cycle_id) or {}).get("quality_score") or 0.0)
        for row in selected
        if (quality_by_cycle.get(row.cycle_id) or {}).get("quality_score") is not None
    ]
    liminalqa_published_count = sum(
        1 for row in selected if bool(((quality_by_cycle.get(row.cycle_id) or {}).get("liminalqa") or {}).get("published"))
    )
    return {
        "dataset_name": "ls-fellowship-council-ledger-sample",
        "source": "artifacts/council-ledger",
        "selection_policy": {
            "excluded": ["demo cycles", "cid contract fixtures", "dry_run:unknown ledgers"],
            "limit": len(selected),
            "goal": "curated evidence-grade sample for fellowship review",
        },
        "summary": {
            "ledger_count": len(selected),
            "success_count": success_count,
            "failure_count": len(selected) - success_count,
            "avg_resonance": round(sum(row.resonance for row in selected) / len(selected), 4) if selected else 0.0,
            "avg_contribution": round(sum(row.contribution for row in selected) / len(selected), 4) if selected else 0.0,
            "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 4) if quality_scores else 0.0,
            "liminalqa_published_count": liminalqa_published_count,
            "risky_cycle_count": risky_cycle_count,
            "incident_count": incident_count,
        },
        "items": [
            {
                "cycle_id": row.cycle_id,
                "file": f"ledgers/{row.path.name}",
                "quality_file": (
                    f"council-quality/{row.cycle_id}.json"
                    if row.cycle_id in quality_by_cycle
                    else None
                ),
                "model_id": row.model_id,
                "route": row.route,
                "success": row.success,
                "receiver_resonance": row.resonance,
                "best_contributor_score": row.contribution,
                "quality_score": (quality_by_cycle.get(row.cycle_id) or {}).get("quality_score"),
                "risk_state": ((quality_by_cycle.get(row.cycle_id) or {}).get("operator_guidance") or {}).get("risk_state"),
                "incident_published": bool(
                    ((((quality_by_cycle.get(row.cycle_id) or {}).get("liminalqa") or {}).get("incident") or {}).get("published"))
                ),
                "liminalqa_published": bool(((quality_by_cycle.get(row.cycle_id) or {}).get("liminalqa") or {}).get("published")),
                "goal_summary": row.goal_summary,
                "source_type": row.source_type,
            }
            for row in selected
        ],
        "traces": {
            "included": [],
            "note": "Replay traces are not packaged in this first sample. The ledger sample is the current minimum evidence artifact.",
        },
        "limitations": [
            "Most cycles currently use callable-backed local LLM outputs but still expose route='unknown'.",
            "This sample is a curated subset, not a full production dataset.",
            "Receiver resonance is currently derived from runtime signals rather than human annotation.",
        ],
    }


def write_readme(manifest: dict) -> None:
    text = f"""# Fellowship Dataset

This folder contains a curated sample of council-ledger artifacts selected from `artifacts/council-ledger`.

Summary:

- ledger_count: {manifest["summary"]["ledger_count"]}
- success_count: {manifest["summary"]["success_count"]}
- failure_count: {manifest["summary"]["failure_count"]}
- avg_resonance: {manifest["summary"]["avg_resonance"]}
- avg_contribution: {manifest["summary"]["avg_contribution"]}
- avg_quality_score: {manifest["summary"]["avg_quality_score"]}
- liminalqa_published_count: {manifest["summary"]["liminalqa_published_count"]}
- risky_cycle_count: {manifest["summary"]["risky_cycle_count"]}
- incident_count: {manifest["summary"]["incident_count"]}

Selection policy:

- exclude demo cycles
- exclude contract fixtures
- exclude `dry_run:unknown` ledgers
- keep a small mixed sample for fellowship review

Contents:

- `manifest.json`: dataset manifest and limitations
- `ledgers/`: selected council-ledger JSON artifacts
- `council-quality/`: paired council-quality artifacts when available
- `traces/`: reserved for replay traces in a follow-up package
"""
    (OUTPUT_DIR / "README.md").write_text(text, encoding="utf-8")


def build_dataset() -> dict:
    rows = load_rows()
    selected = select_rows(rows)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TRACE_DIR.mkdir(parents=True, exist_ok=True)

    for row in selected:
        shutil.copy2(row.path, OUTPUT_LEDGER_DIR / row.path.name)
        quality_path = QUALITY_DIR / f"{row.cycle_id}.json"
        if quality_path.exists():
            shutil.copy2(quality_path, OUTPUT_QUALITY_DIR / quality_path.name)

    manifest = build_manifest(selected)
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(manifest)
    return manifest


if __name__ == "__main__":
    result = build_dataset()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
