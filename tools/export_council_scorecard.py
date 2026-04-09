from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "artifacts" / "council-ledger"
DEFAULT_DATASET_INPUT_DIR = ROOT / "artifacts" / "fellowship-dataset" / "ledgers"
DEFAULT_DATASET_QUALITY_DIR = ROOT / "artifacts" / "fellowship-dataset" / "council-quality"
DEFAULT_QUALITY_INPUT_DIR = ROOT / "artifacts" / "council-quality"
DEFAULT_OUTPUT_PATH = ROOT / "ghostgpt-ls-landing" / "src" / "data" / "councilScorecard.json"


def parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def normalize_model_label(value: object) -> str:
    label = str(value or "n/a")
    if label in {"callable:unknown", "dry_run:unknown", "unknown", "n/a"}:
        return "local-council-llm"
    return label


def normalize_route_label(value: object) -> str:
    label = str(value or "unknown")
    if label == "unknown":
        return "route-pending"
    return label


def load_ledgers(input_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if not input_dir.exists():
        return rows
    for path in sorted(input_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_path"] = str(path)
        rows.append(payload)
    rows.sort(key=lambda item: parse_iso(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def load_quality_artifacts(input_dir: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not input_dir.exists():
        return rows
    for path in sorted(input_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cycle_id = str(payload.get("cycle_id") or "")
        if cycle_id:
            rows[cycle_id] = payload
    return rows


def classify_row(row: dict) -> str:
    cycle_id = str(row.get("cycle_id") or "")
    best = normalize_model_label((row.get("attribution") or {}).get("best_contributor_model_id"))
    route = normalize_route_label((row.get("final_decision") or {}).get("selected_route"))
    if cycle_id.startswith("demo-cycle-"):
        return "demo"
    if route == "route-pending":
        return "low_signal"
    return "artifact"


def select_rows(rows: list[dict]) -> tuple[list[dict], str]:
    if not rows:
        return [], "empty"
    artifact_rows = [row for row in rows if classify_row(row) == "artifact"]
    if artifact_rows:
        return artifact_rows, "artifact"
    demo_rows = [row for row in rows if classify_row(row) == "demo"]
    if demo_rows:
        return demo_rows, "demo"
    return rows, "mixed"


def build_scorecard(rows: list[dict], *, quality_by_cycle: dict[str, dict] | None = None) -> dict:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    selected_rows, source = select_rows(rows)
    quality_by_cycle = quality_by_cycle or {}
    if not selected_rows:
        return {
            "generated_at": generated_at,
            "source": "empty",
            "summary": {
                "ledgers": 0,
                "top_contributor": "n/a",
                "success_rate": 0.0,
                "avg_resonance": 0.0,
                "avg_merit": 0.0,
                "avg_quality": 0.0,
                "avg_relation_safety": 0.0,
                "risky_cycle_count": 0,
                "incident_count": 0,
                "reviewed_cycle_count": 0,
                "approval_conversion_rate": 0.0,
                "escalation_rate": 0.0,
            },
            "bars": {
                "best_contributor_frequency": [],
                "model_type_lift": [],
                "route_wins": [],
            },
            "lines": {
                "resonance_trend": [],
                "merit_trend": [],
                "incident_trend": [],
                "review_trend": [],
            },
            "takeaways": {
                "with_ls": [
                    "No council-ledger artifacts were available at build time.",
                    "Run a real council cycle locally or in CI to refresh this public scorecard.",
                    "The page preserves the rendering contract even when the source snapshot is empty.",
                ],
                "disclaimer": "This scorecard currently has no live council-ledger source data behind it."
            },
        }

    best_counts: Counter[str] = Counter()
    contribution_totals: defaultdict[str, float] = defaultdict(float)
    type_totals: defaultdict[str, list[float]] = defaultdict(list)
    route_wins: Counter[str] = Counter()
    resonance_series: list[dict] = []
    merit_series: list[dict] = []
    successes: list[float] = []
    resonances: list[float] = []
    merits: list[float] = []
    qualities: list[float] = []
    relation_safeties: list[float] = []
    incident_count = 0
    risky_cycle_count = 0
    reviewed_cycle_count = 0
    incident_series: list[dict] = []
    review_series: list[dict] = []
    approved_count = 0
    escalate_count = 0
    for index, row in enumerate(selected_rows, start=1):
        outcome = row.get("outcome", {})
        attribution = row.get("attribution", {})
        participants = row.get("participants", [])
        cycle_id = str(row.get("cycle_id") or "")
        quality_payload = quality_by_cycle.get(cycle_id) or {}
        quality_outcome = quality_payload.get("council_outcome") or {}
        guidance = quality_payload.get("operator_guidance") or {}
        operator_review = quality_payload.get("operator_review") or {}
        liminalqa = quality_payload.get("liminalqa") or {}
        participant_types = {
            normalize_model_label(item.get("model_id")): str(item.get("model_type") or "unknown")
            for item in participants
        }
        best = normalize_model_label(attribution.get("best_contributor_model_id"))
        best_counts[best] += 1
        route = normalize_route_label((row.get("final_decision") or {}).get("selected_route"))
        route_wins[route] += 1
        for entry in attribution.get("contribution_breakdown", []):
            model_id = normalize_model_label(entry.get("model_id"))
            score = float(entry.get("total_contribution_score") or 0.0)
            contribution_totals[model_id] += score
            type_totals[participant_types.get(model_id, "unknown")].append(score)
        success = 1.0 if outcome.get("success") else 0.0
        resonance = float(outcome.get("receiver_resonance_score", outcome.get("operator_feedback_score", 0.0)) or 0.0)
        quality_score = (
            float(quality_payload.get("relation_adjusted_quality_score"))
            if quality_payload.get("relation_adjusted_quality_score") is not None
            else float(quality_payload.get("quality_score"))
            if quality_payload.get("quality_score") is not None
            else clamp(
                (float(outcome.get("path_quality", 0.0) or 0.0) + resonance + success) / 3.0
            )
        )
        relation_safety = clamp(
            float((quality_payload.get("relational_field") or {}).get("relation_safety_score", 0.0) or 0.0)
        )
        network = float(quality_outcome.get("network_improvement", outcome.get("network_improvement", 0.0)) or 0.0)
        merit = clamp((float(attribution.get("best_contributor_score", 0.0) or 0.0) + resonance + max(network, 0.0)) / 3.0)
        label = f"c{index}"
        risk_state = str(guidance.get("risk_state") or "watch")
        if risk_state in {"repair", "escalate"}:
            risky_cycle_count += 1
        if risk_state == "escalate":
            escalate_count += 1
        review_decision = str(operator_review.get("decision") or "pending")
        if review_decision in {"approved", "rejected"}:
            reviewed_cycle_count += 1
        if review_decision == "approved":
            approved_count += 1
        if (liminalqa.get("incident") or {}).get("published"):
            incident_count += 1
        resonance_series.append({"label": label, "value": round(resonance * 100.0, 2)})
        merit_series.append({"label": label, "value": round(merit * 100.0, 2)})
        incident_series.append({"label": label, "value": incident_count})
        review_series.append({"label": label, "value": reviewed_cycle_count})
        successes.append(success)
        resonances.append(resonance)
        merits.append(merit)
        qualities.append(quality_score)
        relation_safeties.append(relation_safety)
    type_lift = {key: round(avg(values), 4) for key, values in type_totals.items()}
    top_contributor = best_counts.most_common(1)[0][0] if best_counts else "n/a"
    takeaways = {
        "with_ls": [
            f"{top_contributor} currently leads the council on repeated cycles, so model contribution is observable instead of anecdotal.",
            "Receiver resonance trends show whether answers are becoming easier to accept over time.",
            "Route win counts expose which graph paths actually close with quality, not just which ones sound plausible.",
        ],
        "disclaimer": "This scorecard is assembled from council-ledger artifacts found at build time. It is a snapshot of observed cycles, not a universal production guarantee."
    }

    return {
        "generated_at": generated_at,
        "source": source,
        "summary": {
            "ledgers": len(selected_rows),
            "top_contributor": top_contributor,
            "success_rate": round(avg(successes) * 100.0, 2),
            "avg_resonance": round(avg(resonances) * 100.0, 2),
            "avg_merit": round(avg(merits) * 100.0, 2),
            "avg_quality": round(avg(qualities) * 100.0, 2),
            "avg_relation_safety": round(avg(relation_safeties) * 100.0, 2),
            "risky_cycle_count": risky_cycle_count,
            "incident_count": incident_count,
            "reviewed_cycle_count": reviewed_cycle_count,
            "approval_conversion_rate": round((approved_count / len(selected_rows)) * 100.0, 2),
            "escalation_rate": round((escalate_count / len(selected_rows)) * 100.0, 2),
        },
        "bars": {
            "best_contributor_frequency": [{"label": key, "value": value} for key, value in best_counts.items()],
            "model_type_lift": [{"label": key, "value": value} for key, value in type_lift.items()],
            "route_wins": [{"label": key, "value": value} for key, value in route_wins.items()],
        },
        "lines": {
            "resonance_trend": resonance_series,
            "merit_trend": merit_series,
            "incident_trend": incident_series,
            "review_trend": review_series,
        },
        "takeaways": takeaways,
    }


def write_scorecard(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_scorecard(input_dir: Path, output_path: Path, *, keep_existing_on_empty: bool = False) -> dict:
    rows = load_ledgers(input_dir)
    quality_dir = input_dir.parent / "council-quality"
    quality_by_cycle = load_quality_artifacts(quality_dir)
    if keep_existing_on_empty and not rows and output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    payload = build_scorecard(rows, quality_by_cycle=quality_by_cycle)
    write_scorecard(payload, output_path)
    return payload


def export_scorecard_with_preferred_sources(
    *,
    preferred_input_dirs: list[Path],
    output_path: Path,
    keep_existing_on_empty: bool = False,
) -> dict:
    for input_dir in preferred_input_dirs:
        rows = load_ledgers(input_dir)
        if rows:
            quality_dir = input_dir.parent / "council-quality"
            payload = build_scorecard(rows, quality_by_cycle=load_quality_artifacts(quality_dir))
            payload["input_dir"] = str(input_dir)
            if "fellowship-dataset" in str(input_dir).replace("\\", "/"):
                payload["source"] = "fellowship_dataset"
            write_scorecard(payload, output_path)
            return payload

    if keep_existing_on_empty and output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))

    payload = build_scorecard([])
    payload["input_dir"] = ""
    write_scorecard(payload, output_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Export council-ledger artifacts into a landing scorecard JSON snapshot.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--dataset-input-dir", type=Path, default=DEFAULT_DATASET_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--keep-existing-on-empty", action="store_true")
    args = parser.parse_args()

    payload = export_scorecard_with_preferred_sources(
        preferred_input_dirs=[args.dataset_input_dir, args.input_dir],
        output_path=args.output,
        keep_existing_on_empty=args.keep_existing_on_empty,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source": payload.get("source"),
                "input_dir": payload.get("input_dir", ""),
                "ledgers": payload.get("summary", {}).get("ledgers", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
