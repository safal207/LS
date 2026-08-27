#!/usr/bin/env python3
"""CLI for provider-neutral, exact-head-bound LS PR review."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from multi_model_review import (
    CatalogModel,
    OpenRouterClient,
    ResolvedModel,
    ReviewProviderClient,
    ReviewRuntimeError,
    aggregate_reviews,
    bind_provider_routes,
    build_prompts,
    build_provider_client,
    changed_files_from_diff,
    classify_risk,
    extract_json_object,
    findings_overlap,
    load_config,
    load_provider_config,
    model_is_active,
    policy_decision,
    redact_diff,
    render_markdown,
    resolve_models,
    run_review,
    validate_review_payload,
    validate_sha,
    write_outputs,
)

__all__ = [
    "CatalogModel",
    "OpenRouterClient",
    "ResolvedModel",
    "ReviewProviderClient",
    "ReviewRuntimeError",
    "aggregate_reviews",
    "bind_provider_routes",
    "build_prompts",
    "build_provider_client",
    "changed_files_from_diff",
    "classify_risk",
    "extract_json_object",
    "findings_overlap",
    "load_config",
    "load_provider_config",
    "main",
    "model_is_active",
    "parse_args",
    "policy_decision",
    "redact_diff",
    "render_markdown",
    "resolve_models",
    "run_review",
    "validate_review_payload",
    "validate_sha",
    "write_outputs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run exact-head multi-model PR review against a saved diff.")
    parser.add_argument("--config", type=Path, default=Path(".github/ai-review-models.json"))
    parser.add_argument(
        "--provider-config",
        type=Path,
        default=Path(".github/ai-review-provider-routes.json"),
    )
    parser.add_argument("--diff-file", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--mode", choices=("advisory", "strict"), default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        roster = load_config(args.config)
        provider_config = load_provider_config(args.provider_config)
        config = bind_provider_routes(roster, provider_config)
        base_sha = validate_sha(args.base_sha, "base_sha")
        head_sha = validate_sha(args.head_sha, "head_sha")
        if args.pr_number <= 0:
            raise ReviewRuntimeError("pr_number must be positive")
        mode = args.mode or str(config["defaults"]["mode"])
        if mode not in {"advisory", "strict"}:
            raise ReviewRuntimeError("mode must be advisory or strict")
        try:
            diff_text = args.diff_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReviewRuntimeError(f"cannot read diff file: {exc}") from exc

        provider = config["provider"]
        credential = os.environ.get(provider["credential_env"], "").strip()
        client: ReviewProviderClient | None = None
        if credential:
            defaults = config["defaults"]
            client = build_provider_client(
                provider,
                credential=credential,
                timeout_seconds=defaults["request_timeout_seconds"],
                max_attempts=defaults["max_attempts"],
            )
        artifact = run_review(
            config=config,
            client=client,
            repository=args.repository,
            pr_number=args.pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            diff_text=diff_text,
            mode=mode,
        )
        write_outputs(artifact, args.output, args.markdown_output)
        print(json.dumps({"status": artifact["status"], "verdict": artifact["aggregate"]["verdict"], "policy": artifact["policy"]}))
        return 2 if artifact["policy"]["enforced_block"] else 0
    except (ReviewRuntimeError, OSError, ValueError, TypeError) as exc:
        print(f"multi-model review error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
