# ruff: noqa: E402
"""Tests for the radioactive decay model for ResonanceKnowledgeUnit.

Covers:
  - ResonanceDecayConfig: defaults, half_life_for() per source
  - effective_score(): formula correctness, timestamp handling, source dispatch
  - is_expired(): floor threshold
  - apply_decay(): sorting, includes expired
  - prune_expired(): removes expired, keeps live
  - MemoryGraphStore.list_live_resonance_units(): integrated decay filter
  - MemoryGraphStore.confirm_resonance_unit(): timestamp reset resets decay
"""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.decay import (
    ResonanceDecayConfig,
    apply_decay,
    effective_score,
    is_expired,
    prune_expired,
)
from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(hours_ago: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


def _ts(hours_ago: float = 0.0) -> str:
    return _utc(hours_ago).isoformat()


def _unit(
    resonance: float = 0.8,
    hours_ago: float = 0.0,
    source: str = "care_cycle",
) -> ResonanceKnowledgeUnit:
    return ResonanceKnowledgeUnit(
        source_question="test",
        resonance_score=resonance,
        timestamp=_ts(hours_ago),
        metadata={"source": source},
    )


# ---------------------------------------------------------------------------
# ResonanceDecayConfig
# ---------------------------------------------------------------------------


def test_config_defaults():
    cfg = ResonanceDecayConfig()
    assert cfg.default_half_life_hours == 24.0
    assert cfg.floor_score == 0.05
    assert cfg.half_life_for("care_cycle") == 72.0
    assert cfg.half_life_for("fallback") == 12.0
    assert cfg.half_life_for("dashscope") == 48.0
    assert cfg.half_life_for("unknown_source") == 24.0


def test_config_custom_half_life():
    cfg = ResonanceDecayConfig(
        default_half_life_hours=10.0,
        half_life_by_source={"my_source": 5.0},
    )
    assert cfg.half_life_for("my_source") == 5.0
    assert cfg.half_life_for("other") == 10.0


# ---------------------------------------------------------------------------
# effective_score — formula correctness
# ---------------------------------------------------------------------------


def test_effective_score_fresh_unit_unchanged():
    """A unit timestamped right now has effective ≈ score₀."""
    cfg = ResonanceDecayConfig()
    u = _unit(resonance=0.8, hours_ago=0.0, source="care_cycle")
    now = _utc(0.0)
    score = effective_score(u, cfg, now=now)
    assert abs(score - 0.8) < 0.001


def test_effective_score_after_one_half_life():
    """After exactly T½ hours the score must be halved."""
    cfg = ResonanceDecayConfig()
    half_life = cfg.half_life_for("care_cycle")  # 72 h
    u = _unit(resonance=0.8, hours_ago=half_life, source="care_cycle")
    now = _utc(0.0)
    score = effective_score(u, cfg, now=now)
    assert abs(score - 0.4) < 1e-6, f"Expected 0.4, got {score}"


def test_effective_score_after_two_half_lives():
    """After 2×T½ the score must be ¼ of the original."""
    cfg = ResonanceDecayConfig()
    half_life = cfg.half_life_for("fallback")  # 12 h
    u = _unit(resonance=0.8, hours_ago=2 * half_life, source="fallback")
    now = _utc(0.0)
    score = effective_score(u, cfg, now=now)
    assert abs(score - 0.2) < 1e-6, f"Expected 0.2, got {score}"


def test_effective_score_formula_matches_manual():
    """Cross-check against the formula computed independently."""
    cfg = ResonanceDecayConfig()
    half_life = 24.0
    elapsed = 10.0
    score0 = 0.7
    lam = math.log(2) / half_life
    expected = score0 * math.exp(-lam * elapsed)

    u = _unit(resonance=score0, hours_ago=elapsed, source="unknown_source")
    got = effective_score(u, cfg, now=_utc(0.0))
    assert abs(got - expected) < 1e-9


def test_effective_score_fallback_decays_faster_than_care_cycle():
    """fallback (T½=12h) must decay faster than care_cycle (T½=72h)."""
    cfg = ResonanceDecayConfig()
    elapsed = 24.0
    u_fb = _unit(resonance=0.8, hours_ago=elapsed, source="fallback")
    u_cc = _unit(resonance=0.8, hours_ago=elapsed, source="care_cycle")
    now = _utc(0.0)
    assert effective_score(u_fb, cfg, now=now) < effective_score(u_cc, cfg, now=now)


def test_effective_score_zero_resonance():
    u = _unit(resonance=0.0, hours_ago=1.0)
    assert effective_score(u, ResonanceDecayConfig()) == 0.0


def test_effective_score_bad_timestamp_returns_score0():
    """Unparseable timestamp → Δt=0 → score unchanged."""
    cfg = ResonanceDecayConfig()
    u = ResonanceKnowledgeUnit(
        source_question="t",
        resonance_score=0.6,
        timestamp="not-a-date",
        metadata={"source": "care_cycle"},
    )
    score = effective_score(u, cfg)
    assert abs(score - 0.6) < 1e-9


# ---------------------------------------------------------------------------
# is_expired
# ---------------------------------------------------------------------------


def test_is_expired_fresh_unit_not_expired():
    cfg = ResonanceDecayConfig(floor_score=0.05)
    u = _unit(resonance=0.8, hours_ago=0.0)
    assert not is_expired(u, cfg)


def test_is_expired_very_old_unit():
    cfg = ResonanceDecayConfig(floor_score=0.05)
    # After 10 half-lives score₀·2^(-10) ≈ 0.8/1024 ≈ 0.00078 < 0.05
    half_life = cfg.half_life_for("care_cycle")
    u = _unit(resonance=0.8, hours_ago=10 * half_life, source="care_cycle")
    assert is_expired(u, cfg)


def test_is_expired_just_above_floor_not_expired():
    """A unit whose effective score is clearly above the floor is not expired."""
    cfg = ResonanceDecayConfig(floor_score=0.05)
    # Use a very fresh unit — effective ≈ score₀ = 0.8, well above 0.05
    u = _unit(resonance=0.8, hours_ago=0.0, source="care_cycle")
    assert not is_expired(u, cfg)


# ---------------------------------------------------------------------------
# apply_decay
# ---------------------------------------------------------------------------


def test_apply_decay_sorted_strongest_first():
    cfg = ResonanceDecayConfig()
    now = _utc(0.0)
    units = [
        _unit(resonance=0.5, hours_ago=0.0),
        _unit(resonance=0.9, hours_ago=0.0),
        _unit(resonance=0.3, hours_ago=0.0),
    ]
    result = apply_decay(units, cfg, now=now)
    scores = [s for _, s in result]
    assert scores == sorted(scores, reverse=True)


def test_apply_decay_includes_expired():
    cfg = ResonanceDecayConfig(floor_score=0.05)
    half_life = cfg.half_life_for("fallback")
    units = [
        _unit(resonance=0.8, hours_ago=0.0, source="fallback"),
        _unit(resonance=0.8, hours_ago=20 * half_life, source="fallback"),
    ]
    result = apply_decay(units, cfg)
    assert len(result) == 2  # expired unit still present


def test_apply_decay_empty():
    assert apply_decay([], ResonanceDecayConfig()) == []


# ---------------------------------------------------------------------------
# prune_expired
# ---------------------------------------------------------------------------


def test_prune_expired_removes_old_units():
    cfg = ResonanceDecayConfig(floor_score=0.05)
    half_life = cfg.half_life_for("fallback")
    fresh = _unit(resonance=0.8, hours_ago=0.0, source="fallback")
    stale = _unit(resonance=0.8, hours_ago=15 * half_life, source="fallback")
    result = prune_expired([fresh, stale], cfg)
    assert len(result) == 1
    assert result[0] is fresh


def test_prune_expired_keeps_all_fresh():
    cfg = ResonanceDecayConfig()
    units = [_unit(resonance=0.8, hours_ago=0.0) for _ in range(5)]
    assert len(prune_expired(units, cfg)) == 5


def test_prune_expired_empty():
    assert prune_expired([], ResonanceDecayConfig()) == []


# ---------------------------------------------------------------------------
# MemoryGraphStore.list_live_resonance_units
# ---------------------------------------------------------------------------


def test_store_list_live_filters_expired(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    cfg = ResonanceDecayConfig(floor_score=0.05)
    half_life = cfg.half_life_for("fallback")

    fresh = ResonanceKnowledgeUnit(
        source_question="fresh",
        resonance_score=0.8,
        timestamp=_ts(0.0),
        metadata={"source": "fallback"},
    )
    stale = ResonanceKnowledgeUnit(
        source_question="stale",
        resonance_score=0.8,
        timestamp=_ts(15 * half_life),
        metadata={"source": "fallback"},
    )
    store.store_resonance_unit(fresh)
    store.store_resonance_unit(stale)

    live = store.list_live_resonance_units(cfg)
    assert len(live) == 1
    assert live[0].source_question == "fresh"


def test_store_list_live_no_config_uses_defaults(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    u = ResonanceKnowledgeUnit(
        source_question="q",
        resonance_score=0.8,
        timestamp=_ts(0.0),
        metadata={"source": "care_cycle"},
    )
    store.store_resonance_unit(u)
    live = store.list_live_resonance_units()
    assert len(live) == 1


# ---------------------------------------------------------------------------
# MemoryGraphStore.confirm_resonance_unit
# ---------------------------------------------------------------------------


def test_confirm_resets_timestamp(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    cfg = ResonanceDecayConfig()
    half_life = cfg.half_life_for("care_cycle")

    # Store a unit that is 1 half-life old (effective = 0.4)
    old_ts = _ts(half_life)
    u = ResonanceKnowledgeUnit(
        source_question="q",
        resonance_score=0.8,
        timestamp=old_ts,
        metadata={"source": "care_cycle"},
    )
    stored = store.store_resonance_unit(u)

    # Effective score before confirmation ≈ 0.4
    before = effective_score(stored, cfg)
    assert abs(before - 0.4) < 1e-4

    confirmed = store.confirm_resonance_unit(stored.unit_id)
    assert confirmed is not None
    assert confirmed.timestamp != old_ts

    # After confirmation the decay clock is reset — effective ≈ score₀
    after = effective_score(confirmed, cfg)
    assert after > 0.79, f"Expected score close to 0.8 after confirm, got {after}"


def test_confirm_nonexistent_unit_returns_none(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    result = store.confirm_resonance_unit("no-such-id")
    assert result is None


def test_confirm_unit_survives_subsequent_list_live(tmp_path):
    """A confirmed unit must not be pruned when listed immediately after."""
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    cfg = ResonanceDecayConfig(floor_score=0.05)
    half_life = cfg.half_life_for("fallback")

    # Start with a unit that would normally be expired
    u = ResonanceKnowledgeUnit(
        source_question="q",
        resonance_score=0.8,
        timestamp=_ts(15 * half_life),
        metadata={"source": "fallback"},
    )
    stored = store.store_resonance_unit(u)

    assert store.list_live_resonance_units(cfg) == []  # expired before confirm

    store.confirm_resonance_unit(stored.unit_id)
    live = store.list_live_resonance_units(cfg)
    assert len(live) == 1
