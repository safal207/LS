from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = (
    ROOT / "docs" / "lotus-cases" / "chatgpt-mobile-web-impact-v1.json"
)
DOC_PATH = ROOT / "docs" / "lotus-cases" / "CHATGPT_MOBILE_WEB_IMPACT.md"


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
        "af78900ccf7d744576a4ef8335b67a0939c3304780cc08f7570898bbe7f3a1e9"
    )


def test_scorecard_is_advisory_and_non_executing() -> None:
    authority = _scorecard()["authority"]

    assert authority["mode"] == "advisory_only"
    for field in (
        "ownership",
        "approval",
        "execution",
        "account_access",
        "prompt_submission",
        "login_submission",
        "external_submission",
        "security_claim",
        "deployment",
        "delivery",
        "merge",
    ):
        assert authority[field] is False


def test_public_baseline_is_pass_with_one_diagnostic() -> None:
    scorecard = _scorecard()

    assert scorecard["verdict"] == "LOW_SEVERITY_HUMAN_REVIEW"
    assert scorecard["public_mobile_baseline"]["result"] == (
        "PASS_WITH_ONE_DIAGNOSTIC"
    )
    assert len(scorecard["human_impact_order"]) == 1
    finding = scorecard["human_impact_order"][0]
    assert finding["id"] == "mobile-login-console-error"
    assert finding["severity"] == "P3-diagnostic"
    assert finding["evidence_status"] == (
        "CONFIRMED_DIAGNOSTIC_USER_IMPACT_UNKNOWN"
    )


def test_rejected_harms_and_authenticated_boundary_are_explicit() -> None:
    scorecard = _scorecard()
    rejected = "\n".join(scorecard["rejected_harms"])
    handoff = scorecard["authenticated_handoff"]

    assert "Mobile event delivery failure" in rejected
    assert "Broken mobile login" in rejected
    assert "Security vulnerability" in rejected
    assert "Native-app or authenticated-chat failure" in rejected
    assert handoff["status"] == "REQUIRED_FOR_PRODUCT_AUDIT"
    assert "long_chat_scrolling" in handoff["surfaces"]
    assert "offline_recovery" in handoff["surfaces"]


def test_exact_cross_repository_chain_is_preserved() -> None:
    chain = _scorecard()["evidence_chain"]

    assert chain["liminalqa_pr"] == 106
    assert chain["liminalqa_exact_head"] == (
        "2407be212e19a393fcd0d8dd33d9fe444aea663b"
    )
    assert chain["pythia_pr"] == 239
    assert chain["pythia_exact_head"] == (
        "cf15c07e7087f399db1b459c4850f5b4261c9b43"
    )
    assert chain["cml_pr"] == 216
    assert chain["cml_exact_head"] == (
        "29f31980c2ba229a38c4a3530eb4930e14dd3fa5"
    )
    assert chain["cml_pack_id"] == (
        "17bda596a7530302a35eeed0336907dd96e35c1349f5694e246d1cc0b147e75b"
    )


def test_human_document_preserves_low_severity_and_scope() -> None:
    document = DOC_PATH.read_text(encoding="utf-8")

    for required in (
        "LOW_SEVERITY_HUMAN_REVIEW",
        "scoped pass",
        "P3 console diagnostic",
        "No visible user impact",
        "signed-in mobile chat product",
        "does not log in",
    ):
        assert required in document
