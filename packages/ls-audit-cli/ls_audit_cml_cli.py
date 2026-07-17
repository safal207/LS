from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

import cml_git_internet as cml
import ls_audit as core
import ls_audit_cli as base


def anonymous_cml_client(timeout: float) -> core.Client:
    """Use a separate anonymous client so the target token is never forwarded."""

    return core.Client(base.GITHUB_API, None, timeout)


def _generic_cml_failure(
    registry: cml.Registry,
    *,
    pr_url: str,
    expected_head: str,
    base_sha: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": cml.EVIDENCE_SCHEMA,
        "target": {
            "pr_url": pr_url,
            "expected_head": expected_head,
            "base_sha": base_sha,
        },
        "lane_status": "INCOMPLETE",
        "sources": [
            {
                "repository": source.repository,
                "commit": source.commit,
                "status": "INCOMPLETE",
                "publishable_candidates": 0,
                "reason_code": "COLLECTION_INCOMPLETE",
            }
            for source in registry.sources
        ],
        "publishable_candidates": 0,
        "selected": [],
        "authority": {
            "approval": False,
            "execution": False,
            "delivery": False,
            "merge": False,
        },
    }


def collect_cml(
    *,
    registry: cml.Registry,
    output: Path,
    ref: core.Ref,
    expected_head: str,
    timeout: float,
) -> tuple[dict[str, Any], str]:
    pr = base.read_json(output / "evidence" / "pr.json", dict)
    files = base.read_json(output / "evidence" / "files.json", list)
    base_sha: str | None = None
    title = ""
    filenames: list[str] = []
    if pr is not None:
        title = str(pr.get("title") or "")
        base_value = (pr.get("base") or {}).get("sha")
        if isinstance(base_value, str):
            base_sha = base_value.lower()
    if files is not None:
        filenames = [
            str(item.get("filename"))
            for item in files
            if isinstance(item, dict) and isinstance(item.get("filename"), str)
        ]
    try:
        if base_sha is None:
            raise cml.CmlError("frozen target base SHA is unavailable")
        evidence = cml.collect_evidence(
            registry=registry,
            client=anonymous_cml_client(timeout),
            target={
                "pr_url": ref.url,
                "expected_head": expected_head,
                "base_sha": base_sha,
            },
            title=title,
            filenames=filenames,
        )
    except Exception:
        evidence = _generic_cml_failure(
            registry,
            pr_url=ref.url,
            expected_head=expected_head,
            base_sha=base_sha,
        )
    digest = core.write_json(output / "evidence" / "cml-memory.json", evidence)
    return evidence, digest


def render_scorecard(card: Mapping[str, Any]) -> str:
    rendered = core.markdown(dict(card))
    summary = card.get("causal_memory")
    if not isinstance(summary, dict):
        return rendered
    section = cml.render_markdown(summary)
    marker = "\n## Evidence\n"
    if marker not in rendered:
        return rendered + "\n\n" + section
    return rendered.replace(marker, "\n" + section + "\n## Evidence\n", 1)


def attach_cml_to_scorecard(
    *,
    output: Path,
    cml_evidence: Mapping[str, Any],
    cml_digest: str,
    prior_result: core.Result,
) -> core.Result:
    scorecard_path = output / "scorecard.json"
    manifest_path = output / "manifest.json"
    card = base.read_json(scorecard_path, dict)
    manifest = base.read_json(manifest_path, dict)
    if card is None or manifest is None:
        raise core.InputError("Generated Scorecard or manifest is missing")

    lanes = dict(card.get("lanes") or {})
    lane_status = str(cml_evidence.get("lane_status") or "INCOMPLETE")
    if lane_status not in {"PASS", "INCOMPLETE"}:
        lane_status = "INCOMPLETE"
    lanes["causal_memory"] = lane_status
    card["lanes"] = lanes
    card["causal_memory"] = cml.scorecard_summary(cml_evidence)

    digests = dict(card.get("evidence_digests") or {})
    digests["evidence/cml-memory.json"] = cml_digest
    card["evidence_digests"] = digests
    bundle_digest = hashlib.sha256(core.canonical(sorted(digests.items()))).hexdigest()
    card["bundle_digest"] = f"sha256:{bundle_digest}"
    card["verdict"] = base.policy_verdict(lanes, card.get("adjudication"))
    if lane_status == "INCOMPLETE" and "FAIL" not in lanes.values():
        card["interpretation"] = (
            "The exact-head audit completed, but the optional CML evidence lane is incomplete. "
            "Causal memory cannot support PASS unless a human explicitly accepts that incomplete lane with a reason."
        )

    core.write_json(scorecard_path, card)
    markdown_path = output / "SCORECARD.md"
    markdown_path.write_text(render_scorecard(card), encoding="utf-8")

    manifest["evidence_digests"] = digests
    manifest["bundle_digest"] = card["bundle_digest"]
    manifest["scorecard_digests"] = {
        "scorecard.json": hashlib.sha256(scorecard_path.read_bytes()).hexdigest(),
        "SCORECARD.md": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
    }
    core.write_json(manifest_path, manifest)
    return core.Result(
        output,
        str(card["verdict"]),
        prior_result.exact_head,
        prior_result.exit_code,
    )


def main(argv: list[str] | None = None) -> int:
    parser = core.parser()
    parser.add_argument(
        "--cml-registry",
        type=Path,
        help="Optional local Git Internet trust registry for public CML evidence.",
    )
    args = parser.parse_args(argv)
    try:
        ref = core.parse_url(args.pr_url)
        expected = core.validate_sha(args.expected_head)
        api_base = base.validate_network_boundary(ref, args.api_base)
        base.validate_finding_dispositions(args.adjudication)
        registry = cml.load_registry(args.cml_registry) if args.cml_registry else None
        output = args.output or Path(
            f"ls-audit-{ref.owner}-{ref.repo}-pr-{ref.number}-{expected[:12]}"
        )
        base.validate_output_boundary(output, args.overwrite)
        client = base.ValidatedClient(
            api_base,
            os.environ.get(args.token_env),
            args.timeout,
        )
        core.run(
            args.pr_url,
            expected,
            output,
            client,
            args.overwrite,
            args.adjudication,
        )
        cml_evidence = None
        cml_digest = None
        if registry is not None:
            cml_evidence, cml_digest = collect_cml(
                registry=registry,
                output=output,
                ref=ref,
                expected_head=expected,
                timeout=args.timeout,
            )
        final_state, final_digest = base.record_final_head(
            client, ref, expected, output
        )
        result = base.harden_scorecard(output, final_state, final_digest)
        if cml_evidence is not None and cml_digest is not None:
            result = attach_cml_to_scorecard(
                output=output,
                cml_evidence=cml_evidence,
                cml_digest=cml_digest,
                prior_result=result,
            )
    except (core.InputError, cml.CmlError) as exc:
        parser.error(str(exc))
    except core.ApiError as exc:
        if "output" in locals():
            base.cleanup_unsealed(output)
        print(
            f"ls-audit: GitHub API failure at {exc.endpoint}: {exc.message}",
            file=sys.stderr,
        )
        return 4
    except OSError as exc:
        if "output" in locals():
            base.cleanup_unsealed(output)
        print(f"ls-audit: local filesystem failure: {exc}", file=sys.stderr)
        return 5

    print(
        f"Bundle: {result.output}\n"
        f"Exact head: {result.exact_head}\n"
        f"Verdict: {result.verdict}"
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
