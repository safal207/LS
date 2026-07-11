import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools/run_native_causal_reviewers.sh"


def test_runner_creates_explicit_not_run_artifacts_without_secrets(tmp_path):
    patch = tmp_path / "target.patch"
    patch.write_bytes(b"diff --git a/a b/a\n")
    digest = "sha256:" + hashlib.sha256(patch.read_bytes()).hexdigest()
    output = tmp_path / "output"
    env_file = tmp_path / "target.env"
    env_file.write_text(
        "\n".join(
            [
                "export TARGET_REPOSITORY=safal207/LS",
                "export TARGET_PR_NUMBER=42",
                f"export TARGET_HEAD_SHA={'a' * 40}",
                f"export TARGET_PATCH_SHA256={digest}",
                f"export PATCH_FILE={patch}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "TARGET_ENV_FILE": str(env_file),
            "OUTPUT_DIR": str(output),
            "CAUSAL_PROMPT_FILE": str(ROOT / ".github/prompts/causal-review-v0.1.md"),
            "XAI_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "OPENAI_API_KEY": "",
            "XAI_MODEL": "grok-4.5",
            "DEEPSEEK_MODEL": "deepseek-reasoner",
            "CODEX_MODEL": "gpt-5.6-terra",
        }
    )

    subprocess.run(
        ["bash", str(RUNNER)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    expected = {
        "grok-review.json": "grok",
        "deepseek-review.json": "deepseek",
        "codex-review.json": "codex",
    }
    for filename, reviewer in expected.items():
        review = json.loads((output / filename).read_text(encoding="utf-8"))
        assert review["reviewer"]["id"] == reviewer
        assert review["execution"]["status"] == "NOT_RUN"
        assert review["execution"]["provenance"] == "UNVERIFIED"
        assert review["findings"] == []
        assert review["verdict"] is None

    lane = json.loads((output / "deepseek-lane.json").read_text(encoding="utf-8"))
    assert lane["execution"]["status"] == "NOT_RUN"
    assert lane["findings"] == []
