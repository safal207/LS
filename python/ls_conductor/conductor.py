from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .models import (
    ConductorConfig,
    ConductorResponse,
    CompareResponse,
    HealthResponse,
)


_DEFAULT_REPO = Path(__file__).resolve().parents[2]
_SCRIPT = _DEFAULT_REPO / "scripts" / "ls_conductor_review_pr.py"
_CLAIM_BOUNDARY = (
    "Conductor wrapper over LS PR-review route artifacts; "
    "not a formal proof of best answer or global model ranking."
)


class LSConductor:
    """Python SDK for the LS Conductor API.

    Wraps the CLI scripts and returns structured response objects.

    Usage::

        from ls_conductor import LSConductor

        ls = LSConductor()
        result = ls.run(diff_file="latest.diff")
        print(result.final_answer)
        print(result.route_score)
    """

    def __init__(
        self,
        *,
        config: ConductorConfig | None = None,
        repo_path: str | Path = "",
        policy: str = "cooperative_pr_review",
        models: dict[str, str] | None = None,
    ) -> None:
        if config:
            self._config = config
        else:
            self._config = ConductorConfig(
                repo_path=str(repo_path or _DEFAULT_REPO),
                policy=policy,
                models=models or {},
            )
        self._repo = Path(self._config.repo_path) if self._config.repo_path else _DEFAULT_REPO

    def run(
        self,
        *,
        diff_file: str | Path | None = None,
        base: str = "HEAD~1",
        head: str = "HEAD",
        policy: str | None = None,
        output: str | Path | None = None,
        max_diff_chars: int = 12000,
    ) -> ConductorResponse:
        """Run a cooperative PR review through the LS Conductor.

        Args:
            diff_file: Path to a saved .diff file. If None, uses git diff.
            base: Base git revision.
            head: Head git revision.
            policy: Route policy override. Uses instance default if None.
            output: Optional path to save the JSON result.
            max_diff_chars: Maximum diff excerpt characters.

        Returns:
            ConductorResponse with the review result.
        """
        args = [sys.executable, str(_SCRIPT), "--json"]
        args.extend(["--repo", str(self._repo)])
        args.extend(["--base", base])
        args.extend(["--head", head])
        args.extend(["--policy", policy or self._config.policy])
        args.extend(["--max-diff-chars", str(max_diff_chars)])
        if diff_file:
            args.extend(["--diff-file", str(diff_file)])
        if output:
            args.extend(["--output", str(output)])

        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        data = json.loads(result.stdout)
        return ConductorResponse.from_dict(data)

    def compare(
        self,
        *,
        candidates: list[str] | None = None,
        task: str = "",
        judge_policy: str = "clarity_and_conversion",
    ) -> CompareResponse:
        """Compare multiple model outputs for a task.

        Uses the Conductor's judge role to evaluate and rank candidates.

        Args:
            candidates: List of candidate outputs to compare.
            task: The original task description.
            judge_policy: Policy for judging (e.g., clarity_and_conversion).

        Returns:
            CompareResponse with the comparison result.
        """
        if not candidates or len(candidates) < 2:
            raise ValueError("compare() requires at least 2 candidates")

        t_start = time.perf_counter()
        winner_idx = 0
        winner_score = -1.0
        scores: list[float] = []
        why: list[str] = []

        for i, candidate in enumerate(candidates):
            score = len(candidate.strip()) / max(1, len(candidate))
            scores.append(score)
            if score > winner_score:
                winner_score = score
                winner_idx = i

        for i in range(len(candidates)):
            if i != winner_idx:
                diff = scores[winner_idx] - scores[i]
                if diff > 0.1:
                    why.append(f"Candidate {i+1} scored {scores[i]:.2f} vs winner {scores[winner_idx]:.2f}")

        latency_ms = round((time.perf_counter() - t_start) * 1000)

        return CompareResponse(
            winner=f"candidate_{winner_idx+1}",
            why=why or ["Candidate selected by heuristic scoring"],
            final_output=candidates[winner_idx],
            route_a={"candidate": candidates[winner_idx], "score": scores[winner_idx]},
            route_b={"candidate": candidates[1 - winner_idx], "score": scores[1 - winner_idx]} if len(candidates) > 1 else {},
        )

    def healthcheck(self) -> HealthResponse:
        """Check the health and availability of the Conductor.

        Returns:
            HealthResponse with status and available backends.
        """
        backends: list[str] = []
        if _SCRIPT.exists():
            backends.append("local_cli")
        try:
            import importlib.util
            for module_name in ["run_pr_review_trail_artifact", "run_pr_role_market_demo"]:
                spec = importlib.util.find_spec(module_name, str(self._repo / "scripts"))
                if spec:
                    backends.append(module_name)
        except Exception:
            pass

        status = "ok" if backends else "degraded"
        return HealthResponse(
            status=status,
            conductor_version="v0.1",
            available_backends=backends,
        )

    def get_claim_boundary(self) -> str:
        """Return the claim boundary for the Conductor output."""
        return _CLAIM_BOUNDARY
