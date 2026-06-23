from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DiffAnalysis:
    diff_digest: str
    analysis_digest: str
    changed_files: tuple[str, ...]
    test_files: tuple[str, ...]
    added_lines: int
    removed_lines: int
    risk_flags: tuple[str, ...]
    findings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "diff_digest": self.diff_digest,
            "analysis_digest": self.analysis_digest,
            "changed_files": list(self.changed_files),
            "test_files": list(self.test_files),
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "risk_flags": list(self.risk_flags),
            "findings": list(self.findings),
            "evidence_refs": list(self.evidence_refs),
            "summary": self.summary,
        }


def analyze_diff(diff_text: str) -> DiffAnalysis:
    if not diff_text.strip():
        raise ValueError("PR review requires a non-empty diff")

    changed_files: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            changed_files.append(line[6:])
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:])

    files = tuple(dict.fromkeys(changed_files))
    test_files = tuple(
        path
        for path in files
        if path.startswith("test")
        or "/test" in path
        or path.endswith("_test.py")
    )
    added_text = "\n".join(added).lower()
    risk_flags: list[str] = []
    checks = (
        ("dynamic_code_execution", ("eval(", "exec(")),
        ("shell_execution", ("os.system(", "subprocess.")),
        ("unsafe_deserialization", ("pickle.loads(", "yaml.load(")),
    )
    for code, patterns in checks:
        if any(pattern in added_text for pattern in patterns):
            risk_flags.append(code)

    findings: list[str] = []
    if risk_flags:
        findings.append(
            "High-risk additions detected: " + ", ".join(sorted(risk_flags)) + "."
        )
    if not test_files:
        findings.append("No changed test file is present in the supplied diff.")
    else:
        findings.append(
            f"Changed test evidence is present in {len(test_files)} file(s)."
        )
    findings.append(
        f"Diff changes {len(files)} file(s), adds {len(added)} line(s), "
        f"and removes {len(removed)} line(s)."
    )

    diff_digest = hashlib.sha256(diff_text.encode("utf-8")).hexdigest()
    analysis_seed = {
        "changed_files": list(files),
        "test_files": list(test_files),
        "added_lines": len(added),
        "removed_lines": len(removed),
        "risk_flags": sorted(risk_flags),
        "findings": findings,
    }
    analysis_digest = hashlib.sha256(
        canonical_json(analysis_seed).encode("utf-8")
    ).hexdigest()
    evidence_refs = [
        f"evidence:diff:sha256:{diff_digest}",
        f"evidence:analysis:sha256:{analysis_digest}",
    ]
    if test_files:
        tests_digest = hashlib.sha256(
            canonical_json({"test_files": list(test_files)}).encode("utf-8")
        ).hexdigest()
        evidence_refs.append(f"evidence:tests:sha256:{tests_digest}")

    if risk_flags:
        summary = "The change requires blocking review because executable risk was added."
    elif test_files:
        summary = "The change has deterministic review evidence and changed tests."
    else:
        summary = "The change is reviewable but test evidence is incomplete."

    return DiffAnalysis(
        diff_digest=diff_digest,
        analysis_digest=analysis_digest,
        changed_files=files,
        test_files=test_files,
        added_lines=len(added),
        removed_lines=len(removed),
        risk_flags=tuple(sorted(risk_flags)),
        findings=tuple(findings),
        evidence_refs=tuple(evidence_refs),
        summary=summary,
    )


def build_contributions(analysis: DiffAnalysis) -> tuple[dict[str, Any], ...]:
    specs = (
        ("reviewer", "code_review", analysis.summary, analysis.findings),
        (
            "risk_critic",
            "risk_critique",
            "No blocking risk signature was found."
            if not analysis.risk_flags
            else "Blocking risk signatures were found.",
            tuple(f"risk:{flag}" for flag in analysis.risk_flags),
        ),
        (
            "verifier",
            "evidence_verification",
            "Changed test evidence is linked."
            if analysis.test_files
            else "Changed test evidence is missing.",
            analysis.evidence_refs,
        ),
    )
    contributions: list[dict[str, Any]] = []
    for role_id, capability, summary, details in specs:
        payload = {
            "role_id": role_id,
            "capability": capability,
            "summary": summary,
            "details": list(details),
            "analysis_digest": analysis.analysis_digest,
        }
        contribution_ref = "contribution:sha256:" + hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest()
        contributions.append({**payload, "contribution_ref": contribution_ref})
    return tuple(contributions)


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
