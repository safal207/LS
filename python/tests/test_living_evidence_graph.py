from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_model_review.evidence_graph import (  # noqa: E402
    ArtifactKind,
    EvidenceSignal,
    EvidenceTier,
    HarmonizationDecision,
    Observation,
    Relation,
    RelationHint,
    SignalPhase,
    build_artifact_graph,
    node_id_for_path,
)
from multi_model_review.evidence_probes import (  # noqa: E402
    load_pattern_specimen,
    probe_additional_properties_parity,
    probe_digest_pattern_parity,
    probe_timezone_comparison_safety,
    probe_unknown_property_parity,
    run_pattern_specimen,
)

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
OBSERVED_AT = "2026-07-06T20:56:29Z"


class LivingEvidenceGraphTests(unittest.TestCase):
    def test_builds_only_explicit_typed_relations(self) -> None:
        paths = [
            "fixtures/runtime/a/envelope.schema.json",
            "fixtures/runtime/b/event.schema.json",
            "tools/validate_a.py",
            "tools/validate_b.py",
            "python/tests/test_a.py",
            "spec/a-conformance.md",
            ".github/workflows/a.yml",
        ]
        graph = build_artifact_graph(
            paths,
            repository="safal207/LS",
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            observed_at=OBSERVED_AT,
            branch="feat/living-evidence-graph-799",
            relation_hints=[
                RelationHint(
                    "tools/validate_a.py",
                    Relation.IMPLEMENTS,
                    "fixtures/runtime/a/envelope.schema.json",
                    "explicit review-unit mapping",
                ),
                RelationHint(
                    "python/tests/test_a.py",
                    Relation.TESTS,
                    "tools/validate_a.py",
                    "test imports validator",
                ),
                RelationHint(
                    "spec/a-conformance.md",
                    Relation.DOCUMENTS,
                    "tools/validate_a.py",
                    "spec names validator CLI",
                ),
                RelationHint(
                    ".github/workflows/a.yml",
                    Relation.INVOKES,
                    "python/tests/test_a.py",
                    "workflow command names test",
                ),
            ],
        )
        kinds = {node.kind for node in graph.nodes}
        self.assertTrue(
            {
                ArtifactKind.JSON_SCHEMA,
                ArtifactKind.VALIDATOR,
                ArtifactKind.TEST,
                ArtifactKind.SPECIFICATION,
                ArtifactKind.WORKFLOW,
            }
            <= kinds
        )
        self.assertEqual(len(graph.edges), 4)
        edge_pairs = {(edge.source, edge.relation, edge.target) for edge in graph.edges}
        self.assertNotIn(
            (
                "tools::validate_a.py",
                Relation.IMPLEMENTS,
                "fixtures::runtime::b::event.schema.json",
            ),
            edge_pairs,
        )
        self.assertNotIn(
            (
                "tools::validate_b.py",
                Relation.IMPLEMENTS,
                "fixtures::runtime::a::envelope.schema.json",
            ),
            edge_pairs,
        )
        self.assertIn("IMPLEMENTS", json.dumps(graph.to_dict(), sort_keys=True))

    def test_relation_hint_rejects_unknown_artifact(self) -> None:
        with self.assertRaisesRegex(ValueError, "relation target is not in graph"):
            build_artifact_graph(
                ["tools/validate_a.py"],
                repository="safal207/LS",
                base_sha=BASE_SHA,
                head_sha=HEAD_SHA,
                observed_at=OBSERVED_AT,
                relation_hints=[
                    RelationHint(
                        "tools/validate_a.py",
                        Relation.IMPLEMENTS,
                        "missing.schema.json",
                        "invalid mapping",
                    )
                ],
            )

    def test_temporal_context_rejects_naive_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            build_artifact_graph(
                ["tools/validate_case.py"],
                repository="safal207/LS",
                base_sha=BASE_SHA,
                head_sha=HEAD_SHA,
                observed_at="2026-07-06T20:56:29",
            )

    def _signal(self, *, use_paths: bool = False) -> EvidenceSignal:
        primary = "tools/validate_case.py" if use_paths else "tools::validate_case.py"
        related = (
            ["fixtures/runtime/envelope.schema.json"]
            if use_paths
            else ["fixtures::runtime::envelope.schema.json"]
        )
        return EvidenceSignal(
            signal_id="closed-object-parity",
            title="Runtime accepts a schema-rejected field",
            tier=EvidenceTier.T1_STRUCTURAL,
            primary_artifact=primary,
            related_artifacts=related,
            violated_relation=Relation.IMPLEMENTS,
        )

    def _observation(self) -> Observation:
        return Observation(
            observation_id="obs-1",
            method="structural probe",
            observer="living-evidence-probe",
            evidence="schema and validator disagree",
            repeatable=True,
            observed_at=OBSERVED_AT,
        )

    def test_add_signal_accepts_paths_and_normalizes_to_node_ids(self) -> None:
        graph = build_artifact_graph(
            ["tools/validate_case.py", "fixtures/runtime/envelope.schema.json"],
            repository="safal207/LS",
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            observed_at=OBSERVED_AT,
        )
        signal = self._signal(use_paths=True)
        graph.add_signal(signal)
        self.assertEqual(signal.primary_artifact, node_id_for_path("tools/validate_case.py"))
        self.assertEqual(
            signal.related_artifacts,
            [node_id_for_path("fixtures/runtime/envelope.schema.json")],
        )

    def test_phase_sequence_is_strictly_linear(self) -> None:
        signal = self._signal()
        signal.add_observation(self._observation())
        with self.assertRaisesRegex(ValueError, "LATENT -> REPRODUCED"):
            signal.advance(SignalPhase.REPRODUCED, "obs-1", "2026-07-06T20:56:30Z")

    def test_transition_time_is_aware_and_monotonic(self) -> None:
        signal = self._signal()
        signal.add_observation(self._observation())
        signal.advance(SignalPhase.UNFOLDED, "obs-1", "2026-07-06T20:56:31Z")
        with self.assertRaisesRegex(ValueError, "time-monotonic"):
            signal.advance(SignalPhase.REPRODUCED, "obs-1", "2026-07-06T20:56:30Z")
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            signal.advance(SignalPhase.REPRODUCED, "obs-1", "2026-07-06T20:56:32")

    def test_transition_cannot_precede_observation(self) -> None:
        signal = self._signal()
        signal.add_observation(self._observation())
        with self.assertRaisesRegex(ValueError, "cannot precede"):
            signal.advance(SignalPhase.UNFOLDED, "obs-1", "2026-07-06T20:56:28Z")

    def test_harmonized_transition_requires_decision(self) -> None:
        signal = self._signal()
        signal.add_observation(self._observation())
        signal.advance(SignalPhase.UNFOLDED, "obs-1", "2026-07-06T20:56:30Z")
        signal.advance(SignalPhase.REPRODUCED, "obs-1", "2026-07-06T20:56:31Z")
        signal.advance(SignalPhase.CONFIRMED, "obs-1", "2026-07-06T20:56:32Z")
        with self.assertRaisesRegex(ValueError, "harmonization decision"):
            signal.advance(SignalPhase.HARMONIZED, "obs-1", "2026-07-06T20:56:33Z")
        signal.record_harmonization(
            HarmonizationDecision(
                decision_id="harm-1",
                observation_id="obs-1",
                resolution="schema and runtime converge on closed-object rejection",
                evidence="the same mutation is rejected by both contracts",
                decided_at="2026-07-06T20:56:33Z",
            )
        )
        signal.advance(SignalPhase.HARMONIZED, "obs-1", "2026-07-06T20:56:34Z")
        self.assertEqual(signal.phase, SignalPhase.HARMONIZED)

    def test_signal_lifecycle_preserves_regression_memory(self) -> None:
        graph = build_artifact_graph(
            ["tools/validate_case.py", "fixtures/runtime/envelope.schema.json"],
            repository="safal207/LS",
            base_sha=BASE_SHA,
            head_sha=HEAD_SHA,
            observed_at=OBSERVED_AT,
            relation_hints=[
                RelationHint(
                    "tools/validate_case.py",
                    Relation.IMPLEMENTS,
                    "fixtures/runtime/envelope.schema.json",
                    "explicit review-unit mapping",
                )
            ],
        )
        signal = self._signal()
        signal.add_observation(self._observation())
        signal.advance(SignalPhase.UNFOLDED, "obs-1", "2026-07-06T20:56:30Z")
        signal.advance(SignalPhase.REPRODUCED, "obs-1", "2026-07-06T20:56:31Z")
        signal.advance(SignalPhase.CONFIRMED, "obs-1", "2026-07-06T20:56:32Z")
        signal.record_harmonization(
            HarmonizationDecision(
                decision_id="harm-1",
                observation_id="obs-1",
                resolution="runtime and schema now reject the same counterexample",
                evidence="verified exact-head parity",
                decided_at="2026-07-06T20:56:33Z",
            )
        )
        signal.advance(SignalPhase.HARMONIZED, "obs-1", "2026-07-06T20:56:34Z")
        signal.advance(SignalPhase.BLOCKING, "obs-1", "2026-07-06T20:56:35Z")
        signal.advance(SignalPhase.FIXED, "obs-1", "2026-07-06T20:56:36Z")
        signal.advance(SignalPhase.VERIFIED, "obs-1", "2026-07-06T20:56:37Z")
        signal.advance(SignalPhase.DORMANT, "obs-1", "2026-07-06T20:56:38Z")
        signal.preserve_regression_memory("schema_runtime_closed_object_parity")
        graph.add_signal(signal)
        self.assertEqual(graph.signals[0].phase, SignalPhase.DORMANT)
        self.assertEqual(graph.signals[0].regression_rule, "schema_runtime_closed_object_parity")
        self.assertIsNotNone(graph.signals[0].harmonization)

    def test_shape_probe_ignores_comments_and_docstrings(self) -> None:
        schema = {"type": "object", "additionalProperties": False}
        source = '''
"""The validator should reject an unexpected key and enforce additionalProperties."""

def validate(value):
    # Future implementation may compare value.keys() - allowed.
    return True
'''
        finding = probe_additional_properties_parity(
            schema=schema,
            schema_path="schema.json",
            validator_source=source,
            validator_path="validate.py",
        )
        self.assertIsNotNone(finding)

    def test_shape_probe_accepts_executable_unknown_key_guard(self) -> None:
        schema = {"type": "object", "additionalProperties": False}
        source = '''
def validate(value):
    unknown = value.keys() - {"known"}
    if unknown:
        raise ValueError("unexpected key")
'''
        finding = probe_additional_properties_parity(
            schema=schema,
            schema_path="schema.json",
            validator_source=source,
            validator_path="validate.py",
        )
        self.assertIsNone(finding)

    def test_granular_shape_probe_ignores_unrelated_function_guard(self) -> None:
        schema = {"type": "object", "additionalProperties": False}
        source = '''
def validate_other(value):
    unknown = value.keys() - {"known"}
    if unknown:
        raise ValueError("unexpected key")

def validate_envelope(value):
    return True
'''
        finding = probe_unknown_property_parity(
            schema=schema,
            schema_path="envelope.schema.json",
            validator_source=source,
            validator_path="validate.py",
            category="envelope",
            function_name="validate_envelope",
        )
        self.assertIsNotNone(finding)

    def test_digest_probe_recurses_into_conditional_branches(self) -> None:
        schema = {
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "action_digest": {
                            "type": "string",
                            "pattern": "^sha256:[A-Za-z0-9._-]+$",
                        }
                    },
                }
            ]
        }
        finding = probe_digest_pattern_parity(
            schema=schema,
            schema_path="envelope.schema.json",
            validator_source="value.startswith('sha256:')",
            validator_path="validate.py",
        )
        self.assertIsNotNone(finding)

    def test_digest_probe_does_not_use_unrelated_fullmatch(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "action_digest": {
                    "type": "string",
                    "pattern": "^sha256:[A-Za-z0-9._-]+$",
                }
            },
        }
        source = '''
import re

def validate_digest(value):
    return value.startswith("sha256:")

def validate_other(other):
    return re.fullmatch(r"^sha256:[A-Za-z0-9._-]+$", other) is not None
'''
        finding = probe_digest_pattern_parity(
            schema=schema,
            schema_path="envelope.schema.json",
            validator_source=source,
            validator_path="validate.py",
        )
        self.assertIsNotNone(finding)

    def test_digest_probe_accepts_matching_compiled_regex(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "action_digest": {
                    "type": "string",
                    "pattern": "^sha256:[A-Za-z0-9._-]+$",
                }
            },
        }
        source = '''
import re
DIGEST = re.compile(r"^sha256:[A-Za-z0-9._-]+$")

def validate(value):
    if not value.startswith("sha256:"):
        return False
    return DIGEST.fullmatch(value) is not None
'''
        finding = probe_digest_pattern_parity(
            schema=schema,
            schema_path="envelope.schema.json",
            validator_source=source,
            validator_path="validate.py",
        )
        self.assertIsNone(finding)

    def test_timezone_probe_scopes_parse_and_compare_to_same_chain(self) -> None:
        unrelated = """
from datetime import datetime

def parse_only(value):
    return datetime.fromisoformat(value)

def compare_unrelated(left, right):
    return left < right
"""
        self.assertIsNone(probe_timezone_comparison_safety(source=unrelated, path="unrelated.py"))

        risky = """
from datetime import datetime

def parse_timestamp(value):
    return datetime.fromisoformat(value)

def compare_events(left, right):
    parsed_left = parse_timestamp(left)
    parsed_right = parse_timestamp(right)
    return parsed_left < parsed_right
"""
        self.assertIsNotNone(probe_timezone_comparison_safety(source=risky, path="risky.py"))

        guarded = """
from datetime import datetime

def parse_timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed

def compare_events(left, right):
    parsed_left = parse_timestamp(left)
    parsed_right = parse_timestamp(right)
    return parsed_left < parsed_right
"""
        self.assertIsNone(probe_timezone_comparison_safety(source=guarded, path="guarded.py"))

    def test_timezone_guard_must_match_parsed_variable(self) -> None:
        source = """
from datetime import datetime, timezone

class Context:
    tzinfo = timezone.utc

def parse_timestamp(value, context):
    parsed = datetime.fromisoformat(value)
    if context.tzinfo is None:
        raise ValueError("context timezone required")
    return parsed

def compare_events(left, right, context):
    parsed_left = parse_timestamp(left, context)
    parsed_right = parse_timestamp(right, context)
    return parsed_left < parsed_right
"""
        finding = probe_timezone_comparison_safety(source=source, path="wrong_guard.py")
        self.assertIsNotNone(finding)

    def test_timezone_access_without_enforcement_is_not_a_guard(self) -> None:
        source = """
from datetime import datetime

def parse_timestamp(value):
    parsed = datetime.fromisoformat(value)
    print(parsed.tzinfo)
    return parsed

def compare_events(left, right):
    parsed_left = parse_timestamp(left)
    parsed_right = parse_timestamp(right)
    return parsed_left < parsed_right
"""
        finding = probe_timezone_comparison_safety(source=source, path="logging_only.py")
        self.assertIsNotNone(finding)

    def test_synthetic_pattern_specimen_recognizes_expected_signatures(self) -> None:
        specimen = load_pattern_specimen(
            ROOT / "python/tests/fixtures/living_evidence_pattern_specimen/specimen.json"
        )
        findings = run_pattern_specimen(specimen)
        ids = {finding.finding_id for finding in findings}
        self.assertEqual(ids, set(specimen["expected_signature_ids"]))
        self.assertTrue(all(finding.counterexample_recipe for finding in findings))
        self.assertTrue(all(finding.tier == EvidenceTier.T1_STRUCTURAL for finding in findings))


if __name__ == "__main__":
    unittest.main()
