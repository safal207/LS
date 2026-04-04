# -*- coding: utf-8 -*-
"""Tests for multi_party_alignment — per-party state snapshot builder."""
from __future__ import annotations

try:
    from agent.multi_party_alignment import (
        MultiPartyAlignmentMetrics,
        build_multi_party_alignment_state,
    )
except ImportError:
    from modules.agent.multi_party_alignment import (
        MultiPartyAlignmentMetrics,
        build_multi_party_alignment_state,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_report(
    *,
    participants=None,
    hotspots=None,
    alignment_score=0.5,
    tension_score=0.3,
):
    return {
        "participants": participants or [],
        "pairwise_hotspots": hotspots or [],
        "alignment_score": alignment_score,
        "tension_score": tension_score,
    }


def _hotspot(participants, tension=0.5, alignment=0.4, mismatch_reasons=None):
    return {
        "participants": participants,
        "tension": tension,
        "alignment": alignment,
        "mismatch_reasons": mismatch_reasons or [],
        "agreement_reasons": [],
        "has_evidence": True,
    }


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------

def test_empty_report_returns_stable_schema():
    result = build_multi_party_alignment_state({})
    assert result["party_count"] == 0
    assert result["parties"] == []
    assert result["state_label"] in {"converging", "stable", "diverging", "escalating"}
    assert isinstance(result["alignment_convergence"], float)
    assert isinstance(result["adoption_coverage"], float)
    assert isinstance(result["state_description"], str)


def test_none_report_treated_as_empty():
    result = build_multi_party_alignment_state(None)  # type: ignore[arg-type]
    assert result["party_count"] == 0
    assert result["state_label"] == "stable"


def test_no_hotspots_two_participants():
    report = _make_report(
        participants=[
            {"participant_id": "human-1"},
            {"participant_id": "agent-1"},
        ],
        alignment_score=0.7,
        tension_score=0.2,
    )
    result = build_multi_party_alignment_state(report)
    assert result["party_count"] == 2
    assert result["state_label"] == "converging"
    assert result["dominant_tension_axis"] == ""
    for party in result["parties"]:
        assert party["hotspot_count"] == 0
        assert party["alignment_gap"] == 0.0


# ---------------------------------------------------------------------------
# Party extraction
# ---------------------------------------------------------------------------

def test_parties_extracted_from_participants():
    report = _make_report(
        participants=[
            {"participant_id": "alice"},
            {"participant_id": "bob"},
            {"participant_id": "carol"},
        ]
    )
    result = build_multi_party_alignment_state(report)
    ids = [p["party_id"] for p in result["parties"]]
    assert ids == ["alice", "bob", "carol"]


def test_parties_fallback_from_hotspots():
    report = {
        "pairwise_hotspots": [
            _hotspot(["x", "y"], tension=0.4),
            _hotspot(["y", "z"], tension=0.3),
        ],
        "alignment_score": 0.5,
        "tension_score": 0.35,
    }
    result = build_multi_party_alignment_state(report)
    ids = {p["party_id"] for p in result["parties"]}
    assert ids == {"x", "y", "z"}


def test_max_five_parties():
    participants = [{"participant_id": f"p{i}"} for i in range(10)]
    report = _make_report(participants=participants)
    result = build_multi_party_alignment_state(report)
    assert result["party_count"] <= 5


def test_duplicate_party_ids_deduplicated():
    report = {
        "pairwise_hotspots": [
            _hotspot(["a", "b"]),
            _hotspot(["a", "c"]),
            _hotspot(["b", "c"]),
        ],
        "alignment_score": 0.4,
        "tension_score": 0.5,
    }
    result = build_multi_party_alignment_state(report)
    ids = [p["party_id"] for p in result["parties"]]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Position labels
# ---------------------------------------------------------------------------

def test_tension_source_label_for_dominant_party():
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        hotspots=[
            _hotspot(["a", "b"], tension=0.7, mismatch_reasons=["intent_conflict:x!=y"]),
        ],
        tension_score=0.7,
        alignment_score=0.2,
    )
    result = build_multi_party_alignment_state(report)
    # Both a and b appear in the single hotspot; both have high tension
    labels = {p["party_id"]: p["position_label"] for p in result["parties"]}
    assert labels["a"] in {"tension_source", "responsive", "neutral"}


def test_aligned_label_when_no_hotspots_and_high_alignment():
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        alignment_score=0.8,
        tension_score=0.1,
    )
    result = build_multi_party_alignment_state(report)
    for party in result["parties"]:
        assert party["position_label"] == "aligned"


def test_neutral_label_when_no_hotspots_low_alignment():
    report = _make_report(
        participants=[{"participant_id": "a"}],
        alignment_score=0.3,
        tension_score=0.2,
    )
    result = build_multi_party_alignment_state(report)
    assert result["parties"][0]["position_label"] == "neutral"


# ---------------------------------------------------------------------------
# Tension axes
# ---------------------------------------------------------------------------

def test_tension_axes_collected_from_hotspot_mismatch_reasons():
    reasons = ["intent_conflict:x!=y", "why_mismatch"]
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        hotspots=[_hotspot(["a", "b"], mismatch_reasons=reasons)],
    )
    result = build_multi_party_alignment_state(report)
    for party in result["parties"]:
        assert set(party["tension_axes"]) == set(reasons)


def test_tension_axes_capped_at_four():
    reasons = [f"reason_{i}" for i in range(8)]
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        hotspots=[_hotspot(["a", "b"], mismatch_reasons=reasons)],
    )
    result = build_multi_party_alignment_state(report)
    for party in result["parties"]:
        assert len(party["tension_axes"]) <= 4


