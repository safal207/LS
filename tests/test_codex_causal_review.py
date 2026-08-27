import hashlib
import io
import json
import urllib.error

from tools.codex_causal_review import _provider_matches, run_review, write_review


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
    monkeypatch.setenv("CODEX_MODEL", "gpt-5.6-terra")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("REVIEW_JSON_FILE", str(tmp_path / "review.json"))
    monkeypatch.setenv("REVIEW_MD_FILE", str(tmp_path / "review.md"))
    monkeypatch.setenv("RAW_RESPONSE_FILE", str(tmp_path / "raw.txt"))


def valid_model_output():
    return {
        "verdict": "COMMENT",
        "risk_level": "medium",
        "findings": [
            {
                "id": "CODEX-1",
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
                "dedupe_key": "external.codex.missing-validation",
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


def response_payload(*, model="gpt-5.6-terra", output=None):
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": model,
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(output or valid_model_output()),
                    }
                ],
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    }


def test_model_provenance_accepts_exact_or_dated_snapshot():
    assert _provider_matches("gpt-5.6-terra", "gpt-5.6-terra")
    assert _provider_matches("gpt-5.6-terra", "gpt-5.6-terra-2026-06-01")
    assert not _provider_matches("gpt-5.6-terra", "gpt-5.6-luna")


def test_not_run_writes_zero_finding_artifact(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    review = write_review(
        status="NOT_RUN",
        provenance="UNVERIFIED",
        details="OPENAI_API_KEY unavailable.",
    )
    assert review["reviewer"]["id"] == "codex"
    assert review["execution"]["status"] == "NOT_RUN"
    assert review["findings"] == []


def test_completed_response_records_provider_and_usage(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.codex_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(model="gpt-5.6-terra-2026-06-01")
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "COMPLETED"
    assert review["execution"]["provenance"] == "MATCHED"
    assert review["reviewer"]["model"] == "gpt-5.6-terra-2026-06-01"
    assert "total_tokens=150" in review["execution"]["details"]
    assert len(review["findings"]) == 1


def test_model_mismatch_is_diagnostic(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.codex_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(model="gpt-5.6-luna")
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MISMATCH"
    assert review["findings"] == []


def test_insufficient_quota_is_explicit_failed_lane(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    body = json.dumps(
        {
            "error": {
                "code": "insufficient_quota",
                "type": "insufficient_quota",
                "message": "You exceeded your current quota.",
            }
        }
    ).encode("utf-8")

    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            hdrs=None,
            fp=io.BytesIO(body),
        )

    monkeypatch.setattr("tools.codex_causal_review.urllib.request.urlopen", fail)
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "FAILED"
    assert review["execution"]["provenance"] == "UNVERIFIED"
    assert "insufficient_quota" in review["execution"]["details"]
    assert review["findings"] == []


def test_invalid_output_is_diagnostic_after_model_match(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "tools.codex_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            response_payload(output={"findings": []})
        ),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MATCHED"
    assert review["findings"] == []
