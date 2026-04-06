from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "tools" / "liminalqa_local_dashboard.html"
ENV_PATH = ROOT / ".env.liminalqa.local"
DEFAULT_REPORT_PATH = ROOT / "artifacts" / "quality-report.json"
ARTIFACTS_DIR = ROOT / "artifacts"
LANE_CONFIGS = {
    "mesh-tests": {
        "lane_key": "mesh-tests",
        "lane_title": "Mesh Tests Quality Gate",
        "threshold": "30%",
        "min_line_coverage": 30.0,
        "junit_file": ARTIFACTS_DIR / "mesh-junit.xml",
        "coverage_file": ARTIFACTS_DIR / "coverage.xml",
        "pytest_args": [
            "-m",
            "pytest",
            "-q",
            "tests/test_service_runtime.py",
            "python/tests/test_web4_mesh.py",
            "python/tests/test_web4_mesh_node.py",
            "python/tests/test_web4_mesh_transport_ws.py",
            "--junitxml=artifacts/mesh-junit.xml",
            "--cov=agent",
            "--cov=python/modules/web4_mesh",
            "--cov-report=xml:artifacts/coverage.xml",
        ],
        "pythonpath": "python",
    }
}


def load_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def resolve_settings() -> tuple[str, str]:
    env_map = load_local_env()
    base_url = os.environ.get("LIMINALQA_URL") or env_map.get("LIMINALQA_URL") or "http://127.0.0.1:8080"
    token = os.environ.get("LIMINALQA_TOKEN") or env_map.get("LIMINALQA_TOKEN") or "devtoken"
    return base_url.rstrip("/"), token


def api_request(method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    base_url, token = resolve_settings()
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"error": body or str(exc)}
        return exc.code, parsed
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def ulid_like() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")

    def encode(value: int, length: int) -> str:
        chars = []
        for _ in range(length):
            chars.append(alphabet[value & 0x1F])
            value >>= 5
        return "".join(reversed(chars))

    return encode(ms, 10) + encode(rand, 16)


def smoke_payload() -> dict:
    now = datetime.now(timezone.utc)
    started = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    completed = (now.replace(microsecond=min(now.microsecond + 120000, 999000))).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "run": {
            "run_id": ulid_like(),
            "build_id": ulid_like(),
            "plan_name": "ls-dashboard-smoke",
            "env": {"CI": "false", "SOURCE": "ls-dashboard"},
            "started_at": started,
            "runner_version": "ls-dashboard-v1",
        },
        "tests": [
            {
                "name": "dashboard_smoke_publish",
                "suite": "ls.local.dashboard",
                "guidance": "Local dashboard smoke publish",
                "status": "pass",
                "duration_ms": 120,
                "started_at": started,
                "completed_at": completed,
            }
        ],
        "signals": [
            {
                "test_name": "dashboard_smoke_publish",
                "kind": "system",
                "value": 1.0,
                "meta": {"note": "dashboard smoke publish"},
                "at": started,
            }
        ],
        "artifacts": [],
    }


def locate_quality_report() -> pathlib.Path | None:
    if DEFAULT_REPORT_PATH.exists():
        return DEFAULT_REPORT_PATH
    candidates = sorted(ROOT.glob("artifacts/**/quality-report.json"))
    return candidates[0] if candidates else None


def aggregate_quality_reports(reports: list[dict], label: str = "local-dashboard") -> dict:
    counts = Counter(report.get("verdict", "UNKNOWN") for report in reports)
    aggregate_verdict = "PASS"
    if counts.get("BLOCK"):
        aggregate_verdict = "BLOCK"
    elif counts.get("WARN"):
        aggregate_verdict = "WARN"
    elif not reports:
        aggregate_verdict = "WARN"

    min_coverage_values = [
        report["min_line_coverage_observed"]
        for report in reports
        if report.get("min_line_coverage_observed") is not None
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "local/LS",
        "event_name": "manual",
        "ref": "local",
        "sha": None,
        "run_id": None,
        "run_attempt": None,
        "workflow": "local-dashboard",
        "workflow_job": "local-dashboard",
        "run_url": f"{resolve_settings()[0]}/health",
        "label": label,
        "aggregate_verdict": aggregate_verdict,
        "lane_count": len(reports),
        "verdict_counts": dict(counts),
        "total_failures": sum(int(report.get("total_failures", 0)) for report in reports),
        "flaky_suspect_lanes": [
            report.get("lane_key") for report in reports if report.get("flaky_suspect")
        ],
        "min_line_coverage_observed": min(min_coverage_values) if min_coverage_values else None,
        "lanes": reports,
    }


