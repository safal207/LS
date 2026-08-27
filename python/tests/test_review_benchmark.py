from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import review_benchmark as benchmark  # noqa: E402

EVIDENCE_SHA = "a" * 64
PROMPT_SHA = "b" * 64


def case(*, status: str = "FROZEN") -> dict:
    return {
        "schema_version": "ls.review_benchmark_case.v0.1",
        "case_id": "pr796-final-v0.1",
        "status": status,
        "evidence_manifest_path": (
            "benchmarks/exact-head/pr796-final-calibration-v0.1.json"
        ),
        "evidence_sha256": EVIDENCE_SHA if status == "FROZEN" else None,
        "coordinates": {
            "repository": "safal207/LS",
            "pr_number": 796,
            "base_sha": "c" * 40,
            "head_sha": "d" * 40,
            "changed_file_count": 19,
        },
        "prompt_path": "benchmarks/review-comparison/prompts/blind-review-v0.1.md",
        "lanes": [
            {
                "lane": "CLAUDE",
                "visibility": "FROZEN_BUNDLE_ONLY",
                "must_not_receive": ["LS report"],
            },
            {
                "lane": "LS",
                "visibility": "FROZEN_BUNDLE_ONLY",
                "must_not_receive": ["Claude report"],
            },
        ],
    }


def report(
    lane: str,
    finding_id: str,
    *,
    classification: str = "CONFIRMED_DEFECT",
    reproduction_status: str = "STATICALLY_PROVEN",
    proposed_edge: bool = False,
) -> dict:
    findings = [
        {
            "finding_id": finding_id,
            "title": "Restart state requires reconciliation",
            "severity": "high",
            "classification": classification,
            "confidence": 0.9,
            "claim": "A claimed execution can become in doubt after restart.",
            "evidence": [
                {
                    "path": "tools/validate_durable_approval_v0_2.py",
                    "line_start": 10,
                    "line_end": 12,
                    "observation": "The reducer exposes an IN_DOUBT execution state.",
                }
            ],
            "failure_scenario": (
                "A restart occurs after claim and before durable effect evidence."
            ),
            "reproduction": {
                "status": reproduction_status,
                "steps": [
                    "Apply UserApproved",
                    "Apply ExecutionClaimed",
                    "Restart runtime",
                ],
            },
            "recommendation": "Require explicit reconciliation evidence.",
            "uncertainties": [],
        }
    ]
    structured_analysis = {
        "artifact_nodes": [],
        "relations": [],
        "probes": [],
    }
    if lane == "LS":
        structured_analysis = {
            "artifact_nodes": [
                {
                    "node_id": "runtime",
                    "kind": "runtime",
                    "path": "tools/validate_durable_approval_v0_2.py",
                    "observation": "Reducer implements restart transitions.",
                },
                {
                    "node_id": "fixture",
                    "kind": "fixture",
                    "path": "fixtures/durable-approval/runtime_restart.json",
                    "observation": "Fixture exercises the restart path.",
                },
            ],
            "relations": [
                {
                    "relation_id": "runtime-fixture",
                    "source_node": "runtime",
                    "target_node": "fixture",
                    "relation_type": "PROVEN_BY",
                    "status": "OBSERVED",
                    "evidence_finding_ids": [finding_id],
                }
            ],
            "probes": [
                {
                    "probe_id": "restart-probe",
                    "kind": "deterministic_replay",
                    "status": "PASSED",
                    "command": "python tools/test_durable_approval.py",
                    "observation": "Restart transitions to IN_DOUBT.",
                    "evidence_finding_ids": [finding_id],
                }
            ],
        }
    proposed_edges = []
    if proposed_edge:
        proposed_edges = [
            {
                "proposal_id": f"{lane}-EDGE-001",
                "source_node": "runtime",
                "target_node": "fixture",
                "relation_type": "PROVEN_BY",
                "provenance_finding_ids": [finding_id],
                "confidence": 0.8,
                "status": "UNTRUSTED",
            }
        ]
    return {
        "schema_version": "ls.review_benchmark_report.v0.1",
        "case_id": "pr796-final-v0.1",
        "lane": lane,
        "evidence_sha256": EVIDENCE_SHA,
        "reviewer": {
            "system": "Claude" if lane == "CLAUDE" else "Living Evidence Graph",
            "model": "test-model",
            "version": "test-version",
        },
        "prompt_sha256": PROMPT_SHA,
        "verdict": "COMMENT",
        "findings": findings,
        "structured_analysis": structured_analysis,
        "proposed_edges": proposed_edges,
        "limitations": [],
    }


