from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without server extras
    raise ImportError(
        "ls_conductor.server requires the server extra. "
        "Install with: python -m pip install -e python/ls_conductor[server]"
    ) from exc

from .conductor import LSConductor


class ConductorRunInput(BaseModel):
    diff_file: str | None = Field(default=None, description="Path to a saved diff file.")
    base: str = Field(default="HEAD~1", description="Base git revision.")
    head: str = Field(default="HEAD", description="Head git revision.")
    policy: str = Field(default="cooperative_pr_review", description="Route policy.")
    output: str | None = Field(default=None, description="Optional JSON artifact output path.")
    max_diff_chars: int = Field(default=12000, ge=1, description="Maximum diff excerpt characters.")
    repo_path: str | None = Field(default=None, description="Optional LS repository path override.")


class CompareInput(BaseModel):
    candidates: list[str] = Field(default_factory=list, description="Candidate outputs to compare.")
    task: str = Field(default="", description="Original task description.")
    judge_policy: str = Field(default="clarity_and_conversion", description="Comparison policy.")
    repo_path: str | None = Field(default=None, description="Optional LS repository path override.")


_CLAIM_BOUNDARY = (
    "Local HTTP facade over the LS Conductor Python SDK and PR-review CLI; "
    "not a hosted production API, formal proof of best answer, or global model ranking."
)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def create_app() -> FastAPI:
    app = FastAPI(
        title="LS Conductor Local API",
        version="0.1.0",
        description=(
            "Local HTTP facade for LS Conductor. Wraps the existing Python SDK "
            "and PR-review route artifacts."
        ),
    )

    @app.get("/v1/health")
    def health(repo_path: str | None = None) -> dict[str, Any]:
        conductor = LSConductor(repo_path=Path(repo_path) if repo_path else "")
        response = _to_jsonable(conductor.healthcheck())
        response["claim_boundary"] = _CLAIM_BOUNDARY
        return response

    @app.post("/v1/conductor/run")
    def run_conductor(payload: ConductorRunInput) -> dict[str, Any]:
        try:
            conductor = LSConductor(repo_path=Path(payload.repo_path) if payload.repo_path else "")
            response = conductor.run(
                diff_file=payload.diff_file,
                base=payload.base,
                head=payload.head,
                policy=payload.policy,
                output=payload.output,
                max_diff_chars=payload.max_diff_chars,
            )
            data = _to_jsonable(response)
            data["http_facade"] = {
                "version": "v0.1",
                "claim_boundary": _CLAIM_BOUNDARY,
            }
            return data
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/v1/conductor/compare")
    def compare(payload: CompareInput) -> dict[str, Any]:
        try:
            conductor = LSConductor(repo_path=Path(payload.repo_path) if payload.repo_path else "")
            response = conductor.compare(
                candidates=payload.candidates,
                task=payload.task,
                judge_policy=payload.judge_policy,
            )
            data = _to_jsonable(response)
            data["http_facade"] = {
                "version": "v0.1",
                "claim_boundary": _CLAIM_BOUNDARY,
            }
            return data
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised only without server extras
        raise ImportError(
            "Running the local HTTP facade requires uvicorn. "
            "Install with: python -m pip install -e python/ls_conductor[server]"
        ) from exc

    uvicorn.run("ls_conductor.server:app", host="127.0.0.1", port=8788, reload=False)


if __name__ == "__main__":
    main()