def evaluate_quality_gate(
    artifacts_dir: pathlib.Path,
    max_failures: int = 0,
    min_line_coverage: float | None = None,
    require_junit: bool = True,
    require_coverage: bool = True,
) -> dict:
    junit_files = sorted(artifacts_dir.glob("*junit.xml"))
    coverage_files = sorted(artifacts_dir.glob("*coverage.xml"))

    total_tests = total_failures = total_errors = total_skipped = 0
    total_time = 0.0
    observed_coverages: list[float] = []
    issues: list[str] = []

    for path in junit_files:
        root = ET.parse(path).getroot()
        total_tests += int(float(root.attrib.get("tests", 0) or 0))
        total_failures += int(float(root.attrib.get("failures", 0) or 0))
        total_errors += int(float(root.attrib.get("errors", 0) or 0))
        total_skipped += int(float(root.attrib.get("skipped", 0) or 0))
        total_time += float(root.attrib.get("time", 0) or 0)

    for path in coverage_files:
        root = ET.parse(path).getroot()
        observed_coverages.append(float(root.attrib.get("line-rate", 0) or 0) * 100.0)

    total_failed_like = total_failures + total_errors
    min_observed_coverage = min(observed_coverages) if observed_coverages else None

    if require_junit and not junit_files:
        issues.append("JUnit artifacts are missing.")
    if require_coverage and not coverage_files:
        issues.append("Coverage artifacts are missing.")
    if total_failed_like > max_failures:
        issues.append(f"Failures+errors {total_failed_like} exceed threshold {max_failures}.")
    if min_line_coverage is not None:
        if min_observed_coverage is None:
            issues.append("Coverage threshold configured but no coverage XML files were found.")
        elif min_observed_coverage < min_line_coverage:
            issues.append(
                f"Minimum line coverage {min_observed_coverage:.1f}% is below threshold {min_line_coverage:.1f}%."
            )

    if issues:
        verdict = "BLOCK"
    elif not junit_files or not coverage_files:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "total_tests": total_tests,
        "total_failures": total_failed_like,
        "total_skipped": total_skipped,
        "runtime_seconds": total_time,
        "min_line_coverage_observed": min_observed_coverage,
        "junit_files": [path.name for path in junit_files],
        "coverage_files": [path.name for path in coverage_files],
        "issues": issues,
    }


def write_lane_snapshot(report: dict) -> pathlib.Path:
    quality_dir = ARTIFACTS_DIR / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    report_path = quality_dir / f"{report['lane_key']}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report_path


