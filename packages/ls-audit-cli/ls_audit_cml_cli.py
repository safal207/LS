from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping
import urllib.parse
import urllib.request

import cml_git_internet as cml
import ls_audit as core
import ls_audit_cli as base

TOOL_VERSION = "0.2.0"
_BASE64_BYTES = 4 * ((cml.MAX_FILE_BYTES + 2) // 3)
MAX_CML_ENCODED_CHARS = _BASE64_BYTES + 2 * ((_BASE64_BYTES + 59) // 60) + 4


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject every redirect so credentials and trust never cross hosts."""

    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(NoRedirectHandler())


def open_without_redirect(request: Any, *, timeout: float) -> Any:
    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)


def target_client(api_base: str, token: str | None, timeout: float) -> core.Client:
    return base.ValidatedClient(
        api_base,
        token,
        timeout,
        opener=open_without_redirect,
    )


class AnonymousPublicCmlClient(core.Client):
    """Anonymous client with exact-pin, public-source, and envelope checks."""

    def __init__(
        self,
        base_url: str,
        token: str | None,
        timeout: float,
        *,
        opener: Any = open_without_redirect,
    ) -> None:
        super().__init__(base_url, token, timeout, opener=opener)
        self._verified_pins: set[tuple[str, str]] = set()

    @staticmethod
    def _parts(endpoint: str) -> tuple[list[str], dict[str, list[str]]]:
        parsed = urllib.parse.urlsplit(endpoint)
        return (
            parsed.path.strip("/").split("/") if parsed.path else [],
            urllib.parse.parse_qs(parsed.query, keep_blank_values=True),
        )

    def _verify_exact_pin(self, repository: str, commit: str) -> None:
        key = (repository, commit)
        if key in self._verified_pins:
            return
        resolved = super().get(f"/repos/{repository}/commits/{commit}")
        if not isinstance(resolved, dict) or resolved.get("sha") != commit:
            raise cml.CmlError("CML source commit did not resolve to the registry pin")
        self._verified_pins.add(key)

    @staticmethod
    def _validate_content_envelope(value: Mapping[str, Any]) -> None:
        size = value.get("size")
        encoded = value.get("content")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or size > cml.MAX_FILE_BYTES
        ):
            raise cml.CmlError("CML content size is missing, malformed, or oversized")
        if value.get("encoding") != "base64" or not isinstance(encoded, str):
            raise cml.CmlError("CML content must use bounded base64 encoding")
        if len(encoded) > MAX_CML_ENCODED_CHARS:
            raise cml.CmlError("CML base64 envelope exceeds the safe character bound")
        compact = "".join(encoded.split())
        expected_length = 4 * ((size + 2) // 3)
        if len(compact) != expected_length or len(compact) % 4:
            raise cml.CmlError("CML base64 envelope does not match its declared size")
        padding = 2 if compact.endswith("==") else 1 if compact.endswith("=") else 0
        decoded_size = 3 * (len(compact) // 4) - padding
        if decoded_size != size:
            raise cml.CmlError("CML base64 padding does not match its declared size")

    def get(self, endpoint: str) -> Any:
        parts, query = self._parts(endpoint)
        is_repo_metadata = len(parts) == 3 and parts[0] == "repos"
        is_content = len(parts) >= 5 and parts[0] == "repos" and parts[3] == "contents"
        if is_content:
            refs = query.get("ref", [])
            repository = "/".join(parts[1:3])
            if len(refs) != 1 or not cml.SHA40.fullmatch(refs[0]):
                raise cml.CmlError("CML content request requires one exact commit pin")
            self._verify_exact_pin(repository, refs[0])

        value = super().get(endpoint)
        if is_repo_metadata:
            if (
                not isinstance(value, dict)
                or value.get("private") is not False
                or value.get("visibility") != "public"
            ):
                raise cml.CmlError("CML source must be a public GitHub repository")
        if is_content and isinstance(value, dict):
            self._validate_content_envelope(value)
        return value


def anonymous_cml_client(timeout: float) -> core.Client:
    """Use a separate anonymous client so the target token is never forwarded."""

    return AnonymousPublicCmlClient(
        base.GITHUB_API,
        None,
        timeout,
        opener=open_without_redirect,
    )


def _authority() -> dict[str, bool]:
    return {
        "approval": False,
        "execution": False,
        "delivery": False,
        "merge": False,
    }


def _source_states(
    registry: cml.Registry, *, status: str, reason_code: str
) -> list[dict[str, Any]]:
    return [
        {
            "repository": source.repository,
            "commit": source.commit,
            "status": status,
            "publishable_candidates": 0,
            "reason_code": reason_code,
        }
        for source in registry.sources
    ]


def _generic_cml_failure(
    registry: cml.Registry,
    *,
    pr_url: str,
    expected_head: str,
    base_sha: str | None,
    reason_code: str = "COLLECTION_INCOMPLETE",
) -> dict[str, Any]:
    return {
        "schema_version": cml.EVIDENCE_SCHEMA,
        "target": {
            "pr_url": pr_url,
            "expected_head": expected_head,
            "base_sha": base_sha,
        },
        "lane_status": "INCOMPLETE",
        "sources": _source_states(
            registry,
            status="INCOMPLETE",
            reason_code=reason_code,
        ),
        "publishable_candidates": 0,
        "selected": [],
        "authority": _authority(),
    }


def _cml_not_run(
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
        "lane_status": "NOT_RUN",
        "sources": _source_states(
            registry,
            status="NOT_RUN",
            reason_code="INITIAL_EXACT_HEAD_MISMATCH",
        ),
        "publishable_candidates": 0,
        "selected": [],
        "authority": _authority(),
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
    observed_head: str | None = None
    title = ""
    filenames: list[str] = []
    if pr is not None:
        title = str(pr.get("title") or "")
        base_value = (pr.get("base") or {}).get("sha")
        head_value = (pr.get("head") or {}).get("sha")
        if isinstance(base_value, str):
            base_sha = base_value.lower()
        if isinstance(head_value, str):
            observed_head = head_value.lower()
    if files is not None:
        filenames = [
            str(item.get("filename"))
            for item in files
            if isinstance(item, dict) and isinstance(item.get("filename"), str)
        ]

    if observed_head != expected_head:
        evidence = _cml_not_run(
            registry,
            pr_url=ref.url,
            expected_head=expected_head,
            base_sha=base_sha,
        )
    elif files is None:
        evidence = _generic_cml_failure(
            registry,
            pr_url=ref.url,
            expected_head=expected_head,
            base_sha=base_sha,
            reason_code="FROZEN_QUERY_EVIDENCE_INCOMPLETE",
        )
    else:
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


def _safe_markdown(value: object, limit: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    text = html.escape(text.replace("`", "'"), quote=False)
    text = text.replace("\\", "\\\\")
    for character in "*_[]()#!|":
        text = text.replace(character, "\\" + character)
    return text


def render_cml_section(summary: Mapping[str, Any]) -> str:
    lines = [
        "## Causal Memory",
        "",
        f"- Lane: **{_safe_markdown(summary.get('lane_status'), 40)}**",
        f"- Trusted sources: **{int(summary.get('source_count') or 0)}**",
        f"- Publishable candidates: **{int(summary.get('publishable_candidates') or 0)}**",
        f"- Selected memories: **{int(summary.get('selected_count') or 0)}**",
        "",
    ]
    selected = summary.get("selected") or []
    if selected:
        for index, item in enumerate(selected, start=1):
            path = " → ".join(
                _safe_markdown(value, 220)
                for value in (item.get("selected_path") or [])
            )
            lines.extend(
                [
                    f"### {index}. {_safe_markdown(item.get('situation'), 240)}",
                    "",
                    f"- Relevance: `{float(item.get('score') or 0):.6f}`",
                    f"- Source: `{_safe_markdown(item.get('source_repository'), 160)}@{_safe_markdown(item.get('registry_commit'), 40)}`",
                    f"- Pack: `{_safe_markdown(item.get('pack_id'), 64)}`",
                    f"- Best-known path: {path}",
                    "",
                ]
            )
    elif summary.get("lane_status") == "NOT_RUN":
        lines.extend(
            [
                "CML retrieval did not run because the initial exact-head gate failed.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "No publishable accepted CML memory met the deterministic relevance threshold.",
                "",
            ]
        )
    lines.extend(
        [
            "CML evidence is advisory context only. It cannot approve, execute, deliver, or merge this change.",
            "",
        ]
    )
    return "\n".join(lines)


def render_scorecard(card: Mapping[str, Any]) -> str:
    rendered = core.markdown(dict(card))
    summary = card.get("causal_memory")
    if not isinstance(summary, dict):
        return rendered
    section = render_cml_section(summary)
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
    if lane_status not in {"PASS", "INCOMPLETE", "NOT_RUN"}:
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


def stamp_tool_version(output: Path) -> None:
    manifest_path = output / "manifest.json"
    manifest = base.read_json(manifest_path, dict)
    if manifest is None:
        raise core.InputError("Generated manifest is missing")
    tool = dict(manifest.get("tool") or {})
    tool.update({"name": "ls-exact-head-audit", "version": TOOL_VERSION})
    manifest["tool"] = tool
    core.write_json(manifest_path, manifest)


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
        client = target_client(
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
        stamp_tool_version(output)
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
