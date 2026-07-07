from __future__ import annotations

from review_benchmark_v0_2_common import sha256_json

EVIDENCE = "f" * 64
PROMPT = "a" * 64


def case_value():
    return {
        "schema_version": "ls.review_benchmark_case.v0.2",
        "case_id": "case-v0.2",
        "status": "FROZEN",
        "evidence_manifest_path": "benchmarks/exact-head/case.json",
        "evidence_sha256": EVIDENCE,
        "coordinates": {
            "repository": "safal207/LS",
            "pr_number": 796,
            "base_sha": "1" * 40,
            "head_sha": "2" * 40,
            "changed_file_count": 19,
        },
        "prompt_path": "benchmarks/review-comparison/prompts/blind-review-v0.2.md",
        "lanes": [
            {
                "lane": "FRONTIER_MODEL",
                "visibility": "FROZEN_BUNDLE_ONLY",
                "must_not_receive": ["LS report"],
            },
            {
                "lane": "LS",
                "visibility": "FROZEN_BUNDLE_ONLY",
                "must_not_receive": ["frontier-model report"],
            },
        ],
    }


def binding_value(lane="FRONTIER_MODEL", **overrides):
    value = {
        "schema_version": "ls.review_benchmark_run_binding.v0.2",
        "case_id": "case-v0.2",
        "lane": lane,
        "evidence_sha256": EVIDENCE,
        "prompt_sha256": PROMPT,
        "run_id": f"run-{lane.lower()}",
        "executor": {
            "provider": "xAI" if lane == "FRONTIER_MODEL" else "LS",
            "model": "Grok 4.5" if lane == "FRONTIER_MODEL" else "LS graph runtime",
            "version": "2026-07-07",
            "channel": "WEB_UI" if lane == "FRONTIER_MODEL" else "LOCAL",
        },
        "provenance": {
            "level": "USER_ATTESTED",
            "issuer": "human_operator",
            "evidence": ["Executor identity recorded before model output."],
        },
        "nonce": ("b" if lane == "FRONTIER_MODEL" else "c") * 64,
    }
    value.update(overrides)
    return value


def finding(lane, suffix="001", classification="CONFIRMED_DEFECT"):
    prefix = "FM" if lane == "FRONTIER_MODEL" else "LS"
    return {
        "finding_id": f"{prefix}-{suffix}",
        "title": "Finding",
        "severity": "high",
        "classification": classification,
        "confidence": 0.9,
        "claim": "A testable claim.",
        "evidence": [
            {
                "path": "tools/example.py",
                "line_start": 1,
                "line_end": 2,
                "observation": "Observed evidence.",
            }
        ],
        "failure_scenario": "A concrete failure occurs.",
        "reproduction": {
            "status": "STATICALLY_PROVEN",
            "steps": ["Inspect the frozen bytes."],
        },
        "recommendation": "Correct the invariant.",
        "uncertainties": [],
    }


def report_value(lane, binding, findings=None):
    findings = list(findings or [])
    structured = {"artifact_nodes": [], "relations": [], "probes": []}
    if lane == "LS":
        ids = [item["finding_id"] for item in findings]
        structured = {
            "artifact_nodes": [
                {
                    "node_id": "n1",
                    "kind": "runtime",
                    "path": "tools/example.py",
                    "observation": "Runtime node.",
                },
                {
                    "node_id": "n2",
                    "kind": "test",
                    "path": "python/tests/test_example.py",
                    "observation": "Test node.",
                },
            ],
            "relations": [
                {
                    "relation_id": "r1",
                    "source_node": "n1",
                    "target_node": "n2",
                    "relation_type": "validated_by",
                    "status": "OBSERVED",
                    "evidence_finding_ids": ids,
                }
            ],
            "probes": [
                {
                    "probe_id": "p1",
                    "kind": "static",
                    "status": "PASSED",
                    "command": "python -m unittest",
                    "observation": "Probe completed.",
                    "evidence_finding_ids": ids,
                }
            ],
        }
    return {
        "schema_version": "ls.review_benchmark_report.v0.2",
        "case_id": "case-v0.2",
        "lane": lane,
        "evidence_sha256": EVIDENCE,
        "prompt_sha256": PROMPT,
        "run_binding_sha256": sha256_json(binding),
        "verdict": "REQUEST_CHANGES" if findings else "APPROVE",
        "findings": findings,
        "structured_analysis": structured,
        "proposed_edges": [],
        "limitations": [],
    }
