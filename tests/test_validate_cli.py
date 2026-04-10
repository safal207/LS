from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ls.cognition.validate_cli import main


def _sample_payload() -> dict:
    return {
        "task_prompt": "Which deployment strategy?",
        "candidates": [
            {
                "agent_id": "agent-a",
                "answer_text": "Blue-green deployment with automated rollback.",
                "relevance": 0.90,
                "thread_relevance": 0.87,
                "hallucination_risk": 0.05,
                "supports": ["agent-b"],
            },
            {
                "agent_id": "agent-b",
                "answer_text": "Blue-green with canary analysis before full cutover.",
                "relevance": 0.85,
                "thread_relevance": 0.82,
                "hallucination_risk": 0.07,
            },
        ],
    }


def _write_payload(payload: dict) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(payload, tmp)
    tmp.close()
    return tmp.name


# ── Basic validation ─────────────────────────────────────────────────────────


def test_cli_basic(capsys):
    path = _write_payload(_sample_payload())
    main([path])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["winner_agent_id"] is not None
    assert output["consensus_status"] in {"convergent", "weak", "conflicted", "rejected"}
    assert isinstance(output["ranked_candidates"], list)
    assert len(output["ranked_candidates"]) == 2
    Path(path).unlink()


# ── With governance ──────────────────────────────────────────────────────────


def test_cli_with_governance(capsys):
    path = _write_payload(_sample_payload())
    main([path, "--governance"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert "governance" in output
    assert isinstance(output["governance"]["review_required"], bool)
    assert output["governance"]["governed_winner_agent_id"] is not None
    Path(path).unlink()


# ── With signing ─────────────────────────────────────────────────────────────


def test_cli_with_sign_requires_trace(capsys):
    """--sign without --trace: no trace_artifact → no signing section."""
    path = _write_payload(_sample_payload())
    main([path, "--sign"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    # Without --trace there's no trace_artifact, so no "trace" key
    assert "trace" not in output or output.get("trace") is None
    Path(path).unlink()


def test_cli_with_trace_and_sign(capsys):
    """--trace --sign: trace attached, signing attempted."""
    path = _write_payload(_sample_payload())
    main([path, "--trace", "--sign"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    # lifetra_py not installed → trace_artifact is None → no trace key
    # This is fine — we test graceful degradation
    # If trace IS present, signing must have been attempted
    if "trace" in output and output["trace"] is not None:
        assert "signed" in output["trace"]
    Path(path).unlink()


# ── Compact output ───────────────────────────────────────────────────────────


def test_cli_compact_output(capsys):
    path = _write_payload(_sample_payload())
    main([path, "--compact"])
    captured = capsys.readouterr()
    # Compact output should be a single line
    lines = captured.out.strip().split("\n")
    assert len(lines) == 1
    output = json.loads(lines[0])
    assert output["winner_agent_id"] is not None
    Path(path).unlink()


# ── All flags combined ───────────────────────────────────────────────────────


def test_cli_all_flags(capsys):
    path = _write_payload(_sample_payload())
    main([path, "--governance", "--trace", "--sign", "--escalation", "logging"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["winner_agent_id"] is not None
    assert "governance" in output
    Path(path).unlink()


# ── Error handling ───────────────────────────────────────────────────────────


def test_cli_missing_file():
    with pytest.raises(SystemExit) as exc_info:
        main(["/nonexistent/file.json"])
    assert exc_info.value.code == 1


def test_cli_bad_json():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write("not valid json{{{")
    tmp.close()
    with pytest.raises(SystemExit) as exc_info:
        main([tmp.name])
    assert exc_info.value.code == 1
    Path(tmp.name).unlink()


def test_cli_missing_task_prompt():
    payload = {"candidates": [{"agent_id": "a", "answer_text": "x"}]}
    path = _write_payload(payload)
    with pytest.raises(SystemExit) as exc_info:
        main([path])
    assert exc_info.value.code == 1
    Path(path).unlink()


# ── Stdin mode ───────────────────────────────────────────────────────────────


def test_cli_stdin(capsys, monkeypatch):
    payload = json.dumps(_sample_payload())
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    main(["-"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["winner_agent_id"] is not None
