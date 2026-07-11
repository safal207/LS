import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAME_REPO = ROOT / ".github/workflows/trusted-causal-review-same-repo.yml"
FORK_COLLECTOR = ROOT / ".github/workflows/causal-review-collect.yml"
OLD_BRIDGE = ROOT / ".github/workflows/trusted-causal-review-ensemble.yml"


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


def test_same_repo_workflow_is_loaded_from_protected_base_context():
    text = SAME_REPO.read_text(encoding="utf-8")

    assert "  pull_request_target:\n" in text
    assert "  pull_request:\n" not in text
    assert "github.event.pull_request.head.repo.full_name == github.repository" in text
    assert "github.event.pull_request.author_association" in text
    assert "OWNER" in text
    assert "MEMBER" in text
    assert "COLLABORATOR" in text
    assert "ref: refs/heads/main" in text
    assert "persist-credentials: false" in text
    assert "ref: ${{ github.event.pull_request.head.sha }}" not in text
    assert "actions/checkout@v4" in text
    assert "NEVER check out the pull request head" in text


def test_privileged_workflow_structure_keeps_secrets_after_verification():
    workflow = parsed_yaml(SAME_REPO)
    jobs = workflow["jobs"]
    ensemble = jobs["ensemble"]
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
    secret_indices = [
        index
        for index, step in enumerate(steps)
        if "secrets." in json.dumps(step, sort_keys=True)
    ]
    assert secret_indices
    assert all(index > verify_index for index in secret_indices)

    for step in steps:
        uses = str(step.get("uses", ""))
        assert "${{" not in uses
        if str(step.get("name", "")).startswith("Run trusted "):
            condition = str(step.get("if", ""))
            assert "steps.request.outcome == 'success'" in condition

    skip_job = jobs["report-untrusted-same-repo"]
    assert "secrets." not in json.dumps(skip_job, sort_keys=True)
    assert "NOT AUTHORIZED" in json.dumps(skip_job)


def test_same_repo_workflow_never_executes_target_pr_code():
    text = SAME_REPO.read_text(encoding="utf-8")

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
        "curl -s |",
        "make ",
        "bash target.patch",
        "source target.patch",
    )
    for command in forbidden:
        assert command not in text

    assert "python tools/retrying_causal_review_github.py collect" in text
    assert "python tools/retrying_causal_review_github.py verify" in text


def test_exact_target_is_verified_before_and_after_model_calls():
    text = SAME_REPO.read_text(encoding="utf-8")

    first_verify = text.index("Verify exact target before credentials")
    credentials = text.index("Resolve native reviewer credentials")
    grok = text.index("Run trusted Grok causal lane")
    deepseek = text.index("Run trusted DeepSeek causal lane")
    codex = text.index("Run trusted Codex causal lane")
    final_verify = text.index("Reverify exact head after model calls")
    report = text.index("Build exact-target ensemble report")

    assert first_verify < credentials < grok < deepseek < codex < final_verify < report
    assert text.count("python tools/retrying_causal_review_github.py verify") == 2
    assert text.count('--expected-pr-number "$PR_NUMBER"') == 2
    assert text.count('--expected-head-sha "$EXPECTED_HEAD_SHA"') == 2
    assert text.count('--expected-head-branch "$EXPECTED_HEAD_BRANCH"') == 2


def test_native_reviewers_have_explicit_missing_secret_states():
    text = SAME_REPO.read_text(encoding="utf-8")

    for secret, reviewer in (
        ("XAI_API_KEY", "Grok"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("OPENAI_API_KEY", "Codex"),
    ):
        assert f"secrets.{secret}" in text
        assert f"Record {reviewer} NOT_RUN lane" in text
        assert f"Repository secret {secret} is unavailable" in text


def test_fork_workflow_has_no_model_secrets_or_native_execution():
    text = FORK_COLLECTOR.read_text(encoding="utf-8")

    assert "github.event.pull_request.head.repo.full_name != github.repository" in text
    assert "secret_access\": False" in text
    assert "NOT_AUTHORIZED_FOR_FORK" in text
    assert "python tools/retrying_causal_review_github.py collect" in text
    assert "secrets.XAI_API_KEY" not in text
    assert "secrets.DEEPSEEK_API_KEY" not in text
    assert "secrets.OPENAI_API_KEY" not in text
    assert "grok_causal_review.py review" not in text
    assert "deepseek_causal_review.py review" not in text
    assert "codex_causal_review.py review" not in text


def test_workflow_run_bridge_is_removed():
    assert SAME_REPO.exists()
    assert FORK_COLLECTOR.exists()
    assert not OLD_BRIDGE.exists()