def adjudication(
    *,
    decision: str = "TRUE_STATICALLY_PROVEN",
    ground_truth_complete: bool = True,
    with_edge: bool = False,
) -> dict:
    edge_decisions = []
    if with_edge:
        edge_decisions = [
            {
                "lane": "LS",
                "proposal_id": "LS-EDGE-001",
                "decision": "APPROVE_PROPOSAL",
                "rationale": "Evidence supports the proposal, but promotion is separate.",
            }
        ]
    return {
        "schema_version": "ls.review_benchmark_adjudication.v0.1",
        "case_id": "pr796-final-v0.1",
        "evidence_sha256": EVIDENCE_SHA,
        "adjudicator": "human",
        "ground_truth_complete": ground_truth_complete,
        "known_truth": (
            [
                {
                    "ground_truth_id": "GT-001",
                    "title": "Restart requires reconciliation",
                    "severity": "high",
                    "matched_cluster_ids": ["C001"],
                }
            ]
            if ground_truth_complete
            else []
        ),
        "clusters": [
            {
                "cluster_id": "C001",
                "canonical_claim": (
                    "Execution becomes IN_DOUBT after restart without effect evidence."
                ),
                "members": [
                    {
                        "lane": "CLAUDE",
                        "finding_id": "CLAUDE-001",
                        "attribution_correct": True,
                    },
                    {
                        "lane": "LS",
                        "finding_id": "LS-001",
                        "attribution_correct": True,
                    },
                ],
                "decision": decision,
                "adjudicated_severity": (
                    "high" if decision in benchmark.TRUE_DECISIONS else "none"
                ),
                "rationale": "The frozen runtime and fixture support the decision.",
            }
        ],
        "edge_decisions": edge_decisions,
    }


