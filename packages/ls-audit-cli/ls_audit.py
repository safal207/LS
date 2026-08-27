from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

VERSION = "0.1.0"
SCHEMA = "ls.exact-head-audit.v0.1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PR_PATH = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)/?$")


class InputError(ValueError):
    pass


class ApiError(RuntimeError):
    def __init__(self, endpoint: str, status: int | None, message: str) -> None:
        super().__init__(message)
        self.endpoint, self.status, self.message = endpoint, status, message


@dataclass(frozen=True)
class Ref:
    host: str
    owner: str
    repo: str
    number: int

    @property
    def url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.repo}/pull/{self.number}"


@dataclass(frozen=True)
class Result:
    output: Path
    verdict: str
    exact_head: str
    exit_code: int


class Client:
    def __init__(self, base: str, token: str | None, timeout: float = 30.0,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.base, self.token, self.timeout, self.opener = base.rstrip("/"), token, timeout, opener

    def get(self, endpoint: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ls-exact-head-audit/{VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(f"{self.base}{endpoint}", headers=headers)
        try:
            with self.opener(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            try:
                body = json.loads(body).get("message", body)
            except json.JSONDecodeError:
                pass
            raise ApiError(endpoint, exc.code, str(body)) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ApiError(endpoint, None, str(exc)) from exc

    def pages(self, endpoint: str) -> list[Any]:
        out: list[Any] = []
        for page in range(1, 21):
            sep = "&" if "?" in endpoint else "?"
            chunk = self.get(f"{endpoint}{sep}per_page=100&page={page}")
            if not isinstance(chunk, list):
                raise ApiError(endpoint, None, "Expected list response")
            out.extend(chunk)
            if len(chunk) < 100:
                break
        return out


def parse_url(value: str) -> Ref:
    parsed = urllib.parse.urlparse(value.strip())
    match = PR_PATH.match(parsed.path)
    if parsed.scheme != "https" or not parsed.hostname or not match:
        raise InputError("PR URL must match https://<host>/<owner>/<repo>/pull/<number>")
    owner, repo, number = match.groups()
    return Ref(parsed.hostname.lower(), owner, repo, int(number))


def validate_sha(value: str) -> str:
    value = value.strip().lower()
    if not SHA40.fullmatch(value):
        raise InputError("Expected head must be a full 40-character hexadecimal SHA")
    return value


def api_base(ref: Ref) -> str:
    return "https://api.github.com" if ref.host == "github.com" else f"https://{ref.host}/api/v3"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def write_json(path: Path, value: Any) -> str:
    data = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def safe(call: Callable[[], Any]) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        return call(), None
    except ApiError as exc:
        return None, {"endpoint": exc.endpoint, "http_status": exc.status, "message": exc.message}


def adjudication(path: Path | None, ref: Ref, expected: str) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"Cannot read adjudication JSON: {exc}") from exc
    if data.get("schema_version") != "ls.human-adjudication.v0.1":
        raise InputError("Invalid adjudication schema_version")
    if data.get("target") != {"pr_url": ref.url, "expected_head": expected}:
        raise InputError("Adjudication target does not match PR URL and expected head")
    if data.get("decision") not in {"PASS", "HOLD", "INCONCLUSIVE"}:
        raise InputError("Adjudication decision must be PASS, HOLD, or INCONCLUSIVE")
    if not str(data.get("reviewer") or "").strip() or not str(data.get("summary") or "").strip():
        raise InputError("Adjudication reviewer and summary are required")
    if not isinstance(data.get("findings"), list) or not isinstance(data.get("accepted_incomplete_lanes", []), list):
        raise InputError("Adjudication findings and accepted_incomplete_lanes must be lists")
    for item in data.get("accepted_incomplete_lanes", []):
        if not isinstance(item, dict) or not item.get("lane") or not item.get("reason"):
            raise InputError("Accepted incomplete lanes require lane and reason")
    return data


def template(ref: Ref, expected: str) -> dict[str, Any]:
    return {
        "schema_version": "ls.human-adjudication.v0.1",
        "target": {"pr_url": ref.url, "expected_head": expected},
        "reviewer": "", "decision": "INCONCLUSIVE", "summary": "",
        "accepted_incomplete_lanes": [], "findings": [],
    }


def check_lane(checks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    bounded, states = [], []
    failures = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
    for check in checks:
        conclusion, status = check.get("conclusion"), check.get("status")
        state = "INCOMPLETE" if status != "completed" or conclusion is None else (
            "PASS" if conclusion == "success" else "FAIL" if conclusion in failures else "INCOMPLETE"
        )
        states.append(state)
        bounded.append({
            "name": check.get("name"), "app": (check.get("app") or {}).get("slug"),
            "status": status, "conclusion": conclusion, "lane_status": state,
            "details_url": check.get("details_url"),
        })
    overall = "NOT_RUN" if not states else "FAIL" if "FAIL" in states else "INCOMPLETE" if "INCOMPLETE" in states else "PASS"
    return overall, bounded


def verdict(lanes: dict[str, str], human: dict[str, Any] | None) -> str:
    if "FAIL" in lanes.values():
        return "HOLD"
    if human is None:
        return "INCOMPLETE — HUMAN ADJUDICATION REQUIRED"
    if human["decision"] == "HOLD":
        return "HOLD — HUMAN ADJUDICATED"
    if human["decision"] == "INCONCLUSIVE":
        return "INCONCLUSIVE — HUMAN ADJUDICATED"
    accepted = {x["lane"] for x in human.get("accepted_incomplete_lanes", [])}
    missing = {k for k, v in lanes.items() if k != "human_adjudication" and v in {"NOT_RUN", "INCOMPLETE"}}
    return "PASS — HUMAN ADJUDICATED" if missing <= accepted else "INCONCLUSIVE — UNACCEPTED INCOMPLETE EVIDENCE"


def markdown(card: dict[str, Any]) -> str:
    target = card["target"]
    lines = [
        "# LS Exact-Head PR Risk Audit", "", f"- PR: {target['pr_url']}",
        f"- Expected head: `{target['expected_head']}`", f"- Observed head: `{target.get('observed_head') or 'UNAVAILABLE'}`",
        f"- Verdict: **{card['verdict']}**", "- Authority: **advisory only — no merge authority**", "",
        "## Lanes", "", "| Lane | Status |", "| --- | --- |",
    ]
    lines += [f"| `{name}` | **{state}** |" for name, state in card["lanes"].items()]
    lines += ["", "## Interpretation", "", card["interpretation"], "", "## Evidence", ""]
    lines += [f"- `{path}` — `sha256:{digest}`" for path, digest in card["evidence_digests"].items()]
    lines += ["", "## Boundaries", "", "- `NOT_RUN` and `INCOMPLETE` never count as success.",
              "- Reviews bound to another commit are stale evidence.", "- This bundle cannot approve or merge the PR.", ""]
    return "\n".join(lines)


def run(pr_url: str, expected_head: str, output: Path, client: Client,
        overwrite: bool = False, adjudication_path: Path | None = None) -> Result:
    ref, expected = parse_url(pr_url), validate_sha(expected_head)
    human = adjudication(adjudication_path, ref, expected)
    if output.exists() and not output.is_dir():
        raise InputError(f"Output path is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        if not overwrite:
            raise InputError(f"Output directory is not empty: {output}")
        shutil.rmtree(output)
    evidence = output / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)

    endpoint = f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}"
    pr = client.get(endpoint)
    observed = str((pr.get("head") or {}).get("sha") or "").lower() or None
    exact = "PASS" if observed == expected else "FAIL"
    bounded_pr = {
        "url": pr.get("html_url"), "number": pr.get("number"), "title": pr.get("title"),
        "state": pr.get("state"), "draft": pr.get("draft"), "author": (pr.get("user") or {}).get("login"),
        "head": {"sha": observed, "ref": (pr.get("head") or {}).get("ref")},
        "base": {"sha": (pr.get("base") or {}).get("sha"), "ref": (pr.get("base") or {}).get("ref")},
        "changed_files": pr.get("changed_files"), "additions": pr.get("additions"), "deletions": pr.get("deletions"),
    }
    digests = {"evidence/pr.json": write_json(evidence / "pr.json", bounded_pr)}
    files = reviews = status = checks = None
    errors: dict[str, Any] = {}
    if exact == "PASS":
        files, errors["files"] = safe(lambda: client.pages(f"{endpoint}/files"))
        reviews, errors["reviews"] = safe(lambda: client.pages(f"{endpoint}/reviews"))
        status, errors["commit_status"] = safe(lambda: client.get(f"/repos/{ref.owner}/{ref.repo}/commits/{expected}/status"))
        checks, errors["check_runs"] = safe(lambda: client.get(f"/repos/{ref.owner}/{ref.repo}/commits/{expected}/check-runs?per_page=100"))
        errors = {k: v for k, v in errors.items() if v}
        if files is not None:
            files = [{k: f.get(k) for k in ("sha", "filename", "status", "additions", "deletions", "changes", "previous_filename", "blob_url", "patch")} for f in files]
            digests["evidence/files.json"] = write_json(evidence / "files.json", files)
        if reviews is not None:
            reviews = [{"id": r.get("id"), "reviewer": (r.get("user") or {}).get("login"), "state": r.get("state"),
                        "commit_id": r.get("commit_id"), "exact_head": r.get("commit_id") == expected,
                        "submitted_at": r.get("submitted_at"), "html_url": r.get("html_url")} for r in reviews]
            digests["evidence/reviews.json"] = write_json(evidence / "reviews.json", reviews)
        if status is not None:
            digests["evidence/commit-status.json"] = write_json(evidence / "commit-status.json", status)
        if checks is not None:
            digests["evidence/check-runs.json"] = write_json(evidence / "check-runs.json", checks)
    if errors:
        digests["evidence/api-errors.json"] = write_json(evidence / "api-errors.json", errors)
    if human:
        digests["evidence/human-adjudication.json"] = write_json(evidence / "human-adjudication.json", human)

    checks_state, bounded_checks = check_lane(list((checks or {}).get("check_runs") or []))
    if checks is not None:
        digests["evidence/check-runs-bounded.json"] = write_json(evidence / "check-runs-bounded.json", bounded_checks)
    status_state = "NOT_RUN" if status is None else {"success": "PASS", "failure": "FAIL", "error": "FAIL", "pending": "INCOMPLETE"}.get(status.get("state"), "NOT_RUN")
    review_state = "NOT_RUN" if reviews == [] else "PASS" if any(r["exact_head"] for r in reviews or []) else "INCOMPLETE"
    if reviews is None and "reviews" in errors:
        review_state = "INCOMPLETE"
    lanes = {
        "exact_head": exact,
        "changed_files": "PASS" if files is not None else "NOT_RUN" if exact == "FAIL" else "INCOMPLETE",
        "commit_status": status_state if exact == "PASS" else "NOT_RUN",
        "check_runs": checks_state if exact == "PASS" else "NOT_RUN",
        "exact_head_reviews": review_state if exact == "PASS" else "NOT_RUN",
        "human_adjudication": "PASS" if human else "NOT_RUN",
    }
    decision = verdict(lanes, human)
    interpretation = (
        "The current PR head does not match the expected SHA. Secondary collection stopped fail-closed."
        if exact == "FAIL" else
        "The exact head matched, but human adjudication has not run. Complete adjudication-template.json and rerun."
        if human is None else
        "Human adjudication supports PASS; accepted incomplete lanes are explicit and reasoned."
        if decision.startswith("PASS") else
        "The evidence does not support PASS. Preserve this bundle and do not treat it as approval."
    )
    bundle_digest = hashlib.sha256(canonical(sorted(digests.items()))).hexdigest()
    target = {"pr_url": ref.url, "host": ref.host, "owner": ref.owner, "repo": ref.repo,
              "pr_number": ref.number, "expected_head": expected, "observed_head": observed}
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = {"schema_version": SCHEMA, "tool": {"name": "ls-exact-head-audit", "version": VERSION},
                "generated_at": now, "target": target, "authority": "advisory-only",
                "evidence_digests": digests, "bundle_digest": f"sha256:{bundle_digest}"}
    write_json(output / "manifest.json", manifest)
    write_json(output / "adjudication-template.json", template(ref, expected))
    card = {"schema_version": SCHEMA, "generated_at": now, "target": target, "verdict": decision,
            "lanes": lanes, "interpretation": interpretation, "evidence_digests": digests,
            "bundle_digest": manifest["bundle_digest"], "authority": "advisory-only", "adjudication": human}
    write_json(output / "scorecard.json", card)
    (output / "SCORECARD.md").write_text(markdown(card))
    return Result(output, decision, exact, 3 if exact == "FAIL" else 0)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ls-audit", description="Freeze GitHub PR evidence at an exact head SHA.")
    p.add_argument("pr_url")
    p.add_argument("--expected-head", required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--api-base")
    p.add_argument("--token-env", default="GITHUB_TOKEN")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--adjudication", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    p, args = parser(), parser().parse_args(argv)
    try:
        ref, expected = parse_url(args.pr_url), validate_sha(args.expected_head)
        output = args.output or Path(f"ls-audit-{ref.owner}-{ref.repo}-pr-{ref.number}-{expected[:12]}")
        result = run(args.pr_url, expected, output,
                     Client(args.api_base or api_base(ref), os.environ.get(args.token_env), args.timeout),
                     args.overwrite, args.adjudication)
    except InputError as exc:
        p.error(str(exc))
    except ApiError as exc:
        print(f"ls-audit: GitHub API failure at {exc.endpoint}: {exc.message}", file=sys.stderr)
        return 4
    print(f"Bundle: {result.output}\nExact head: {result.exact_head}\nVerdict: {result.verdict}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