def test_tension_axes_empty_when_no_hotspots():
    report = _make_report(participants=[{"participant_id": "a"}])
    result = build_multi_party_alignment_state(report)
    assert result["parties"][0]["tension_axes"] == []


# ---------------------------------------------------------------------------
# Alignment gap
# ---------------------------------------------------------------------------

def test_alignment_gap_zero_when_no_hotspots():
    report = _make_report(participants=[{"participant_id": "a"}])
    result = build_multi_party_alignment_state(report)
    assert result["parties"][0]["alignment_gap"] == 0.0


def test_alignment_gap_computed_from_hotspot_alignment():
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        hotspots=[_hotspot(["a", "b"], alignment=0.6)],
    )
    result = build_multi_party_alignment_state(report)
    party_a = next(p for p in result["parties"] if p["party_id"] == "a")
    # gap = 1 - 0.6 = 0.4
    assert abs(party_a["alignment_gap"] - 0.4) < 1e-4


# ---------------------------------------------------------------------------
# State label
# ---------------------------------------------------------------------------

def test_state_escalating_above_065():
    report = _make_report(tension_score=0.7, alignment_score=0.2)
    result = build_multi_party_alignment_state(report)
    assert result["state_label"] == "escalating"


def test_state_diverging_between_045_and_065():
    report = _make_report(tension_score=0.5, alignment_score=0.3)
    result = build_multi_party_alignment_state(report)
    assert result["state_label"] == "diverging"


def test_state_converging_when_alignment_above_060():
    report = _make_report(tension_score=0.2, alignment_score=0.7)
    result = build_multi_party_alignment_state(report)
    assert result["state_label"] == "converging"


def test_state_stable_otherwise():
    report = _make_report(tension_score=0.3, alignment_score=0.4)
    result = build_multi_party_alignment_state(report)
    assert result["state_label"] == "stable"


# ---------------------------------------------------------------------------
# Dominant tension axis
# ---------------------------------------------------------------------------

def test_dominant_tension_axis_most_frequent_reason():
    report = _make_report(
        participants=[
            {"participant_id": "a"}, {"participant_id": "b"}, {"participant_id": "c"}
        ],
        hotspots=[
            _hotspot(["a", "b"], mismatch_reasons=["why_mismatch"]),
            _hotspot(["a", "c"], mismatch_reasons=["why_mismatch"]),
            _hotspot(["b", "c"], mismatch_reasons=["intent_conflict"]),
        ],
    )
    result = build_multi_party_alignment_state(report)
    assert result["dominant_tension_axis"] == "why_mismatch"


def test_dominant_tension_axis_empty_when_no_mismatch_reasons():
    report = _make_report(
        hotspots=[_hotspot(["a", "b"], mismatch_reasons=[])],
    )
    result = build_multi_party_alignment_state(report)
    assert result["dominant_tension_axis"] == ""


# ---------------------------------------------------------------------------
# Adoption coverage
# ---------------------------------------------------------------------------

def test_adoption_coverage_zero_when_no_traces():
    report = _make_report()
    result = build_multi_party_alignment_state(report)
    assert result["adoption_coverage"] == 0.0


def test_adoption_coverage_mean_of_trace_scores():
    traces = [
        {"adoption_score": 0.8, "adoption_label": "adopted"},
        {"adoption_score": 0.4, "adoption_label": "partially_adopted"},
    ]
    report = _make_report()
    result = build_multi_party_alignment_state(report, adoption_traces=traces)
    assert abs(result["adoption_coverage"] - 0.6) < 1e-4


def test_adoption_coverage_ignores_none_trace_list():
    report = _make_report()
    result = build_multi_party_alignment_state(report, adoption_traces=None)
    assert result["adoption_coverage"] == 0.0


# ---------------------------------------------------------------------------
# Stable schema keys
# ---------------------------------------------------------------------------

def test_output_keys_always_present():
    required = {
        "parties", "party_count", "alignment_convergence",
        "dominant_tension_axis", "state_label", "state_description",
        "adoption_coverage",
    }
    result = build_multi_party_alignment_state({})
    assert required.issubset(result.keys())


def test_party_keys_always_present():
    report = _make_report(
        participants=[{"participant_id": "a"}, {"participant_id": "b"}],
        hotspots=[_hotspot(["a", "b"])],
    )
    result = build_multi_party_alignment_state(report)
    required_party = {"party_id", "position_label", "tension_axes", "alignment_gap", "hotspot_count"}
    for party in result["parties"]:
        assert required_party.issubset(party.keys())


# ---------------------------------------------------------------------------
# Metrics dataclass
# ---------------------------------------------------------------------------

def test_metrics_to_dict_keys():
    m = MultiPartyAlignmentMetrics()
    d = m.to_dict()
    expected = {
        "calls_total", "empty_report_total", "parties_seen_total",
        "avg_parties_per_nonempty", "escalating_total", "diverging_total",
        "converging_total", "stable_total", "hotspots_processed_total",
    }
    assert expected.issubset(d.keys())


def test_metrics_avg_parties_zero_when_no_calls():
    m = MultiPartyAlignmentMetrics()
    assert m.to_dict()["avg_parties_per_nonempty"] == 0.0


def test_metrics_avg_parties_computed():
    m = MultiPartyAlignmentMetrics(
        calls_total=3,
        empty_report_total=1,
        parties_seen_total=6,
    )
    assert m.to_dict()["avg_parties_per_nonempty"] == 3.0
