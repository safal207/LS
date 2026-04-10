from __future__ import annotations

# AgentValidationBridge — collects responses from N agent handles, builds
# CandidateAnswer objects, and runs CollectiveAnswerValidator.
#
# Design
# ──────
# AgentLoop is a single-agent loop.  Validation requires multiple candidates.
# The bridge sits between the two without touching AgentLoop internals:
#
#   bridge.submit(question) ──► each handle.submit(question)
#                            ◄── each handle.drain_response(timeout)
#                            ──► CollectiveAnswerValidator.validate(candidates)
#                            ◄── ValidationResult
#
# Handles are thin wrappers with a two-method protocol:
#   AgentHandle.submit(question)          — send a question
#   AgentHandle.drain_response(timeout)   — wait for the answer string
#
# Two concrete handles are provided:
#   CallableAgentHandle   — wraps a plain callable, ideal for tests
#   AgentLoopHandle       — wraps a real AgentLoop via its queue pair
#
# A candidate_builder callback converts (agent_id, response_text, question)
# into a CandidateAnswer.  A sensible default is provided.

import logging
import queue
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Protocol

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
    ValidationResult,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_DEFAULT_CANDIDATE_BUILDER_TIMEOUT = 10.0


# ── AgentHandle protocol ──────────────────────────────────────────────────────


class AgentHandle(Protocol):
    """Minimal interface that the bridge requires from each agent."""

    @property
    def agent_id(self) -> str: ...

    def submit(self, question: str) -> None: ...

    def drain_response(self, timeout: float) -> str | None:
        """Return the response string, or None on timeout / error."""
        ...


# ── Concrete handles ──────────────────────────────────────────────────────────


@dataclass
class CallableAgentHandle:
    """Wraps a synchronous callable.  Perfect for unit tests.

    Parameters
    ----------
    agent_id:
        Identifier used in CandidateAnswer.
    fn:
        Called with the question string; must return the answer string.
    """

    agent_id: str
    fn: Callable[[str], str]
    _pending: str | None = None

    def submit(self, question: str) -> None:
        try:
            self._pending = self.fn(question)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CallableAgentHandle %r fn raised: %s", self.agent_id, exc)
            self._pending = None

    def drain_response(self, timeout: float) -> str | None:  # noqa: ARG002
        result = self._pending
        self._pending = None
        return result


class AgentLoopHandle:
    """Wraps a real AgentLoop via its input/output queues.

    The AgentLoop must be started (loop.run() in a background thread).
    If the AgentLoop's output_queue is None a private one is injected.
    """

    def __init__(
        self,
        agent_id: str,
        loop: Any,
        *,
        response_timeout: float = _DEFAULT_CANDIDATE_BUILDER_TIMEOUT,
    ) -> None:
        self._agent_id = agent_id
        self._loop = loop
        self._timeout = response_timeout
        self._private_queue: queue.Queue[dict] | None = None

        if getattr(loop, "output_queue", None) is None:
            self._private_queue = queue.Queue()
            loop.output_queue = self._private_queue

        self._out_queue: queue.Queue[dict] = (
            self._private_queue
            if self._private_queue is not None
            else loop.output_queue
        )

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def submit(self, question: str) -> None:
        self._loop.submit(question)

    def drain_response(self, timeout: float) -> str | None:
        try:
            payload = self._out_queue.get(timeout=timeout)
            return payload.get("response") or payload.get("text")
        except queue.Empty:
            logger.warning(
                "AgentLoopHandle %r timed out after %.1fs", self._agent_id, timeout
            )
            return None


# ── Default candidate builder ─────────────────────────────────────────────────

CandidateBuilderFn = Callable[[str, str, str], CandidateAnswer]
"""(agent_id, response_text, task_prompt) -> CandidateAnswer"""


def _default_candidate_builder(
    agent_id: str,
    response_text: str,
    task_prompt: str,  # noqa: ARG001
) -> CandidateAnswer:
    """Produce a CandidateAnswer from a raw response string.

    Uses conservative defaults — all agents start at neutral scores.
    Callers should inject a scoring_fn that computes real relevance /
    hallucination_risk from a judge model or retrieval signal.
    """
    return CandidateAnswer(
        agent_id=agent_id,
        answer_text=response_text,
        relevance=0.70,
        thread_relevance=0.70,
        hallucination_risk=0.10,
    )


