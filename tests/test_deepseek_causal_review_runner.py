import hashlib
import json

from tools.deepseek_causal_review import run_review, write_lane


def configure_env(tmp_path, monkeypatch):
    patch = b"diff --git a/a.py b/a.py\n+value = 1\n"
    patch_path = tmp_path / "target.patch"
    patch_path.write_bytes(patch)
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("Return native causal findings.", encoding="utf-8")
    monkeypatch.setenv("TARGET_REPOSITORY", "safal207/LS")
    monkeypatch.setenv("TARGET_PR_NUMBER", "42")
    monkeypatch.setenv("TARGET_HEAD_SHA", "a" * 40)
    monkeypatch.setenv(
        "TARGET_PATCH_SHA256", "sha256:" + hashlib.sha256(patch).hexdigest()
    )
    monkeypatch.setenv("PATCH_FILE", str(patch_path))
    monkeypatch.setenv("CAUSAL_PROMPT_FILE", str(prompt_path))
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_LANE_FILE", str(tmp_path / "lane.json"))
    monkeypatch.setenv("REVIEW_JSON_FILE", str(tmp_path / "review.json"))
    monkeypatch.setenv("REVIEW_MD_FILE", str(tmp_path / "review.md"))
    monkeypatch.setenv("RAW_RESPONSE_FILE", str(tmp_path / "raw.txt"))
    return patch


def valid_model_output():
    return {
        "findings": [
            {
                "source_id": "ds-1",
                "severity": "medium",
                "title": "Missing validation",
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
                "confidence": 0.75,
                "reproduction": "Pass an invalid value.",
                "recommendation": "Validate before storing.",
            }
        ],
        "tests_to_run": ["Submit malformed input."],
        "human_decision_points": ["Confirm required validation policy."],
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


def test_diagnostic_not_run_writes_findingless_artifacts(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    review = write_lane(
        status="NOT_RUN",
        provenance="UNVERIFIED",
        details="Credential unavailable.",
    )
    assert review["execution"]["status"] == "NOT_RUN"
    assert review["findings"] == []
    assert json.loads((tmp_path / "lane.json").read_text())["model"]["provider"] is None


def test_completed_provider_response_produces_candidate_review(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    payload = {
        "model": "deepseek-reasoner",
        "choices": [
            {"message": {"content": json.dumps(valid_model_output())}}
        ],
    }
    monkeypatch.setattr(
        "tools.deepseek_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"] == {
        "status": "COMPLETED",
        "provenance": "MATCHED",
        "details": "Requested and provider model both equal deepseek-reasoner.",
    }
    assert review["findings"][0]["claim_status"] == "CANDIDATE"
    assert review["findings"][0]["id"].startswith("DEEPSEEK-")


def test_provider_model_mismatch_is_diagnostic(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    payload = {
        "model": "deepseek-chat",
        "choices": [{"message": {"content": json.dumps(valid_model_output())}}],
    }
    monkeypatch.setattr(
        "tools.deepseek_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MISMATCH"
    assert review["findings"] == []


def test_invalid_model_envelope_is_diagnostic(tmp_path, monkeypatch):
    configure_env(tmp_path, monkeypatch)
    payload = {
        "model": "deepseek-reasoner",
        "choices": [{"message": {"content": json.dumps({"findings": []})}}],
    }
    monkeypatch.setattr(
        "tools.deepseek_causal_review.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(payload),
    )
    assert run_review() == 0
    review = json.loads((tmp_path / "review.json").read_text())
    assert review["execution"]["status"] == "DIAGNOSTIC"
    assert review["execution"]["provenance"] == "MATCHED"
    assert review["findings"] == []