class ReviewBenchmarkTests(unittest.TestCase):
    def test_seal_is_deterministic_and_detects_report_mutation(self) -> None:
        frozen_case = case()
        claude_report = report("CLAUDE", "CLAUDE-001")
        first = benchmark.seal_report(frozen_case, claude_report)
        second = benchmark.seal_report(frozen_case, copy.deepcopy(claude_report))
        self.assertEqual(first, second)

        changed = copy.deepcopy(claude_report)
        changed["findings"][0]["claim"] = "The claim was edited after sealing."
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "changed after it was sealed",
        ):
            benchmark.validate_seal(first, changed)

    def test_forged_semantic_seal_field_is_rejected(self) -> None:
        frozen_case = case()
        claude_report = report("CLAUDE", "CLAUDE-001")
        seal = benchmark.seal_report(frozen_case, claude_report)
        forged = copy.deepcopy(seal)
        forged["prompt_sha256"] = "f" * 64
        unsigned = {key: value for key, value in forged.items() if key != "seal_sha256"}
        forged["seal_sha256"] = benchmark.sha256_json(unsigned)
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "prompt_sha256 does not match",
        ):
            benchmark.validate_seal(forged, claude_report)

    def test_score_emits_precision_recall_reproduction_and_categories(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report("CLAUDE", "CLAUDE-001"),
            "LS": report("LS", "LS-001"),
        }
        seals = {
            lane: benchmark.seal_report(frozen_case, value)
            for lane, value in reports.items()
        }
        scorecard = benchmark.score(
            frozen_case,
            reports,
            seals,
            adjudication(),
        )

        self.assertEqual(scorecard["true_cluster_count"], 1)
        self.assertEqual(scorecard["overlap_true_cluster_count"], 1)
        self.assertEqual(scorecard["cluster_analysis"][0]["category"], "BOTH_TRUE")
        for lane in ("CLAUDE", "LS"):
            stats = scorecard["lanes"][lane]
            self.assertEqual(stats["precision"], 1.0)
            self.assertEqual(stats["recall"], 1.0)
            self.assertEqual(stats["reproduction_rate"], 1.0)
            self.assertEqual(stats["attribution_accuracy"], 1.0)
            self.assertEqual(stats["severity_accuracy"], 1.0)
        self.assertRegex(scorecard["scorecard_sha256"], r"^[0-9a-f]{64}$")

    def test_recall_is_null_when_ground_truth_is_not_complete(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report("CLAUDE", "CLAUDE-001"),
            "LS": report("LS", "LS-001"),
        }
        seals = {
            lane: benchmark.seal_report(frozen_case, value)
            for lane, value in reports.items()
        }
        scorecard = benchmark.score(
            frozen_case,
            reports,
            seals,
            adjudication(ground_truth_complete=False),
        )
        self.assertIsNone(scorecard["lanes"]["CLAUDE"]["recall"])
        self.assertIsNone(scorecard["lanes"]["LS"]["recall"])

    def test_escalation_quality_is_scored(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report(
                "CLAUDE",
                "CLAUDE-001",
                classification="DESIGN_QUESTION",
                reproduction_status="NOT_AVAILABLE",
            ),
            "LS": report(
                "LS",
                "LS-001",
                classification="UNSUPPORTED_HYPOTHESIS",
                reproduction_status="NOT_AVAILABLE",
            ),
        }
        seals = {
            lane: benchmark.seal_report(frozen_case, value)
            for lane, value in reports.items()
        }
        scorecard = benchmark.score(
            frozen_case,
            reports,
            seals,
            adjudication(
                decision="REQUIRES_HUMAN_DECISION",
                ground_truth_complete=False,
            ),
        )
        self.assertEqual(
            scorecard["cluster_analysis"][0]["category"],
            "HUMAN_DECISION_REQUIRED",
        )
        self.assertEqual(scorecard["lanes"]["CLAUDE"]["escalation_quality"], 1.0)
        self.assertEqual(scorecard["lanes"]["LS"]["escalation_quality"], 1.0)

    def test_ls_report_requires_structured_graph_and_probe_evidence(self) -> None:
        broken = report("LS", "LS-001")
        broken["structured_analysis"]["relations"] = []
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "LS report requires non-empty",
        ):
            benchmark.validate_report(broken, case())

    def test_proposed_edges_remain_untrusted_and_require_adjudication(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report("CLAUDE", "CLAUDE-001"),
            "LS": report("LS", "LS-001", proposed_edge=True),
        }
        seals = {
            lane: benchmark.seal_report(frozen_case, value)
            for lane, value in reports.items()
        }
        scorecard = benchmark.score(
            frozen_case,
            reports,
            seals,
            adjudication(with_edge=True),
        )
        summary = scorecard["edge_proposal_summary"]["LS"]
        self.assertEqual(summary["proposed"], 1)
        self.assertEqual(summary["approved_proposals"], 1)
        self.assertEqual(summary["trusted_graph_mutations"], 0)

    def test_every_edge_proposal_must_be_adjudicated(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report("CLAUDE", "CLAUDE-001"),
            "LS": report("LS", "LS-001", proposed_edge=True),
        }
        incomplete = adjudication(with_edge=False)
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "every proposed edge must be adjudicated",
        ):
            benchmark.validate_adjudication(incomplete, frozen_case, reports)

    def test_prepared_case_cannot_accept_reports(self) -> None:
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "until the case is FROZEN",
        ):
            benchmark.validate_report(
                report("CLAUDE", "CLAUDE-001"),
                case(status="PREPARED"),
            )

    def test_every_finding_must_be_adjudicated_exactly_once(self) -> None:
        frozen_case = case()
        reports = {
            "CLAUDE": report("CLAUDE", "CLAUDE-001"),
            "LS": report("LS", "LS-001"),
        }
        incomplete = adjudication()
        incomplete["clusters"][0]["members"].pop()
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "every finding must be adjudicated",
        ):
            benchmark.validate_adjudication(incomplete, frozen_case, reports)

    def test_repository_evidence_paths_cannot_escape(self) -> None:
        broken = report("LS", "LS-001")
        broken["findings"][0]["evidence"][0]["path"] = "../secret.txt"
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "inside the repository",
        ):
            benchmark.validate_report(broken, case())

    def test_schema_required_finding_field_cannot_be_omitted(self) -> None:
        broken = report("CLAUDE", "CLAUDE-001")
        broken["findings"][0].pop("recommendation")
        with self.assertRaisesRegex(
            benchmark.BenchmarkError,
            "keys mismatch",
        ):
            benchmark.validate_report(broken, case())


if __name__ == "__main__":
    unittest.main()
