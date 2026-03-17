"""Service layer + runtime builder skeleton for modular agent task execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence


@dataclass
class Task:
    """Represents a unit of work requested from the service layer."""

    task_type: str
    input_data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    """Normalized task execution payload returned to callers."""

    task_type: str
    result: Dict[str, Any]
    raw_output: Optional[str] = None


class LLMService(Protocol):
    """Contract for any model provider (OpenAI, Claude, local, etc.)."""

    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""


class RuntimeStep(Protocol):
    """Pipeline step contract used by the runtime builder."""

    def execute(self, payload: Any) -> Any:
        """Execute step and return output consumed by next step."""


class PreProcessor:
    """Default input cleaner and prompt constructor."""

    def __init__(self, task: Task):
        self.task = task

    def execute(self, _: Any) -> str:
        normalized = {k: v for k, v in self.task.input_data.items() if v is not None}
        return f"task={self.task.task_type};input={normalized}"


class LLMStep:
    """Executes model inference."""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def execute(self, prompt: str) -> str:
        return self.llm_service.generate(prompt)


class PostProcessor:
    """Normalizes raw model response into structured result payload."""

    def __init__(self, task: Task):
        self.task = task

    def execute(self, raw_output: str) -> Result:
        return Result(
            task_type=self.task.task_type,
            raw_output=raw_output,
            result={
                "content": raw_output,
                "input": self.task.input_data,
            },
        )


class RuntimeBuilder:
    """Creates and runs a deterministic pipeline for each task."""

    def __init__(self, task: Task, llm_service: LLMService, steps: Optional[Sequence[RuntimeStep]] = None):
        self.task = task
        self.llm_service = llm_service
        self.pipeline = list(steps) if steps else self.build_pipeline()

    def build_pipeline(self) -> List[RuntimeStep]:
        return [
            PreProcessor(self.task),
            LLMStep(self.llm_service),
            PostProcessor(self.task),
        ]

    def run(self) -> Result:
        payload: Any = None
        for step in self.pipeline:
            payload = step.execute(payload)
        if not isinstance(payload, Result):
            raise TypeError("Runtime pipeline must produce a Result object")
        return payload


class ServiceLayer:
    """High-level orchestrator for task lifecycle and runtime execution."""

    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def create_task(self, task_type: str, input_data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Task:
        return Task(task_type=task_type, input_data=input_data, metadata=metadata or {})

    def execute_task(self, task: Task) -> Result:
        runtime = RuntimeBuilder(task, self.llm_service)
        return runtime.run()

    def execute_task_with_steps(self, task: Task, steps: Sequence[RuntimeStep]) -> Result:
        """Execute a task with a custom runtime pipeline."""

        runtime = RuntimeBuilder(task, self.llm_service, steps=steps)
        return runtime.run()


class EchoLLMService:
    """Simple provider useful for local tests and early prototyping."""

    def generate(self, prompt: str) -> str:
        return f"LLM output for: {prompt}"
