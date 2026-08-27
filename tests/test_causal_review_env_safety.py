import subprocess
from pathlib import Path

from tools.causal_review_request import write_env


def request(repository):
    return {
        "target": {
            "repository": repository,
            "pr_number": 42,
            "head_sha": "a" * 40,
            "patch_sha256": "sha256:" + "b" * 64,
        }
    }


def test_target_environment_quotes_shell_metacharacters(tmp_path):
    marker = tmp_path / "must-not-exist"
    repository = "owner$(touch${IFS}must-not-exist)/repo"
    input_dir = tmp_path / "input dir"
    input_dir.mkdir()
    env_path = tmp_path / "target.env"

    write_env(env_path, request(repository), input_dir)

    script = """
      set -euo pipefail
      source "$1"
      printf '%s\n' \
        "$TARGET_REPOSITORY" \
        "$TARGET_PR_NUMBER" \
        "$TARGET_HEAD_SHA" \
        "$TARGET_PATCH_SHA256" \
        "$PATCH_FILE"
    """
    result = subprocess.run(
        ["bash", "-c", script, "bash", str(env_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert not marker.exists()
    assert result.stdout.splitlines() == [
        repository,
        "42",
        "a" * 40,
        "sha256:" + "b" * 64,
        str(input_dir / "target.patch"),
    ]


def test_target_environment_contains_only_allowlisted_exports(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    env_path = tmp_path / "target.env"
    write_env(env_path, request("safal207/LS"), input_dir)

    names = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        assert line.startswith("export ")
        name = line.removeprefix("export ").split("=", 1)[0]
        names.append(name)

    assert names == [
        "TARGET_REPOSITORY",
        "TARGET_PR_NUMBER",
        "TARGET_HEAD_SHA",
        "TARGET_PATCH_SHA256",
        "PATCH_FILE",
    ]
