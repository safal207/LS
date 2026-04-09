from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for candidate in (PYTHON_ROOT, MODULES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)
HTML_PATH = ROOT / "tools" / "liminalqa_local_dashboard.html"
ENV_PATH = ROOT / ".env.liminalqa.local"
ARTIFACTS_DIR = ROOT / "artifacts"
QUALITY_DIR = ARTIFACTS_DIR / "quality"
QUALITY_REPORT_PATH = ARTIFACTS_DIR / "quality-report.json"
COUNCIL_LEDGER_DIR = ARTIFACTS_DIR / "council-ledger"
COUNCIL_QUALITY_DIR = ARTIFACTS_DIR / "council-quality"
DOCS_BASE_URL = "https://github.com/safal207/LS/blob/main/docs"
COUNCIL_CYCLE_TIMEOUT_SECONDS = 45
FAVICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#161311"/><path d="M16 47V17h8v23h20v7H16zm17-8 9-22h8L40 39h-7z" fill="#fffaf1"/></svg>'
LANE = {
    "key": "mesh-tests",
    "title": "Mesh Tests Quality Gate",
    "threshold": "30%",
    "min_coverage": 30.0,
    "junit": ARTIFACTS_DIR / "mesh-junit.xml",
    "coverage": ARTIFACTS_DIR / "coverage.xml",
    "pythonpath": "python",
    "args": [
        "-m", "pytest", "-q",
        "tests/test_service_runtime.py",
        "python/tests/test_web4_mesh.py",
        "python/tests/test_web4_mesh_node.py",
        "python/tests/test_web4_mesh_transport_ws.py",
        "--junitxml=artifacts/mesh-junit.xml",
        "--cov=agent",
        "--cov=python/modules/web4_mesh",
        "--cov-report=xml:artifacts/coverage.xml",
    ],
}

try:
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.resonance_agent import ResonanceAgent

try:
    from ls.agent_shell.cli import (
        assign_council_reviewer,
        close_council_escalation,
        iter_council_escalation_rows,
        load_council_quality_artifact,
        update_council_operator_review,
    )
except ImportError:
    from python.ls.agent_shell.cli import (
        assign_council_reviewer,
        close_council_escalation,
        iter_council_escalation_rows,
        load_council_quality_artifact,
        update_council_operator_review,
    )


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, value = stripped.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def settings() -> tuple[str, str]:
    env = load_env()
    url = os.environ.get("LIMINALQA_URL") or env.get("LIMINALQA_URL") or "http://127.0.0.1:8080"
    token = os.environ.get("LIMINALQA_TOKEN") or env.get("LIMINALQA_TOKEN") or "devtoken"
    return url.rstrip("/"), token