def run_local_lane(lane_key: str) -> tuple[int, object]:
    config = LANE_CONFIGS.get(lane_key)
    if config is None:
        return 404, {"error": f"unknown lane: {lane_key}"}

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    for artifact_path in [config["junit_file"], config["coverage_file"]]:
        if artifact_path.exists():
            artifact_path.unlink()

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = config["pythonpath"] if not existing_pythonpath else f"{config['pythonpath']}{os.pathsep}{existing_pythonpath}"

    command = [sys.executable, *config["pytest_args"]]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    gate = evaluate_quality_gate(
        ARTIFACTS_DIR,
        max_failures=0,
        min_line_coverage=config["min_line_coverage"],
        require_junit=True,
        require_coverage=True,
    )

    lane_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": "local/LS",
        "event_name": "manual",
        "ref": "local",
        "sha": None,
        "run_id": None,
        "run_attempt": None,
        "job": "local-dashboard",
        "lane_key": config["lane_key"],
        "lane_title": config["lane_title"],
        "verdict": gate["verdict"],
        "total_failures": gate["total_failures"],
        "min_line_coverage_observed": gate["min_line_coverage_observed"],
        "threshold": config["threshold"],
        "flaky_suspect": False,
        "run_url": f"{resolve_settings()[0]}/health",
    }
    lane_snapshot_path = write_lane_snapshot(lane_report)
    reports = []
    for path in sorted((ARTIFACTS_DIR / "quality").glob("*.json")):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    aggregate = aggregate_quality_reports(reports)
    output_path = ROOT / "artifacts" / "quality-report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")

    return_code = 200 if completed.returncode == 0 and gate["verdict"] != "BLOCK" else 422
    return return_code, {
        "lane_key": lane_key,
        "lane_title": config["lane_title"],
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "verdict": gate["verdict"],
        "total_failures": gate["total_failures"],
        "min_line_coverage_observed": gate["min_line_coverage_observed"],
        "issues": gate["issues"],
        "junit_files": gate["junit_files"],
        "coverage_files": gate["coverage_files"],
        "lane_snapshot_path": str(lane_snapshot_path),
        "quality_report_path": str(output_path),
        "stdout_tail": "\n".join(completed.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(completed.stderr.splitlines()[-40:]),
    }


def generate_quality_report() -> tuple[int, object]:
    quality_dir = ROOT / "artifacts" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    lane_files = sorted(quality_dir.glob("*.json"))
    reports = []

    for path in lane_files:
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001
            return 400, {
                "error": f"failed to parse lane snapshot: {exc}",
                "lane_path": str(path),
            }

    if not reports:
        bootstrap = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repository": "local/LS",
            "event_name": "manual",
            "ref": "local",
            "sha": None,
            "run_id": None,
            "run_attempt": None,
            "job": "local-dashboard",
            "lane_key": "local-dashboard",
            "lane_title": "Local Dashboard",
            "verdict": "PASS",
            "total_failures": 0,
            "min_line_coverage_observed": None,
            "threshold": "manual bootstrap",
            "flaky_suspect": False,
            "run_url": f"{resolve_settings()[0]}/health",
        }
        bootstrap_path = quality_dir / "local-dashboard.json"
        bootstrap_path.write_text(json.dumps(bootstrap, indent=2) + "\n", encoding="utf-8")
        reports.append(bootstrap)

    aggregate = aggregate_quality_reports(reports)
    output_path = ROOT / "artifacts" / "quality-report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")

    return 200, {
        "report_path": str(output_path),
        "aggregate_verdict": aggregate.get("aggregate_verdict"),
        "lane_count": aggregate.get("lane_count"),
        "total_failures": aggregate.get("total_failures"),
        "verdict_counts": aggregate.get("verdict_counts"),
    }


def quality_report_payload(report: dict) -> dict:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    run_id = ulid_like()
    build_id = ulid_like()

    def map_status(lane: dict) -> str:
        verdict = str(lane.get("verdict", "WARN")).upper()
        if verdict == "PASS" and lane.get("flaky_suspect"):
            return "flake"
        if verdict == "PASS":
            return "pass"
        if verdict == "BLOCK":
            return "fail"
        return "skip"

    tests = []
    signals = []
    for lane in report.get("lanes", []):
        lane_key = str(lane.get("lane_key", "unknown"))
        lane_title = str(lane.get("lane_title", lane_key))
        threshold = lane.get("threshold")
        verdict = str(lane.get("verdict", "WARN")).upper()
        coverage = lane.get("min_line_coverage_observed")
        total_failures = int(lane.get("total_failures", 0))
        flaky_suspect = bool(lane.get("flaky_suspect"))
        run_url = lane.get("run_url") or report.get("run_url")

        error = None
        if verdict == "BLOCK":
            error = {
                "error_type": "QualityGateBlock",
                "message": (
                    f"{lane_title} blocked: failures={total_failures}, "
                    f"min_coverage={coverage}, threshold={threshold}"
                ),
            }

        tests.append(
            {
                "name": lane_key,
                "suite": "github-actions.quality-gate",
                "guidance": threshold,
                "status": map_status(lane),
                "duration_ms": None,
                "error": error,
                "started_at": report.get("generated_at") or now_iso,
                "completed_at": report.get("generated_at") or now_iso,
            }
        )
        signals.append(
            {
                "test_name": lane_key,
                "kind": "system",
                "latency_ms": None,
                "value": float(total_failures),
                "meta": {
                    "lane_title": lane_title,
                    "aggregate_verdict": report.get("aggregate_verdict"),
                    "lane_verdict": verdict,
                    "threshold": threshold,
                    "min_line_coverage_observed": coverage,
                    "flaky_suspect": flaky_suspect,
                    "run_url": run_url,
                    "source": "ls-dashboard",
                },
                "at": report.get("generated_at") or now_iso,
            }
        )

    return {
        "run": {
            "run_id": run_id,
            "build_id": build_id,
            "plan_name": "ls-local-quality-report",
            "env": {
                "CI": "false",
                "SOURCE": "ls-dashboard",
                "QUALITY_AGGREGATE_VERDICT": str(report.get("aggregate_verdict", "")),
            },
            "started_at": report.get("generated_at") or now_iso,
            "runner_version": "ls-dashboard-quality-report-v1",
        },
        "tests": tests,
        "signals": signals,
        "artifacts": [],
    }


