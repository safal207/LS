from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Sequence

import ls_audit as core
import ls_audit_cml_cli as cml_cli

SOURCE_SHA_ENV = "LS_TOOL_SOURCE_SHA"
SOURCE_REPOSITORY_ENV = "LS_TOOL_SOURCE_REPOSITORY"


def _output_path(args: Sequence[str]) -> Path | None:
    try:
        parsed = cml_cli.parser().parse_args(list(args))
        _, _, output = cml_cli.resolve_invocation(parsed)
    except (SystemExit, core.InputError):
        return None
    return output


def _positive_int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if value and value.isdigit() and int(value) > 0:
        return int(value)
    return None


def _tool_metadata(source_sha: str) -> dict[str, object]:
    tool: dict[str, object] = {
        "name": "ls-exact-head-audit",
        "version": cml_cli.TOOL_VERSION,
        "source_sha": core.validate_sha(source_sha),
    }
    repository = os.environ.get(SOURCE_REPOSITORY_ENV) or os.environ.get(
        "GITHUB_REPOSITORY"
    )
    workflow = os.environ.get("GITHUB_WORKFLOW")
    run_id = _positive_int_env("GITHUB_RUN_ID")
    run_attempt = _positive_int_env("GITHUB_RUN_ATTEMPT")
    if repository:
        tool["source_repository"] = repository
    if workflow:
        tool["workflow_name"] = workflow
    if run_id is not None:
        tool["workflow_run_id"] = run_id
    if run_attempt is not None:
        tool["workflow_run_attempt"] = run_attempt
    return tool


def stamp_tool_provenance(output: Path, source_sha: str) -> None:
    manifest_path = output / "manifest.json"
    scorecard_path = output / "scorecard.json"
    markdown_path = output / "SCORECARD.md"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        scorecard = json.loads(scorecard_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise core.InputError(f"Cannot stamp tool provenance: {exc}") from exc
    if not isinstance(manifest, dict) or not isinstance(scorecard, dict):
        raise core.InputError("Cannot stamp tool provenance into a malformed bundle")

    manifest_digests = manifest.get("evidence_digests")
    scorecard_digests = scorecard.get("evidence_digests")
    if not isinstance(manifest_digests, dict) or manifest_digests != scorecard_digests:
        raise core.InputError("Manifest and Scorecard evidence digests do not match")

    tool = _tool_metadata(source_sha)
    bound = {
        "evidence_digests": sorted(manifest_digests.items()),
        "tool": tool,
    }
    bundle_digest = f"sha256:{hashlib.sha256(core.canonical(bound)).hexdigest()}"

    scorecard["tool"] = tool
    scorecard["bundle_digest"] = bundle_digest
    core.write_json(scorecard_path, scorecard)
    markdown_path.write_text(cml_cli.render_scorecard(scorecard), encoding="utf-8")

    manifest["tool"] = tool
    manifest["bundle_digest"] = bundle_digest
    manifest["scorecard_digests"] = {
        "scorecard.json": hashlib.sha256(scorecard_path.read_bytes()).hexdigest(),
        "SCORECARD.md": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
    }
    core.write_json(manifest_path, manifest)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    source_sha = os.environ.get(SOURCE_SHA_ENV)
    if source_sha:
        try:
            source_sha = core.validate_sha(source_sha)
        except core.InputError as exc:
            print(f"ls-audit: invalid {SOURCE_SHA_ENV}: {exc}", file=sys.stderr)
            return 2

    exit_code = cml_cli.main(args)
    if source_sha and exit_code in {0, 3}:
        output = _output_path(args)
        if output is None:
            print(
                "ls-audit: cannot resolve output path for tool provenance",
                file=sys.stderr,
            )
            return 5
        try:
            stamp_tool_provenance(output, source_sha)
        except (core.InputError, OSError) as exc:
            print(f"ls-audit: tool provenance failure: {exc}", file=sys.stderr)
            return 5
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