def api_request(method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    url, token = settings()
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body or str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def ulid_like() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    chars = []
    for value, length in ((ms, 10), (rand, 16)):
        local = []
        for _ in range(length):
            local.append(alphabet[value & 0x1F])
            value >>= 5
        chars.append("".join(reversed(local)))
    return "".join(chars)


def smoke_payload() -> dict:
    started = iso_now()
    completed = (datetime.now(timezone.utc) + timedelta(milliseconds=120)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "run": {
            "run_id": ulid_like(),
            "build_id": ulid_like(),
            "plan_name": "ls-dashboard-smoke",
            "env": {"CI": "false", "SOURCE": "ls-dashboard"},
            "started_at": started,
            "runner_version": "ls-dashboard-v3",
        },
        "tests": [{
            "name": "dashboard_smoke_publish",
            "suite": "ls.local.dashboard",
            "guidance": "Local dashboard smoke publish",
            "status": "pass",
            "duration_ms": 120,
            "started_at": started,
            "completed_at": completed,
        }],
        "signals": [{
            "test_name": "dashboard_smoke_publish",
            "kind": "system",
            "value": 1.0,
            "meta": {"note": "dashboard smoke publish"},
            "at": started,
        }],
        "artifacts": [],
    }


def evaluate_quality() -> dict:
    junit_files = sorted(ARTIFACTS_DIR.glob("*junit.xml"))
    coverage_files = sorted(ARTIFACTS_DIR.glob("*coverage.xml"))
    failures = errors = tests = skipped = 0
    runtime_seconds = 0.0
    coverages: list[float] = []
    issues: list[str] = []
    for path in junit_files:
        root = ET.parse(path).getroot()
        tests += int(float(root.attrib.get("tests", 0) or 0))
        failures += int(float(root.attrib.get("failures", 0) or 0))
        errors += int(float(root.attrib.get("errors", 0) or 0))
        skipped += int(float(root.attrib.get("skipped", 0) or 0))
        runtime_seconds += float(root.attrib.get("time", 0) or 0)
    for path in coverage_files:
        root = ET.parse(path).getroot()
        coverages.append(float(root.attrib.get("line-rate", 0) or 0) * 100.0)
    failed_like = failures + errors
    min_coverage = min(coverages) if coverages else None
    if not junit_files:
        issues.append("JUnit artifacts are missing.")
    if not coverage_files:
        issues.append("Coverage artifacts are missing.")
    if failed_like > 0:
        issues.append(f"Failures+errors {failed_like} exceed threshold 0.")
    if min_coverage is None:
        issues.append("Coverage threshold configured but no coverage XML files were found.")
    elif min_coverage < LANE["min_coverage"]:
        issues.append(f"Minimum line coverage {min_coverage:.1f}% is below threshold {LANE['min_coverage']:.1f}%.")
    verdict = "BLOCK" if issues else "PASS"
    return {
        "verdict": verdict,
        "total_tests": tests,
        "total_failures": failed_like,
        "total_skipped": skipped,
        "runtime_seconds": runtime_seconds,
        "min_line_coverage_observed": min_coverage,
        "junit_files": [path.name for path in junit_files],
        "coverage_files": [path.name for path in coverage_files],
        "issues": issues,
    }


def write_json(path: pathlib.Path, payload: dict) -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_json(path: pathlib.Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_quality_reports(reports: list[dict]) -> dict:
    counts = Counter(report.get("verdict", "UNKNOWN") for report in reports)
    verdict = "PASS"
    if counts.get("BLOCK"):
        verdict = "BLOCK"
    elif counts.get("WARN"):
        verdict = "WARN"
    elif not reports:
        verdict = "WARN"
    coverages = [item["min_line_coverage_observed"] for item in reports if item.get("min_line_coverage_observed") is not None]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "local/LS",
        "event_name": "manual",
        "ref": "local",
        "workflow": "local-dashboard",
        "workflow_job": "local-dashboard",
        "run_url": f"{settings()[0]}/health",
        "aggregate_verdict": verdict,
        "lane_count": len(reports),
        "verdict_counts": dict(counts),
        "total_failures": sum(int(item.get("total_failures", 0)) for item in reports),
        "min_line_coverage_observed": min(coverages) if coverages else None,
        "lanes": reports,
    }


def run_local_lane() -> tuple[int, object]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for artifact in (LANE["junit"], LANE["coverage"]):
        if artifact.exists():
            artifact.unlink()
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = LANE["pythonpath"] if not existing_pythonpath else f"{LANE['pythonpath']}{os.pathsep}{existing_pythonpath}"
    command = [sys.executable, *LANE["args"]]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    gate = evaluate_quality()
    lane_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "local/LS",
        "event_name": "manual",
        "ref": "local",
        "job": "local-dashboard",
        "lane_key": LANE["key"],
        "lane_title": LANE["title"],
        "verdict": gate["verdict"],
        "total_failures": gate["total_failures"],
        "min_line_coverage_observed": gate["min_line_coverage_observed"],
        "threshold": LANE["threshold"],
        "flaky_suspect": False,
        "run_url": f"{settings()[0]}/health",
    }
    lane_snapshot_path = write_json(QUALITY_DIR / f"{LANE['key']}.json", lane_report)
    reports = [load_json(path) for path in sorted(QUALITY_DIR.glob("*.json"))]
    aggregate = aggregate_quality_reports([item for item in reports if item])
    write_json(QUALITY_REPORT_PATH, aggregate)
    status = 200 if completed.returncode == 0 and gate["verdict"] != "BLOCK" else 422
    return status, {
        "lane_key": LANE["key"],
        "lane_title": LANE["title"],
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "verdict": gate["verdict"],
        "total_failures": gate["total_failures"],
        "min_line_coverage_observed": gate["min_line_coverage_observed"],
        "issues": gate["issues"],
        "junit_files": gate["junit_files"],
        "coverage_files": gate["coverage_files"],
        "lane_snapshot_path": str(lane_snapshot_path),
        "quality_report_path": str(QUALITY_REPORT_PATH),
        "stdout_tail": "\n".join(completed.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(completed.stderr.splitlines()[-40:]),
    }


def generate_quality_report() -> tuple[int, object]:
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)
    reports = [load_json(path) for path in sorted(QUALITY_DIR.glob("*.json"))]
    reports = [item for item in reports if item]
    if not reports:
        bootstrap = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repository": "local/LS",
            "event_name": "manual",
            "ref": "local",
            "job": "local-dashboard",
            "lane_key": "local-dashboard",
            "lane_title": "Local Dashboard",
            "verdict": "PASS",
            "total_failures": 0,
            "min_line_coverage_observed": None,
            "threshold": "manual bootstrap",
            "flaky_suspect": False,
            "run_url": f"{settings()[0]}/health",
        }
        write_json(QUALITY_DIR / "local-dashboard.json", bootstrap)
        reports.append(bootstrap)
    aggregate = aggregate_quality_reports(reports)
    write_json(QUALITY_REPORT_PATH, aggregate)
    return 200, {
        "report_path": str(QUALITY_REPORT_PATH),
        "aggregate_verdict": aggregate["aggregate_verdict"],
        "lane_count": aggregate["lane_count"],
        "total_failures": aggregate["total_failures"],
        "verdict_counts": aggregate["verdict_counts"],
    }