def publish_quality_report() -> tuple[int, object]:
    report_path = locate_quality_report()
    if report_path is None:
        return 404, {
            "error": "quality-report.json not found",
            "expected_path": str(DEFAULT_REPORT_PATH),
        }

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return 400, {
            "error": f"failed to parse quality report: {exc}",
            "report_path": str(report_path),
        }

    payload = quality_report_payload(report)
    status, response = api_request("POST", "/ingest/batch", payload)
    details = response if isinstance(response, dict) else {"response": response}
    return status, {
        "report_path": str(report_path),
        "aggregate_verdict": report.get("aggregate_verdict"),
        "lane_count": len(report.get("lanes", [])),
        "ingest": details,
    }


def preview_quality_report() -> tuple[int, object]:
    report_path = locate_quality_report()
    if report_path is None:
        return 404, {
            "error": "quality-report.json not found",
            "expected_path": str(DEFAULT_REPORT_PATH),
        }

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return 400, {
            "error": f"failed to parse quality report: {exc}",
            "report_path": str(report_path),
        }

    lanes = []
    for lane in report.get("lanes", []):
        lanes.append(
            {
                "lane_key": lane.get("lane_key"),
                "lane_title": lane.get("lane_title"),
                "verdict": lane.get("verdict"),
                "total_failures": lane.get("total_failures"),
                "min_line_coverage_observed": lane.get("min_line_coverage_observed"),
                "flaky_suspect": lane.get("flaky_suspect"),
            }
        )

    return 200, {
        "report_path": str(report_path),
        "generated_at": report.get("generated_at"),
        "aggregate_verdict": report.get("aggregate_verdict"),
        "lane_count": report.get("lane_count"),
        "total_failures": report.get("total_failures"),
        "min_line_coverage_observed": report.get("min_line_coverage_observed"),
        "verdict_counts": report.get("verdict_counts", {}),
        "lanes": lanes,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send_html(HTML_PATH.read_text(encoding="utf-8"))
            return
        if self.path == "/api/health":
            status, payload = api_request("GET", "/health")
            self._send_json(status, payload)
            return
        if self.path == "/api/lane-options":
            self._send_json(
                200,
                {
                    "lanes": [
                        {"key": key, "title": value["lane_title"], "threshold": value["threshold"]}
                        for key, value in LANE_CONFIGS.items()
                    ]
                },
            )
            return
        if self.path == "/api/quality-report-preview":
            status, payload = preview_quality_report()
            self._send_json(status, payload)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/smoke":
            status, payload = api_request("POST", "/ingest/batch", smoke_payload())
            self._send_json(status, payload)
            return
        if self.path == "/api/run-local-lane":
            status, payload = run_local_lane("mesh-tests")
            self._send_json(status, payload)
            return
        if self.path == "/api/generate-quality-report":
            status, payload = generate_quality_report()
            self._send_json(status, payload)
            return
        if self.path == "/api/publish-quality-report":
            status, payload = publish_quality_report()
            self._send_json(status, payload)
            return
        if self.path == "/api/query":
            status, payload = api_request("POST", "/query", {"limit": 10})
            self._send_json(status, payload)
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a small local dashboard for LiminalQA.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LiminalQA local dashboard: http://{args.host}:{args.port}")
    print(f"Proxy target: {resolve_settings()[0]}")
    server.serve_forever()


if __name__ == "__main__":
    main()
