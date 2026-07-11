import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL_WORKFLOW = ROOT / ".github/workflows/trusted-causal-review-label.yml"
FORK_COLLECTOR = ROOT / ".github/workflows/causal-review-collect.yml"
OLD_DIRECT = ROOT / ".github/workflows/trusted-causal-review-same-repo.yml"
OLD_BRIDGE = ROOT / ".github/workflows/trusted-causal-review-ensemble.yml"
NATIVE_RUNNER = ROOT / "tools/run_native_causal_reviewers.sh"


def parsed_yaml(path: Path):
    result = subprocess.run(
        [
            "ruby",
            "-rjson",
            "-ryaml",
            "-e",
            "doc = YAML.load_file(ARGV[0]); puts JSON.generate(doc)",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_label_workflow_is_loaded_from_protected_base_context():
    text = LABEL_WORKFLOW.read_text(encoding="utf-8")

    assert "  pull_request_target:\n" in text
    assert "    types: [labeled]" in text
    assert "github.event.label.name == 'causal-review'" in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "github.event.pull_request.author_association" in text
    assert "OWNER" in text
    assert "MEMBER" in text
    assert "COLLABORATOR" in text
    assert "ref: refs/heads/main" in text
    assert "persist-credentials: false" in text
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in text
    assert "Never checks out" in text


def test_privileged_workflow_structure_keeps_secrets_after_verification():
    workflow = parsed_yaml(LABEL_WORKFLOW)
    ensemble = workflow["jobs"]["ensemble"]
    steps = ensemble["steps"]

    checkouts = [step for step in steps if str(step.get("uses", "")).startswith("actions/checkout")]
    assert len(checkouts) == 1
    assert checkouts[0]["with"] == {
        "ref": "refs/heads/main",
        "persist-credentials": False,
    }

    verify_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Verify exact target before credentials"
    )
    native_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Run native causal reviewers"
    )
    secret_indices = [
        index
        for index, step in enumerate(steps)
        if "secrets." in json.dumps(step, sort_keys=True)
    ]
    assert secret_indices == [native_index]
    assert verify_index < native_index
    assert "steps.request.outcome == 'success'" in str(steps[native_index]["if"])

    for step in steps:
        uses = str(step.get("uses", ""))
        assert "${{" not in uses


def test_label_command_verifies_before_and_after_model_calls():
    text = LABEL_WORKFLOW.read_text(encoding="utf-8")

    first_verify = text.index("Verify exact target before credentials")
    native = text.index("Run native causal reviewers")
    final_verify = text.index("Reverify exact head after model calls")
    report = text.index("Build exact-target ensemble report")
    remove_label = text.index("Remove command label")

    assert first_verify < native < final_verify < report < remove_label
    assert text.count("python tools/retrying_causal_review_github.py verify") == 2
    assert text.count('--expected-pr-number "$PR_NUMBER"') == 2
    assert text.count('--expected-head-sha "$EXPECTED_HEAD_SHA"') == 2
    assert text.count('--expected-head-branch "$EXPECTED_HEAD_BRANCH"') == 2
    assert "name: 'causal-review'" in text


def test_workflow_and_native_runner_never_execute_target_pr_code():
    workflow = LABEL_WORKFLOW.read_text(encoding="utf-8")
    runner = NATIVE_RUNNER.read_text(encoding="utf-8")
    combined = workflow + "\n" + runner

    forbidden = (
        "git checkout",
        "git switch",
        "npm install",
        "npm ci",
        "pip install",
        "pip3 install",
        "uv pip",
        "poetry install",
        "bundle install",
        "cargo build",
        "go test",
        "curl | sh",
        "make ",
        "bash target.patch",
        "source target.patch",
    )
    for command in forbidden:
        assert command not in combined

    assert "python tools/retrying_causal_review_github.py collect" in workflow
    assert "bash tools/run_native_causal_reviewers.sh" in workflow


def test_native_runner_has_explicit_missing_secret_and_artifact_states():
    text = NATIVE_RUNNER.read_text(encoding="utf-8")

    for secret, reviewer in (
        ("XAI_API_KEY", "Grok"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("OPENAI_API_KEY", "Codex"),
    ):
        assert secret in text
        assert f"Repository secret {secret} is unavailable" in text
        assert f"{reviewer} runner ended without a validated artifact" in text

    assert text.index("run_grok") < text.index("run_deepseek") < text.index("run_codex")
    assert "None receives another reviewer's artifact as input" in text


def test_fork_workflow_has_no_model_secrets_or_native_execution():
    text = FORK_COLLECTOR.read_text(encoding="utf-8")

    assert "github.event.pull_request.head.repo.full_name != github.repository" in text
    assert "secret_access\": False" in text
    assert "NOT_AUTHORIZED_FOR_FORK" in text
    assert "python tools/retrying_causal_review_github.py collect" in text
    assert "secrets.XAI_API_KEY" not in text
    assert "secrets.DEEPSEEK_API_KEY" not in text
    assert "secrets.OPENAI_API_KEY" not in text
    assert "run_native_causal_reviewers.sh" not in text


def test_obsolete_automatic_and_workflow_run_paths_are_removed():
    assert LABEL_WORKFLOW.exists()
    assert FORK_COLLECTOR.exists()
    assert NATIVE_RUNNER.exists()
    assert not OLD_DIRECT.exists()
    assert not OLD_BRIDGE.exists()