def preview_quality_report() -> tuple[int, object]:
    report = load_json(QUALITY_REPORT_PATH)
    if not report:
        return 404, {
            "error": "quality-report.json not found",
            "expected_path": str(QUALITY_REPORT_PATH),
            "hint": "Generate Quality Report first. The path is relative to the project root.",
        }
    lanes = [{
        "lane_key": lane.get("lane_key"),
        "lane_title": lane.get("lane_title"),
        "verdict": lane.get("verdict"),
        "total_failures": lane.get("total_failures"),
        "min_line_coverage_observed": lane.get("min_line_coverage_observed"),
        "flaky_suspect": lane.get("flaky_suspect"),
    } for lane in report.get("lanes", [])]
    return 200, {
        "report_path": str(QUALITY_REPORT_PATH),
        "generated_at": report.get("generated_at"),
        "aggregate_verdict": report.get("aggregate_verdict"),
        "lane_count": report.get("lane_count"),
        "total_failures": report.get("total_failures"),
        "min_line_coverage_observed": report.get("min_line_coverage_observed"),
        "verdict_counts": report.get("verdict_counts", {}),
        "lanes": lanes,
    }


def publish_quality_report() -> tuple[int, object]:
    report = load_json(QUALITY_REPORT_PATH)
    if not report:
        return 404, {"error": "quality-report.json not found", "expected_path": str(QUALITY_REPORT_PATH)}
    tests = []
    signals = []
    generated_at = report.get("generated_at") or iso_now()
    for lane in report.get("lanes", []):
        verdict = str(lane.get("verdict", "WARN")).upper()
        tests.append({
            "name": str(lane.get("lane_key", "unknown")),
            "suite": "github-actions.quality-gate",
            "guidance": lane.get("threshold"),
            "status": "pass" if verdict == "PASS" else "fail" if verdict == "BLOCK" else "skip",
            "duration_ms": None,
            "started_at": generated_at,
            "completed_at": generated_at,
        })
        signals.append({
            "test_name": str(lane.get("lane_key", "unknown")),
            "kind": "system",
            "value": float(lane.get("total_failures", 0)),
            "meta": {
                "lane_title": lane.get("lane_title"),
                "aggregate_verdict": report.get("aggregate_verdict"),
                "lane_verdict": verdict,
                "min_line_coverage_observed": lane.get("min_line_coverage_observed"),
                "source": "ls-dashboard",
            },
            "at": generated_at,
        })
    payload = {
        "run": {
            "run_id": ulid_like(),
            "build_id": ulid_like(),
            "plan_name": "ls-local-quality-report",
            "env": {"CI": "false", "SOURCE": "ls-dashboard", "QUALITY_AGGREGATE_VERDICT": str(report.get("aggregate_verdict", ""))},
            "started_at": generated_at,
            "runner_version": "ls-dashboard-quality-report-v3",
        },
        "tests": tests,
        "signals": signals,
        "artifacts": [],
    }
    status, ingest = api_request("POST", "/ingest/batch", payload)
    return status, {
        "report_path": str(QUALITY_REPORT_PATH),
        "aggregate_verdict": report.get("aggregate_verdict"),
        "lane_count": len(report.get("lanes", [])),
        "ingest": ingest,
    }


def parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def council_ledgers() -> list[dict]:
    rows: list[dict] = []
    if not COUNCIL_LEDGER_DIR.exists():
        return rows
    for path in sorted(COUNCIL_LEDGER_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_path"] = str(path)
        rows.append(payload)
    rows.sort(key=lambda item: parse_iso(item.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def latest_council_quality_artifact() -> dict | None:
    if not COUNCIL_QUALITY_DIR.exists():
        return None
    candidates = sorted(
        COUNCIL_QUALITY_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    for path in reversed(candidates):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_path"] = str(path)
        return payload
    return None


def preview_council_quality_artifact() -> tuple[int, object]:
    payload = latest_council_quality_artifact()
    if not payload:
        return 404, {
            "error": "council-quality artifact not found",
            "expected_path": str(COUNCIL_QUALITY_DIR / "<cycle_id>.json"),
            "hint": "Run a real council cycle first. Demo ledgers do not emit council-quality artifacts.",
        }
    council_outcome = payload.get("council_outcome") or {}
    attribution = payload.get("attribution") or {}
    cel = payload.get("cel") or {}
    liminalqa = payload.get("liminalqa") or {}
    incident = liminalqa.get("incident") or {}
    relational = payload.get("relational_field") or {}
    operator_guidance = payload.get("operator_guidance") or {}
    operator_review = payload.get("operator_review") or {}
    merit_updates = cel.get("merit_updates") or []
    top_merit = max((float(item.get("merit_score") or 0.0) for item in merit_updates), default=0.0)
    return 200, {
        "cycle_id": payload.get("cycle_id"),
        "task_id": payload.get("task_id"),
        "artifact_path": payload.get("_path"),
        "relational_episode_path": payload.get("relational_episode_path"),
        "quality_score": payload.get("quality_score"),
        "relation_adjusted_quality_score": payload.get("relation_adjusted_quality_score"),
        "selected_route": council_outcome.get("selected_route"),
        "success": council_outcome.get("success"),
        "receiver_resonance_score": council_outcome.get("receiver_resonance_score"),
        "receiver_acceptance_label": council_outcome.get("receiver_acceptance_label"),
        "best_contributor_model_id": attribution.get("best_contributor_model_id"),
        "best_contributor_score": attribution.get("best_contributor_score"),
        "relation_safety_score": relational.get("relation_safety_score"),
        "recommended_mode": relational.get("recommended_mode"),
        "dominant_signal": relational.get("dominant_signal"),
        "background_pressure": relational.get("background_pressure"),
        "foreground_expression": relational.get("foreground_expression"),
        "relational_notes": relational.get("notes") or [],
        "risk_state": operator_guidance.get("risk_state"),
        "approval_posture": operator_guidance.get("approval_posture"),
        "route_strategy": operator_guidance.get("route_strategy"),
        "requires_human_review": bool(operator_guidance.get("requires_human_review")),
        "rerun_required": bool(operator_guidance.get("rerun_required")),
        "suggested_operator_action": operator_guidance.get("suggested_operator_action"),
        "operator_review_decision": operator_review.get("decision"),
        "operator_review_reviewer": operator_review.get("reviewer"),
        "operator_review_forced": bool(operator_review.get("forced")),
        "operator_review_assigned_reviewer": operator_review.get("assigned_reviewer"),
        "operator_review_closed_reason": operator_review.get("closed_reason"),
        "contribution_records": len(cel.get("contribution_records") or []),
        "reputation_updates": len(cel.get("reputation_updates") or []),
        "merit_updates": len(merit_updates),
        "top_merit_score": round(top_merit, 4),
        "liminalqa_published": bool(liminalqa.get("published")),
        "liminalqa_status_code": liminalqa.get("status_code"),
        "liminalqa_incident_published": bool(incident.get("published")),
        "liminalqa_incident_status_code": incident.get("status_code"),
    }


def preview_council_risk_queue(limit: int = 5) -> tuple[int, object]:
    if not COUNCIL_QUALITY_DIR.exists():
        return 404, {"error": "council-quality artifact not found", "items": []}
    rows: list[dict] = []
    risk_order = {"escalate": 0, "repair": 1, "watch": 2, "safe": 3}
    for path in COUNCIL_QUALITY_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        guidance = payload.get("operator_guidance") or {}
        relational = payload.get("relational_field") or {}
        outcome = payload.get("council_outcome") or {}
        quality_score = payload.get("relation_adjusted_quality_score")
        if quality_score is None:
            quality_score = payload.get("quality_score")
        rows.append(
            {
                "cycle_id": payload.get("cycle_id"),
                "risk_state": guidance.get("risk_state", "watch"),
                "recommended_mode": relational.get("recommended_mode", "n/a"),
                "approval_posture": guidance.get("approval_posture", "n/a"),
                "review_status": (payload.get("operator_review") or {}).get("decision", "pending"),
                "selected_route": outcome.get("selected_route", "unknown"),
                "quality_score": quality_score,
                "suggested_operator_action": guidance.get("suggested_operator_action", "n/a"),
            }
        )
    rows.sort(key=lambda item: (risk_order.get(str(item["risk_state"]), 2), str(item.get("cycle_id") or "")))
    return 200, {"items": rows[:limit], "total": len(rows)}


def preview_council_escalation_queue(limit: int = 5) -> tuple[int, object]:
    if not COUNCIL_QUALITY_DIR.exists():
        return 404, {"error": "council-quality artifact not found", "items": []}
    rows = iter_council_escalation_rows(COUNCIL_QUALITY_DIR)
    return 200, {"items": rows[:limit], "total": len(rows)}


def claim_next_escalation(reviewer: str, assigned_by: str = "dashboard") -> tuple[int, object]:
    try:
        rows = iter_council_escalation_rows(COUNCIL_QUALITY_DIR)
        target = next(
            (
                item
                for item in rows
                if item.get("review_status") == "pending" and item.get("assigned_reviewer") == "unassigned"
            ),
            None,
        )
        if target is None:
            return 404, {"error": "no unassigned pending escalation found"}
        updated_path = assign_council_reviewer(
            COUNCIL_QUALITY_DIR,
            str(target.get("cycle_id")),
            reviewer=reviewer,
            assigned_by=assigned_by,
        )
        return 200, {
            "cycle_id": target.get("cycle_id"),
            "assigned_reviewer": reviewer,
            "assigned_by": assigned_by,
            "artifact_path": str(updated_path),
        }
    except Exception as exc:
        return 500, {"error": str(exc)}


def close_escalation(cycle_id: str, reviewer: str, reason: str) -> tuple[int, object]:
    try:
        updated_path = close_council_escalation(
            COUNCIL_QUALITY_DIR,
            cycle_id,
            reviewer=reviewer,
            reason=reason,
        )
        return 200, {
            "cycle_id": cycle_id,
            "reviewer": reviewer,
            "reason": reason,
            "artifact_path": str(updated_path),
            "status": "closed",
        }
    except ValueError as exc:
        return 404, {"error": str(exc)}
    except Exception as exc:
        return 500, {"error": str(exc)}


def approve_escalation(cycle_id: str, reviewer: str, force: bool = False) -> tuple[int, object]:
    try:
        artifact = load_council_quality_artifact(COUNCIL_QUALITY_DIR, cycle_id)
        guidance = artifact.get("operator_guidance") or {}
        posture = str(guidance.get("approval_posture") or "evidence_check")
        if posture in {"hold_and_repair", "human_escalation"} and not force:
            return 409, {
                "error": f"approval blocked: posture={posture}",
                "cycle_id": cycle_id,
                "approval_posture": posture,
            }
        updated_path = update_council_operator_review(
            COUNCIL_QUALITY_DIR,
            cycle_id,
            decision="approved",
            reviewer=reviewer,
            forced=force,
            reason=f"approval_posture={posture}",
        )
        return 200, {
            "cycle_id": cycle_id,
            "reviewer": reviewer,
            "status": "approved",
            "forced": force,
            "artifact_path": str(updated_path),
        }
    except ValueError as exc:
        return 404, {"error": str(exc)}
    except Exception as exc:
        return 500, {"error": str(exc)}


def reject_escalation(cycle_id: str, reviewer: str, reason: str) -> tuple[int, object]:
    try:
        updated_path = update_council_operator_review(
            COUNCIL_QUALITY_DIR,
            cycle_id,
            decision="rejected",
            reviewer=reviewer,
            forced=False,
            reason=reason,
        )
        return 200, {
            "cycle_id": cycle_id,
            "reviewer": reviewer,
            "reason": reason,
            "status": "rejected",
            "artifact_path": str(updated_path),
        }
    except ValueError as exc:
        return 404, {"error": str(exc)}
    except Exception as exc:
        return 500, {"error": str(exc)}


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def build_council_analytics() -> dict:
    rows = council_ledgers()
    quality_rows = []
    if COUNCIL_QUALITY_DIR.exists():
        for path in COUNCIL_QUALITY_DIR.glob("*.json"):
            try:
                quality_rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
    if not rows:
        return {
            "ledgers": 0,
            "top_contributor": "n/a",
            "success_rate": 0.0,
            "avg_resonance": 0.0,
            "avg_merit": 0.0,
            "incident_count": 0,
            "risky_cycle_count": 0,
            "reviewed_cycle_count": 0,
            "approval_conversion_rate": 0.0,
            "escalation_rate": 0.0,
            "empty": True,
            "how_to_generate": [
                "Run a real coordination cycle through ResonanceAgent.",
                "Or click Generate Demo Council Ledger in this dashboard.",
                "Paths are relative to the project root: artifacts/council-ledger/<cycle_id>.json",
            ],
            "docs": {
                "local_setup": f"{DOCS_BASE_URL}/LIMINALQA_LOCAL_SETUP.md",
                "roadmap": f"{DOCS_BASE_URL}/COUNCIL_CONTRIBUTION_LEDGER_ROADMAP.md",
            },
            "charts": {},
        }
    best_counts: Counter[str] = Counter()
    contribution_totals: defaultdict[str, float] = defaultdict(float)
    type_totals: defaultdict[str, list[float]] = defaultdict(list)
    route_wins: Counter[str] = Counter()
    approval_outcomes: Counter[str] = Counter()
    resonance_series: list[dict] = []
    quality_series: list[dict] = []
    network_series: list[dict] = []
    merit_series: list[dict] = []
    incident_series: list[dict] = []
    review_series: list[dict] = []
    successes: list[float] = []
    resonances: list[float] = []
    merits: list[float] = []
    incident_count = 0
    risky_cycle_count = 0
    reviewed_cycle_count = 0
    approved_count = 0
    escalate_count = 0
    quality_by_cycle = {str(item.get("cycle_id") or ""): item for item in quality_rows}
    for row in rows:
        outcome = row.get("outcome", {})
        attribution = row.get("attribution", {})
        participants = row.get("participants", [])
        participant_types = {str(item.get("model_id")): str(item.get("model_type") or "unknown") for item in participants}
        best = str(attribution.get("best_contributor_model_id") or "n/a")
        best_counts[best] += 1
        route_wins[str(row.get("final_decision", {}).get("selected_route") or "unknown")] += 1
        for entry in attribution.get("contribution_breakdown", []):
            model_id = str(entry.get("model_id") or "unknown")
            score = float(entry.get("total_contribution_score") or 0.0)
            contribution_totals[model_id] += score
            type_totals[participant_types.get(model_id, "unknown")].append(score)
        success = 1.0 if outcome.get("success") else 0.0
        resonance = float(outcome.get("receiver_resonance_score", outcome.get("operator_feedback_score", 0.0)) or 0.0)
        quality = clamp((float(outcome.get("path_quality", 0.0) or 0.0) + resonance + success) / 3.0)
        network = float(outcome.get("network_improvement", 0.0) or 0.0)
        merit = clamp((float(attribution.get("best_contributor_score", 0.0) or 0.0) + resonance + max(network, 0.0)) / 3.0)
        label = str(row.get("timestamp") or f"cycle-{len(resonance_series)+1}")[:10]
        resonance_series.append({"label": label, "value": round(resonance * 100.0, 2)})
        quality_series.append({"label": label, "value": round(quality * 100.0, 2)})
        network_series.append({"label": label, "value": round(network * 100.0, 2)})
        merit_series.append({"label": label, "value": round(merit * 100.0, 2)})
        successes.append(success)
        resonances.append(resonance)
        merits.append(merit)
        quality_payload = quality_by_cycle.get(str(row.get("cycle_id") or ""))
        guidance = (quality_payload or {}).get("operator_guidance") or {}
        review = (quality_payload or {}).get("operator_review") or {}
        liminalqa = (quality_payload or {}).get("liminalqa") or {}
        risk_state = str(guidance.get("risk_state") or "watch")
        if risk_state in {"repair", "escalate"}:
            risky_cycle_count += 1
        if risk_state == "escalate":
            escalate_count += 1
        review_decision = str(review.get("decision") or "pending")
        approval_outcomes[review_decision] += 1
        if review_decision in {"approved", "rejected"}:
            reviewed_cycle_count += 1
        if review_decision == "approved":
            approved_count += 1
        if (liminalqa.get("incident") or {}).get("published"):
            incident_count += 1
        incident_series.append({"label": label, "value": incident_count})
        review_series.append({"label": label, "value": reviewed_cycle_count})
    type_lift = {key: round(avg(values), 4) for key, values in type_totals.items()}
    return {
        "ledgers": len(rows),
        "top_contributor": best_counts.most_common(1)[0][0] if best_counts else "n/a",
        "success_rate": round(avg(successes) * 100.0, 2),
        "avg_resonance": round(avg(resonances) * 100.0, 2),
        "avg_merit": round(avg(merits) * 100.0, 2),
        "incident_count": incident_count,
        "risky_cycle_count": risky_cycle_count,
        "reviewed_cycle_count": reviewed_cycle_count,
        "approval_conversion_rate": round((approved_count / len(rows)) * 100.0, 2),
        "escalation_rate": round((escalate_count / len(rows)) * 100.0, 2),
        "empty": False,
        "charts": {
            "bestContributorFrequency": [{"label": key, "value": value} for key, value in best_counts.items()],
            "cumulativeContribution": [{"label": key, "value": round(value, 4)} for key, value in contribution_totals.items()],
            "modelTypeLift": [{"label": key, "value": value} for key, value in type_lift.items()],
            "routeWins": [{"label": key, "value": value} for key, value in route_wins.items()],
            "approvalOutcomeSplit": [{"label": key, "value": value} for key, value in approval_outcomes.items()],
            "receiverResonanceTrend": resonance_series,
            "qualityScoreTrend": quality_series,
            "networkImprovementTrend": network_series,
            "averageMeritTrend": merit_series,
            "incidentTrend": incident_series,
            "reviewTrend": review_series,
        },
    }


def generate_demo_council_ledger() -> tuple[int, object]:
    COUNCIL_LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    baseline = datetime.now(timezone.utc) - timedelta(minutes=15)
    demos = [
        ("demo-cycle-001", "local-qwen", "local", "route-a", True, 0.90, 0.88, 0.17, 0.84),
        ("demo-cycle-002", "claude-web", "web", "route-c", True, 0.81, 0.82, 0.12, 0.79),
        ("demo-cycle-003", "local-qwen", "local", "route-b", False, 0.56, 0.54, 0.04, 0.63),
    ]
    written: list[str] = []
    for index, (cycle_id, model_id, model_type, route, success, resonance, path_quality, network, best_score) in enumerate(demos):
        payload = {
            "cycle_id": cycle_id,
            "task_id": cycle_id,
            "timestamp": (baseline + timedelta(minutes=5 * index)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "goal": {"type": "coordination_cycle", "summary": "Demo coordination cycle"},
            "network_context": {"route_candidates": [route], "active_nodes": ["intent", "memory"], "graph_state_version": "demo-v1"},
            "participants": [{"model_id": model_id, "model_type": model_type, "proposal_id": f"proposal-{index}", "proposal_summary": "demo proposal", "route_hint": route, "confidence": 0.8, "latency_ms": 700 + index * 200, "token_cost": 0.0 if model_type == "local" else 0.08, "selected": True, "weight_in_final_decision": 1.0}],
            "final_decision": {"selected_route": route, "decision_summary": "demo decision", "derived_from_proposals": [f"proposal-{index}"]},
            "outcome": {"success": success, "path_quality": path_quality, "network_improvement": network, "operator_intervention_required": not success, "operator_feedback_score": resonance, "receiver_type": "human", "receiver_resonance_score": resonance, "receiver_acceptance_label": "accept" if success else "needs_revision", "drift_detected": not success},
            "attribution": {"best_contributor_model_id": model_id, "best_contributor_score": best_score, "contribution_breakdown": [{"model_id": model_id, "adoption_score": 0.8, "outcome_lift": 0.15, "stability_impact": 0.12, "cost_efficiency": 1.0 if model_type == "local" else 0.5, "total_contribution_score": best_score}]},
        }
        path = COUNCIL_LEDGER_DIR / f"{cycle_id}.json"
        write_json(path, payload)
        written.append(str(path))
    return 200, {"ok": True, "message": "Demo council-ledger artifacts generated.", "ledger_count": len(written), "artifact_dir": str(COUNCIL_LEDGER_DIR), "written_files": written}


def run_real_council_cycle() -> tuple[int, object]:
    prompt = "Run a local council coordination cycle for dashboard observability and contribution tracking."
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="dashboard-council-cycle")
    agent._council_ledger_dir = COUNCIL_LEDGER_DIR
    agent._council_quality_dir = COUNCIL_QUALITY_DIR
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(agent.process_text, prompt)
        try:
            result = future.result(timeout=COUNCIL_CYCLE_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            future.cancel()
            return 504, {
                "error": "real council cycle timed out",
                "timeout_seconds": COUNCIL_CYCLE_TIMEOUT_SECONDS,
                "hint": "Try the demo council ledger first, or rerun the real cycle after the environment is warm.",
            }
    ledger = result.get("council_contribution_ledger") or {}
    artifact_path = result.get("council_contribution_ledger_artifact")
    if not artifact_path:
        return 500, {
            "error": "council ledger artifact was not created",
            "cycle_id": result.get("cycle_id"),
        }
    return 200, {
        "cycle_id": result.get("cycle_id"),
        "artifact_path": artifact_path,
        "quality_artifact_path": result.get("council_quality_artifact"),
        "selected_route": (ledger.get("final_decision") or {}).get("selected_route"),
        "best_contributor_model_id": (ledger.get("attribution") or {}).get("best_contributor_model_id"),
        "success": (ledger.get("outcome") or {}).get("success"),
        "receiver_resonance_score": (ledger.get("outcome") or {}).get("receiver_resonance_score"),
        "final_output": result.get("final_output"),
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_html(HTML_PATH.read_text(encoding="utf-8"))
            return
        if self.path == "/favicon.svg":
            body = FAVICON_SVG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/health":
            status, payload = api_request("GET", "/health")
            self.send_json(status, payload)
            return
        if self.path == "/api/quality-report-preview":
            status, payload = preview_quality_report()
            self.send_json(status, payload)
            return
        if self.path == "/api/council-analytics":
            self.send_json(200, build_council_analytics())
            return
        if self.path == "/api/council-quality-preview":
            status, payload = preview_council_quality_artifact()
            self.send_json(status, payload)
            return
        if self.path == "/api/council-risk-queue":
            status, payload = preview_council_risk_queue()
            self.send_json(status, payload)
            return
        if self.path == "/api/council-escalation-queue":
            status, payload = preview_council_escalation_queue()
            self.send_json(status, payload)
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        if self.path == "/api/health":
            status, payload = api_request("GET", "/health")
            self.send_json(status, payload)
            return
        if self.path == "/api/smoke":
            status, payload = api_request("POST", "/ingest/batch", smoke_payload())
            self.send_json(status, payload)
            return
        if self.path == "/api/run-local-lane":
            status, payload = run_local_lane()
            self.send_json(status, payload)
            return
        if self.path == "/api/generate-quality-report":
            status, payload = generate_quality_report()
            self.send_json(status, payload)
            return
        if self.path == "/api/publish-quality-report":
            status, payload = publish_quality_report()
            self.send_json(status, payload)
            return
        if self.path == "/api/query":
            status, payload = api_request("POST", "/query", {"limit": 10})
            if isinstance(payload, dict) and int(payload.get("total", 0) or 0) == 0:
                payload = {**payload, "note": "This is a lightweight preview. A zero-result query does not necessarily mean ingest is broken.", "request_payload": {"limit": 10}, "hint": "Publish Smoke Batch or Quality Report first, then retry the preview."}
            self.send_json(status, payload)
            return
        if parsed.path == "/api/generate-demo-council-ledger":
            status, payload = generate_demo_council_ledger()
            self.send_json(status, payload)
            return
        if parsed.path == "/api/run-real-council-cycle":
            status, payload = run_real_council_cycle()
            self.send_json(status, payload)
            return
        if parsed.path == "/api/claim-next-escalation":
            reviewer = (query.get("reviewer") or [""])[0].strip()
            assigned_by = (query.get("assigned_by") or ["dashboard"])[0].strip() or "dashboard"
            if not reviewer:
                self.send_json(400, {"error": "reviewer is required"})
                return
            status, payload = claim_next_escalation(reviewer, assigned_by=assigned_by)
            self.send_json(status, payload)
            return
        if parsed.path == "/api/close-escalation":
            cycle_id = (query.get("cycle_id") or [""])[0].strip()
            reviewer = (query.get("reviewer") or [""])[0].strip()
            reason = (query.get("reason") or [""])[0].strip()
            if not cycle_id or not reviewer or not reason:
                self.send_json(400, {"error": "cycle_id, reviewer, and reason are required"})
                return
            status, payload = close_escalation(cycle_id, reviewer, reason)
            self.send_json(status, payload)
            return
        if parsed.path == "/api/approve-escalation":
            cycle_id = (query.get("cycle_id") or [""])[0].strip()
            reviewer = (query.get("reviewer") or [""])[0].strip()
            force = ((query.get("force") or ["false"])[0].strip().lower() == "true")
            if not cycle_id or not reviewer:
                self.send_json(400, {"error": "cycle_id and reviewer are required"})
                return
            status, payload = approve_escalation(cycle_id, reviewer, force=force)
            self.send_json(status, payload)
            return
        if parsed.path == "/api/reject-escalation":
            cycle_id = (query.get("cycle_id") or [""])[0].strip()
            reviewer = (query.get("reviewer") or [""])[0].strip()
            reason = (query.get("reason") or [""])[0].strip()
            if not cycle_id or not reviewer or not reason:
                self.send_json(400, {"error": "cycle_id, reviewer, and reason are required"})
                return
            status, payload = reject_escalation(cycle_id, reviewer, reason)
            self.send_json(status, payload)
            return
        self.send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a small local dashboard for LiminalQA.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LiminalQA local dashboard: http://{args.host}:{args.port}")
    print(f"Proxy target: {settings()[0]}")
    server.serve_forever()


if __name__ == "__main__":
    main()
