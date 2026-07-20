from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = (
    ROOT
    / "docs"
    / "lotus-cases"
    / "tradernet-product-funnel-impact-v1.json"
)
DOC_PATH = (
    ROOT
    / "docs"
    / "lotus-cases"
    / "TRADERNET_PRODUCT_FUNNEL_IMPACT.md"
)


def _scorecard() -> dict:
    return json.loads(SCORECARD_PATH.read_text(encoding="utf-8"))


def test_scorecard_has_stable_canonical_digest() -> None:
    scorecard = _scorecard()
    observed = scorecard.pop("scorecard_sha256")
    canonical = json.dumps(
        scorecard,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert observed == expected
    assert observed == (
        "326d784d6dffaa72e5af54fc271023fa3cdcf8f35d4d7868a748424d19f30dd3"
    )


def test_scorecard_preserves_advisory_authority_boundary() -> None:
    authority = _scorecard()["authority"]

    assert authority["mode"] == "advisory_only"
    assert authority["ownership"] is False
    assert authority["approval"] is False
    assert authority["execution"] is False
    assert authority["account_access"] is False
    assert authority["order_execution"] is False
    assert authority["external_submission"] is False
    assert authority["experiment_launch"] is False
    assert authority["deployment"] is False
    assert authority["delivery"] is False
    assert authority["merge"] is False


def test_human_impact_order_contains_only_confirmed_public_findings() -> None:
    scorecard = _scorecard()
    findings = scorecard["human_impact_order"]

    assert [item["rank"] for item in findings] == [1, 2, 3, 4]
    assert all(item["evidence_status"] == "CONFIRMED" for item in findings)
    assert [item["id"] for item in findings] == [
        "mobile-chart-user-agent-404",
        "mobile-hero-late-discovery",
        "terminal-hidden-mobile-asset",
        "terminal-missing-onboarding-asset",
    ]


def test_handoff_blocks_unproven_authenticated_and_growth_claims() -> None:
    scorecard = _scorecard()
    blocked = "\n".join(scorecard["handoff"]["not_ready"])

    assert "Authenticated order-form defect claims" in blocked
    assert "KYC or funding recovery defect claims" in blocked
    assert "Stop Loss or Take Profit usability claims" in blocked
    assert "Conversion-lift claims" in blocked
    assert "Security-vulnerability claims" in blocked
    assert "One-root-cause claim" in blocked


def test_clickfunnels_boundary_rejects_pressure_and_vendor_overclaim() -> None:
    boundary = _scorecard()["clickfunnels_boundary"]

    assert boundary["role"] == "pattern_reference_only"
    assert boundary["false_urgency"] is False
    assert boundary["pressure_to_trade"] is False
    assert boundary["preselected_paid_or_risk_increasing_choices"] is False
    assert boundary["vendor_claims_are_tradernet_evidence"] is False


def test_scorecard_consumes_exact_cross_repository_heads() -> None:
    chain = _scorecard()["evidence_chain"]

    assert chain["liminalqa_exact_head"] == (
        "d14d0e0cf434000c10609dc8627c288df5306df6"
    )
    assert chain["pythia_exact_head"] == (
        "323705b4f7a8ecca3c5a475e2504f2c41e231188"
    )
    assert chain["cml_exact_head"] == (
        "f0269ee1f9c9237876dcf70fc390a66790a76e55"
    )
    assert chain["cml_pack_id"] == (
        "d9b886e7b4985dd9c4932232a69a5bfb5caaf70f597051a87dd93357560c4654"
    )
    assert chain["lotus_product_lens_exact_head"] == (
        "44087899bdaad86b32b13d89812cbf7a174db2fe"
    )


def test_human_document_keeps_review_and_evidence_language() -> None:
    document = DOC_PATH.read_text(encoding="utf-8")

    assert "HUMAN_REVIEW_REQUIRED" in document
    assert "NEEDS_AUTHENTICATED_EVIDENCE" in document
    assert "qualified seven-day activation" in document
    assert "does not access accounts" in document
