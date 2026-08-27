import hashlib
import io
import json
import urllib.error

from tools.gonka_causal_review import (
    SHADOW_NOTICE,
    _provider_matches,
    run_review,
    write_review,
)


def configure_env(tmp_path, monkeypatch):
    patch = b"diff --git a/a.py b/a.py\n+value = 1\n"
    patch_path = tmp_path / "target.patch"
    patch_path.write_bytes(patch)
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Return a causal-review JSON object.", encoding="utf-8")
    monkeypatch.setenv("TARGET_REPOSITORY", "safal207/LS")
    monkeypatch.setenv("TARGET_PR_NUMBER", "42")
    monkeypatch.setenv("TARGET_HEAD_SHA", "a" * 40)
    monkeypatch.setenv(
        "TARGET_PATCH_SHA256", "sha256:" + hashlib.sha256(patch).hexdigest()
    )
    monkeypatch.setenv("PATCH_FILE", str(patch_path))
    monkeypatch.setenv("CAUSAL_PROMPT_FILE", str(prompt_path))
    monkeypatch.setenv("GONKA_MODEL", "minimaxai/minimax-m2.7")
    monkeypatch.setenv("GONKA_BROKER_API_KEY", "test-key")
    monkeypatch.setenv(
        "GONKA_API_URL", "https://api.gonkagate.com/v1/chat/completions"
    )
    monkeypatch.setenv("REVIEW_JSON_FILE", str(tmp_path / "review.json"))
    monkeypatch.setenv("REVIEW_MD_FILE", str(tmp_path / "review.md"))
    monkeypatch.setenv("RAW_RESPONSE_FILE", str(tmp_path / "raw.json"))


def valid_model_output():
    return {
        "verdict": "REQUEST_CHANGES",
        "risk_level": "medium",
        "findings": [
            {
                "id": "GONKA-1",
                "severity": "medium",
                "title": "Missing validation",
                "claim_status": "CANDIDATE",
                "location": {"path": "a.py", "line": 1},
                "causal_chain": {
                    "change": "A value is accepted.",
                    "root_cause": "Validation is absent.",
                    "failure_mechanism": "Malformed input crosses the boundary.",
                    "observable_effect": "Invalid state is stored.",
                    "impact": "Downstream behavior becomes unreliable.",
                },
                "evidence": [
                    {
                        "type": "patch",
                        "reference": "a.py:1",
                        "excerpt": "+value = 1",
                    }
                ],
                "confidence": 0.8,
                "reproduction": "Pass an invalid value.",
                "recommendation": "Validate before storing.",
                "dedupe_key": "external.gonka.missing-validation",
            }
        ],
        "tests_to_run": ["Submit malformed input."],
        "human_decision_points": ["Confirm the required validation policy."],
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def response_payload(*, model="minimaxai/minimax-m2.7", output=None):
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(output or valid_model_output()),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }


def test_model_provenance_accepts_case_normalization_and_snapshot():
    assert _provider_matches(
        "minimaxai/minimax-m2.7", "MiniMaxAI/MiniMax-M2.7"
    )
    assert _provider_matches(
        "minimaxai/minimax-m2.7", "minimaxai/minimax-m2.7-2026-07-01"
    )
    assert not _provider_matches(
        "minimaxai/minimax-m2.7", "moonshotai/kimi-k2.6"
    )


def test_not_run_writes_zero_finding_shadow_artifact(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    review = write_review(
        status="NOT_RUN",
        provenance="UNVERIFIED",
        details="GONKA_BROKER_API_KEY unavailable.",
    )
    assert review["reviewer"]["id"] == "gonka"
    assert review["execution"]["status"] == "NOT_RUN"
    assert review["findings"] == []
    assert review["verdict"] is None
    assert SHADOW_NOTICE in review["execution"]["details"]


def test_completed_response_is_forced_to_comment_only(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.gonka_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(model="MiniMaxAI/MiniMax-M2.7")
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "COMPLETED"
    assert review["execution"]["provenance"] == "MATCHED"
    assert review["reviewer"]["model"] == "MiniMaxAI/MiniMax-M2.7"
    assert review["verdict"] == "COMMENT"
    assert "total_tokens=150" in review["execution"]["details"]
    assert review["human_decision_points"][0] == SHADOW_NOTICE
    assert len(review["findings"]) == 1


def test_model_mismatch_is_diagnostic(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.gonka_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(model="moonshotai/kimi-k2.6")
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MISMATCH"
    assert review["findings"] == []


def test_broker_http_error_is_explicit_failed_lane(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    body = json.dumps(
        {
            "error": {
                "code": "insufficient_credits",
                "type": "billing_error",
                "message": "Not enough credits.",
            }
        }
    ).encode("utf-8")

    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            402,
            "Payment Required",
            hdrs=None,
            fp=io.BytesIO(body),
        )

    monkeypatch.setattr("tools.gonka_causal_review.urllib.request.urlopen", fail)
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "FAILED"
    assert review["execution"]["provenance"] == "UNVERIFIED"
    assert "insufficient_credits" in review["execution"]["details"]
    assert review["findings"] == []


def test_invalid_output_is_diagnostic_after_model_match(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.gonka_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(output={"findings": []})
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MATCHED"
    assert review["findings"] == []
