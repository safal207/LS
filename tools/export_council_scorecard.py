from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = ROOT / "artifacts" / "council-ledger"
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


def classify_row(row: dict) -> str:
    cycle_id = str(row.get("cycle_id") or "")
    best = str((row.get("attribution") or {}).get("best_contributor_model_id") or "n/a")
    route = str((row.get("final_decision") or {}).get("selected_route") or "unknown")
    if cycle_id.startswith("demo-cycle-"):
        return "demo"
    if best in {"dry_run:unknown", "unknown", "n/a"} or route == "unknown":
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


def build_scorecard(rows: list[dict]) -> dict:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    selected_rows, source = select_rows(rows)
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
            },
            "bars": {
                "best_contributor_frequency": [],
                "model_type_lift": [],
                "route_wins": [],
            },
            "lines": {
                "resonance_trend": [],
                "merit_trend": [],
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
    for index, row in enumerate(selected_rows, start=1):
        outcome = row.get("outcome", {})
        attribution = row.get("attribution", {})
        participants = row.get("participants", [])
        participant_types = {str(item.get("model_id")): str(item.get("model_type") or "unknown") for item in participants}
        best = str(attribution.get("best_contributor_model_id") or "n/a")
        best_counts[best] += 1
        route = str((row.get("final_decision") or {}).get("selected_route") or "unknown")
        route_wins[route] += 1
        for entry in attribution.get("contribution_breakdown", []):
            model_id = str(entry.get("model_id") or "unknown")
            score = float(entry.get("total_contribution_score") or 0.0)
            contribution_totals[model_id] += score
            type_totals[participant_types.get(model_id, "unknown")].append(score)
        success = 1.0 if outcome.get("success") else 0.0
        resonance = float(outcome.get("receiver_resonance_score", outcome.get("operator_feedback_score", 0.0)) or 0.0)
        network = float(outcome.get("network_improvement", 0.0) or 0.0)
        merit = clamp((float(attribution.get("best_contributor_score", 0.0) or 0.0) + resonance + max(network, 0.0)) / 3.0)
        label = f"c{index}"
        resonance_series.append({"label": label, "value": round(resonance * 100.0, 2)})
        merit_series.append({"label": label, "value": round(merit * 100.0, 2)})
        successes.append(success)
        resonances.append(resonance)
        merits.append(merit)
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
        },
        "bars": {
            "best_contributor_frequency": [{"label": key, "value": value} for key, value in best_counts.items()],
            "model_type_lift": [{"label": key, "value": value} for key, value in type_lift.items()],
            "route_wins": [{"label": key, "value": value} for key, value in route_wins.items()],
        },
        "lines": {
            "resonance_trend": resonance_series,
            "merit_trend": merit_series,
        },
        "takeaways": takeaways,
    }


def write_scorecard(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_scorecard(input_dir: Path, output_path: Path, *, keep_existing_on_empty: bool = False) -> dict:
    rows = load_ledgers(input_dir)
    if keep_existing_on_empty and not rows and output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    payload = build_scorecard(rows)
    write_scorecard(payload, output_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Export council-ledger artifacts into a landing scorecard JSON snapshot.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--keep-existing-on-empty", action="store_true")
    args = parser.parse_args()

    payload = export_scorecard(args.input_dir, args.output, keep_existing_on_empty=args.keep_existing_on_empty)
    print(json.dumps({
        "output": str(args.output),
        "source": payload.get("source"),
        "ledgers": payload.get("summary", {}).get("ledgers", 0),
    }, indent=2))


if __name__ == "__main__":
    main()