# ── Bridge ────────────────────────────────────────────────────────────────────


@dataclass
class BridgeResult:
    """Combines the validator result with per-agent raw responses."""

    validation_result: ValidationResult
    raw_responses: dict[str, str | None]  # agent_id → raw response text


class AgentValidationBridge:
    """Collects responses from N agent handles and validates them collectively.

    Parameters
    ----------
    handles:
        Agent handles to query.  At least two handles are required for
        meaningful consensus; one handle will produce ``weak`` status.
    validator:
        A configured CollectiveAnswerValidator (with optional trace /
        governance backends).
    candidate_builder:
        Converts (agent_id, response_text, task_prompt) into a
        CandidateAnswer.  Defaults to conservative neutral scores.
    response_timeout:
        Seconds to wait per handle before treating the response as
        missing.
    parallel:
        When True (default), all handles are submitted concurrently.
        When False, handles are queried sequentially.
    """

    def __init__(
        self,
        handles: list[AgentHandle],
        validator: CollectiveAnswerValidator | None = None,
        *,
        candidate_builder: CandidateBuilderFn | None = None,
        response_timeout: float = _DEFAULT_CANDIDATE_BUILDER_TIMEOUT,
        parallel: bool = True,
    ) -> None:
        if not handles:
            raise ValueError("AgentValidationBridge requires at least one handle")
        self._handles = handles
        self._validator = validator or CollectiveAnswerValidator()
        self._candidate_builder = candidate_builder or _default_candidate_builder
        self._response_timeout = response_timeout
        self._parallel = parallel

    def submit(self, task_prompt: str) -> BridgeResult:
        """Submit *task_prompt* to all handles and return a validated BridgeResult."""
        raw_responses = self._collect(task_prompt)
        candidates = self._build_candidates(task_prompt, raw_responses)
        payload = ValidationInput(task_prompt=task_prompt, candidates=candidates)
        result = self._validator.validate(payload)
        return BridgeResult(validation_result=result, raw_responses=raw_responses)

    # ── private ──────────────────────────────────────────────────────────────

    def _collect(self, question: str) -> dict[str, str | None]:
        if self._parallel:
            return self._collect_parallel(question)
        return self._collect_sequential(question)

    def _collect_parallel(self, question: str) -> dict[str, str | None]:
        responses: dict[str, str | None] = {}
        lock = threading.Lock()

        def _worker(handle: AgentHandle) -> None:
            handle.submit(question)
            text = handle.drain_response(self._response_timeout)
            with lock:
                responses[handle.agent_id] = text

        threads = [
            threading.Thread(target=_worker, args=(h,), daemon=True)
            for h in self._handles
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=self._response_timeout + 1.0)

        # Fill in agents whose threads never completed
        for handle in self._handles:
            responses.setdefault(handle.agent_id, None)
        return responses

    def _collect_sequential(self, question: str) -> dict[str, str | None]:
        responses: dict[str, str | None] = {}
        for handle in self._handles:
            handle.submit(question)
            responses[handle.agent_id] = handle.drain_response(self._response_timeout)
        return responses

    def _build_candidates(
        self,
        task_prompt: str,
        raw_responses: dict[str, str | None],
    ) -> list[CandidateAnswer]:
        candidates = []
        for handle in self._handles:
            text = raw_responses.get(handle.agent_id)
            if text is None:
                # Agent timed out — create a rejected empty candidate so the
                # trace still records the agent's participation.
                candidates.append(
                    CandidateAnswer(
                        agent_id=handle.agent_id,
                        answer_text="",
                        relevance=0.0,
                        thread_relevance=0.0,
                        hallucination_risk=1.0,
                    )
                )
            else:
                candidates.append(
                    self._candidate_builder(handle.agent_id, text, task_prompt)
                )
        return candidates
