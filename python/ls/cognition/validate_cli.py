#!/usr/bin/env python3
"""ls-validate — CLI for the LS collective answer validation pipeline.

Usage examples:

    # Basic validation from a JSON file
    python -m ls.cognition.validate_cli candidates.json

    # With governance (reputation, clustering, coalitions)
    python -m ls.cognition.validate_cli candidates.json --governance

    # With LTP signing
    python -m ls.cognition.validate_cli candidates.json --sign

    # Full pipeline: governance + signing + Lifetra trace
    python -m ls.cognition.validate_cli candidates.json --governance --sign --trace

    # Read from stdin
    echo '{"task_prompt":"...", "candidates":[...]}' | python -m ls.cognition.validate_cli -

Expected JSON format:

    {
        "task_prompt": "Which caching strategy should we use?",
        "candidates": [
            {
                "agent_id": "agent-alpha",
                "answer_text": "Use LRU cache with 300s TTL.",
                "relevance": 0.90,
                "thread_relevance": 0.88,
                "hallucination_risk": 0.05,
                "supports": ["agent-beta"],
                "contradicts": []
            },
            ...
        ]
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_payload(source: str) -> dict[str, Any]:
    """Load and parse JSON from a file path or stdin (when source is '-')."""
    if source == "-":
        text = sys.stdin.read()
    else:
        text = Path(source).read_text(encoding="utf-8")
    return json.loads(text)


def _build_candidates(raw: dict[str, Any]) -> tuple[str, list[Any]]:
    from ls.cognition.collective_answer_validator import CandidateAnswer  # noqa: PLC0415

    task_prompt = raw["task_prompt"]
    candidates = []
    for entry in raw["candidates"]:
        candidates.append(
            CandidateAnswer(
                agent_id=entry["agent_id"],
                answer_text=entry["answer_text"],
                relevance=float(entry.get("relevance", 0.7)),
                thread_relevance=float(entry.get("thread_relevance", 0.7)),
                hallucination_risk=float(entry.get("hallucination_risk", 0.1)),
                supports=list(entry.get("supports", [])),
                contradicts=list(entry.get("contradicts", [])),
            )
        )
    return task_prompt, candidates


def _build_validator(
    *,
    governance: bool = False,
    trace: bool = False,
    escalation: str = "null",
) -> Any:
    from ls.cognition.collective_answer_validator import CollectiveAnswerValidator  # noqa: PLC0415

    trace_backend = None
    governance_engine = None
    escalation_handler = None

    if trace:
        from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter  # noqa: PLC0415

        adapter = LifetraValidationAdapter()
        # If lifetra_py is not installed, adapter will return None traces
        # (graceful fallback) — we still try.
        trace_backend = adapter

    if governance:
        from ls.cognition.validation_governance import (  # noqa: PLC0415
            InMemoryValidationHistoryStore,
            ValidationGovernanceEngine,
        )

        store = InMemoryValidationHistoryStore()
        governance_engine = ValidationGovernanceEngine(history_store=store)

    if escalation == "logging":
        from ls.cognition.validation_escalation import LoggingEscalationHandler  # noqa: PLC0415

        escalation_handler = LoggingEscalationHandler()
    elif escalation == "raising":
        from ls.cognition.validation_escalation import RaisingEscalationHandler  # noqa: PLC0415

        escalation_handler = RaisingEscalationHandler()

    return CollectiveAnswerValidator(
        trace_backend=trace_backend,
        governance_engine=governance_engine,
        escalation_handler=escalation_handler,
    )


def _format_result(result: Any, *, sign: bool = False) -> dict[str, Any]:
    output: dict[str, Any] = {
        "winner_agent_id": result.winner_agent_id,
        "consensus_status": result.consensus_status,
        "consensus_summary": result.consensus_summary,
        "global_risk_flags": result.global_risk_flags,
        "ranked_candidates": [
            {
                "agent_id": vc.agent_id,
                "accepted": vc.accepted,
                "score": round(vc.score, 4),
                "reasons": vc.reasons,
                "risk_flags": vc.risk_flags,
            }
            for vc in result.ranked_candidates
        ],
    }

    if result.trace_artifact is not None:
        artifact = result.trace_artifact
        trace_info: dict[str, Any] = {
            "trace_id": artifact.trace_id,
            "backend": artifact.backend,
            "node_count": artifact.node_count,
            "edge_count": artifact.edge_count,
        }

        if sign:
            try:
                from ls.cognition.ltp_trace_signer import (  # noqa: PLC0415
                    generate_key_pair,
                    sign_trace_artifact,
                    verify_trace_artifact,
                )

                priv, pub = generate_key_pair()
                signed = sign_trace_artifact(artifact, priv)
                verified = verify_trace_artifact(signed, pub)
                trace_info["signed"] = True
                trace_info["verified"] = verified
                trace_info["ltp_envelope"] = signed.metadata.get("ltp_envelope")
            except Exception as exc:  # noqa: BLE001
                trace_info["signed"] = False
                trace_info["sign_error"] = str(exc)

        output["trace"] = trace_info

    if result.governance_report is not None:
        report = result.governance_report
        output["governance"] = {
            "governed_winner_agent_id": report.governed_winner_agent_id,
            "review_required": report.review_required,
            "governance_flags": report.governance_flags,
            "escalation_recommendations": report.escalation_recommendations,
            "coalition_alerts": len(report.coalition_alerts),
            "paraphrase_clusters": len(report.paraphrase_clusters),
            "history_round_count": report.history_round_count,
        }

    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ls-validate",
        description="Run LS collective answer validation on a JSON payload.",
    )
    parser.add_argument(
        "input",
        help="Path to JSON file with candidates, or '-' for stdin.",
    )
    parser.add_argument(
        "--governance",
        action="store_true",
        help="Enable governance engine (reputation, coalitions, clustering).",
    )
    parser.add_argument(
        "--sign",
        action="store_true",
        help="Sign the trace artifact with a generated Ed25519 key pair.",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Attach a Lifetra trajectory trace (requires lifetra_py or uses graceful fallback).",
    )
    parser.add_argument(
        "--escalation",
        choices=["null", "logging", "raising"],
        default="null",
        help="Escalation handler when governance flags review_required (default: null).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: True).",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Compact JSON output (one line).",
    )

    args = parser.parse_args(argv)

    try:
        raw = _load_payload(args.input)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"Error loading input: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        task_prompt, candidates = _build_candidates(raw)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Error parsing candidates: {exc}", file=sys.stderr)
        sys.exit(1)

    from ls.cognition.collective_answer_validator import ValidationInput  # noqa: PLC0415

    validator = _build_validator(
        governance=args.governance,
        trace=args.trace,
        escalation=args.escalation,
    )
    payload = ValidationInput(task_prompt=task_prompt, candidates=candidates)

    try:
        result = validator.validate(payload)
    except Exception as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        sys.exit(2)

    output = _format_result(result, sign=args.sign)

    indent = None if args.compact else 2
    print(json.dumps(output, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
