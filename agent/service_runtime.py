"""Service layer + runtime builder skeleton for modular agent task execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence


logger = logging.getLogger(__name__)


class ParallelTaskExecutionError(RuntimeError):
    """Raised when a parallel task worker fails."""

    def __init__(self, task_index: int, message: str):
        super().__init__(message)
        self.task_index = task_index


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

    def execute_tasks_parallel(
        self,
        tasks: Sequence[Task],
        steps_builder: Optional[Callable[[Task, "ServiceLayer"], Sequence[RuntimeStep]]] = None,
        max_workers: Optional[int] = None,
    ) -> List[Result]:
        """Execute multiple tasks in parallel while preserving input order.

        Args:
            tasks: Task batch to execute.
            steps_builder: Optional function to build a custom step chain per task.
            max_workers: Thread pool size passed to ThreadPoolExecutor.

        Raises:
            ParallelTaskExecutionError: Re-raises the first completed worker failure and
                includes the failed task index (`task_index`). This method uses fail-fast
                semantics and discards remaining results after the first error.
        """

        if not tasks:
            return []

        indexed_results: dict[int, Result] = {}

        def _run_one(index: int, task: Task) -> tuple[int, Result]:
            if steps_builder is None:
                result = self.execute_task(task)
            else:
                result = self.execute_task_with_steps(task, steps_builder(task, self))
            return index, result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {executor.submit(_run_one, idx, task): idx for idx, task in enumerate(tasks)}
            for future in as_completed(future_to_index):
                try:
                    index, result = future.result()
                    indexed_results[index] = result
                except Exception as exc:
                    failed_index = future_to_index[future]
                    logger.exception("Parallel task execution failed for index=%s", failed_index)
                    if len(indexed_results) != len(tasks):
                        logger.warning("Partial results before failure: %d/%d", len(indexed_results), len(tasks))
                    raise ParallelTaskExecutionError(
                        task_index=failed_index,
                        message=f"Task failed during parallel execution at index={failed_index}",
                    ) from exc

        if len(indexed_results) != len(tasks):
            logger.warning("Partial results: %d/%d tasks completed", len(indexed_results), len(tasks))

        return [indexed_results[idx] for idx in sorted(indexed_results)]


class EchoLLMService:
    """Simple provider useful for local tests and early prototyping."""

    def generate(self, prompt: str) -> str:
        return f"LLM output for: {prompt}"
