import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/trusted-causal-review-queue.yml"


def parsed_yaml():
    result = subprocess.run(
        [
            "ruby",
            "-rjson",
            "-ryaml",
            "-e",
            "puts JSON.generate(YAML.load_file(ARGV[0]))",
            str(WORKFLOW),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_queue_workflow_runs_only_from_protected_main_push():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "  push:\n" in text
    assert "    branches: [main]" in text
    assert '      - "causal-review-requests/queue/*.json"' in text
    assert "pull_request_target" not in text
    assert "pull_request:" not in text


def test_queue_workflow_verifies_before_secret_backed_runner():
    workflow = parsed_yaml()
    steps = workflow["jobs"]["ensemble"]["steps"]

    checkout = steps[0]
    assert checkout["with"] == {
        "ref": "${{ github.sha }}",
        "fetch-depth": 2,
        "persist-credentials": False,
    }

    select_index = next(i for i, step in enumerate(steps) if step.get("name") == "Select and validate one protected request")
    verify_index = next(i for i, step in enumerate(steps) if step.get("name") == "Verify exact target before credentials")
    native_index = next(i for i, step in enumerate(steps) if step.get("name") == "Run native causal reviewers")
    final_index = next(i for i, step in enumerate(steps) if step.get("name") == "Reverify exact head after model calls")
    report_index = next(i for i, step in enumerate(steps) if step.get("name") == "Build exact-target ensemble report")

    assert select_index < verify_index < native_index < final_index < report_index
    secret_steps = [i for i, step in enumerate(steps) if "secrets." in json.dumps(step, sort_keys=True)]
    assert secret_steps == [native_index]
    assert "steps.request.outcome == 'success'" in str(steps[native_index]["if"])


def test_queue_workflow_uses_exact_request_and_target_bindings():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/causal_review_queue.py" in text
    assert '--before-sha "${{ github.event.before }}"' in text
    assert '--after-sha "$GITHUB_SHA"' in text
    assert text.count('--expected-pr-number "$PR_NUMBER"') == 2
    assert text.count('--expected-head-sha "$EXPECTED_HEAD_SHA"') == 2
    assert text.count('--expected-head-branch "$EXPECTED_HEAD_BRANCH"') == 2
    assert "bash tools/run_native_causal_reviewers.sh" in text
    assert "retention-days: 7" in text


def test_queue_workflow_never_executes_target_pr_code():
    text = WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "git checkout",
        "npm install",
        "npm ci",
        "pip install",
        "poetry install",
        "cargo build",
        "go test",
        "bash target.patch",
        "source target.patch",
    )
    for command in forbidden:
        assert command not in text
    for step in parsed_yaml()["jobs"]["ensemble"]["steps"]:
        assert "${{" not in str(step.get("uses", ""))
