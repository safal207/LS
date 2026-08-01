from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Sequence

from agents import Agent, Runner, RunContextWrapper, handoff
from pydantic import BaseModel, Field

from .runtime import TrustRuntime


class DispatchInput(BaseModel):
    task: str = Field(min_length=1, description="The exact bounded task for the next agent")
    constraints: list[str] = Field(default_factory=list)
    requested_authority: list[str] = Field(
        default_factory=list,
        description="Effects the next agent may propose, never implicit permission to execute",
    )


def trusted_handoff(
    runtime: TrustRuntime,
    *,
    parent_name: str,
    child: Agent,
):
    async def on_handoff(
        _ctx: RunContextWrapper[None], input_data: DispatchInput
    ) -> None:
        receipt = runtime.issue_dispatch(
            parent_agent=parent_name,
            child_agent=child.name,
            task=input_data.task,
            constraints=input_data.constraints,
            authority_scope=input_data.requested_authority,
        )
        print(
            json.dumps(
                {
                    "event": "dispatch_issued",
                    "parent": parent_name,
                    "child": child.name,
                    "receipt_id": receipt.receipt_id,
                },
                sort_keys=True,
            )
        )

    return handoff(
        agent=child,
        on_handoff=on_handoff,
        input_type=DispatchInput,
        tool_description_override=(
            f"Delegate a bounded task to {child.name}. State constraints and the exact "
            "authority the agent may propose. This records an LS dispatch receipt."
        ),
    )


def build_team(runtime: TrustRuntime) -> Agent:
    safety = Agent(
        name="Safety Reviewer",
        handoff_description="Checks evidence, authority boundaries, and recovery risks.",
        instructions=(
            "Review the proposed change and QA evidence. Identify unsupported claims, stale "
            "work, missing evidence, duplicate effects, and authority escalation. Return a "
            "clear final verdict. Never claim that merge or deployment occurred."
        ),
    )

    qa_name = "QA Agent"
    qa = Agent(
        name=qa_name,
        handoff_description="Validates the proposed change with adversarial tests.",
        instructions=(
            "Review the developer result, design focused positive and negative tests, and "
            "summarize concrete evidence. Then hand off to Safety Reviewer with the exact task, "
            "constraints, and requested authority ['merge'] so the protected-effect gate can "
            "demonstrate that a recommendation is not permission."
        ),
        handoffs=[
            trusted_handoff(runtime, parent_name=qa_name, child=safety),
        ],
    )

    developer_name = "Developer Agent"
    developer = Agent(
        name=developer_name,
        handoff_description="Creates the smallest bounded implementation proposal.",
        instructions=(
            "Produce the smallest implementation plan or patch proposal that addresses the "
            "goal. State assumptions and test evidence. Then hand off to QA Agent with the exact "
            "bounded validation task, constraints, and requested authority ['run_tests']."
        ),
        handoffs=[
            trusted_handoff(runtime, parent_name=developer_name, child=qa),
        ],
    )

    coordinator_name = "Coordinator Agent"
    return Agent(
        name=coordinator_name,
        instructions=(
            "Turn the user's goal into one bounded software-change task. Do not solve the task "
            "yourself. Hand off to Developer Agent with explicit constraints and requested "
            "authority ['write_patch', 'run_tests']."
        ),
        handoffs=[
            trusted_handoff(runtime, parent_name=coordinator_name, child=developer),
        ],
    )


def dry_run() -> dict[str, object]:
    runtime = TrustRuntime()
    root = runtime.issue_dispatch(
        parent_agent="Human",
        child_agent="Coordinator Agent",
        task="Prepare a bounded software change with independent QA and safety review",
        constraints=("no external side effects", "evidence required"),
        authority_scope=("propose_plan",),
    )
    developer = runtime.issue_dispatch(
        parent_agent="Coordinator Agent",
        child_agent="Developer Agent",
        task="Create the smallest patch proposal",
        constraints=("do not deploy",),
        authority_scope=("write_patch", "run_tests"),
    )
    qa = runtime.issue_dispatch(
        parent_agent="Developer Agent",
        child_agent="QA Agent",
        task="Run adversarial validation against the patch proposal",
        constraints=("record negative tests",),
        authority_scope=("run_tests",),
    )
    safety = runtime.issue_dispatch(
        parent_agent="QA Agent",
        child_agent="Safety Reviewer",
        task="Review evidence and decide whether merge may be recommended",
        constraints=("recommendation is not authority",),
        authority_scope=("merge",),
    )
    result = runtime.submit_result(
        dispatch_id=safety.receipt_id,
        agent="Safety Reviewer",
        status="COMPLETED",
        summary="Evidence is sufficient for a human merge decision.",
        evidence=("tests:test_authority_gate", "tests:test_recovery_lineage"),
    )
    blocked = runtime.authorize_effect(
        dispatch_id=safety.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    runtime.grant_human_approval(
        dispatch_id=safety.receipt_id,
        effect="merge",
        approver="demo-human",
        reason="Reviewed the bounded evidence and accepted the residual risk.",
    )
    allowed = runtime.authorize_effect(
        dispatch_id=safety.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )

    interrupted = runtime.issue_dispatch(
        parent_agent="Coordinator Agent",
        child_agent="Research Agent instance-1",
        task="Inspect one dependency contract",
        constraints=("read only",),
        authority_scope=("read_repository",),
    )
    recovered = runtime.recover_dispatch(
        interrupted.receipt_id,
        replacement_agent="Research Agent instance-2",
    )

    return {
        "root_dispatch": root.receipt_id,
        "developer_dispatch": developer.receipt_id,
        "qa_dispatch": qa.receipt_id,
        "safety_dispatch": safety.receipt_id,
        "merge_before_approval": asdict(blocked),
        "merge_after_approval": asdict(allowed),
        "recovery": {
            "superseded": interrupted.receipt_id,
            "replacement": recovered.receipt_id,
        },
        "ledger_valid": runtime.verify_ledger(),
        "ledger": runtime.ledger,
    }


async def run_live(goal: str, approve_merge: bool) -> dict[str, object]:
    runtime = TrustRuntime()
    root = runtime.issue_dispatch(
        parent_agent="Human",
        child_agent="Coordinator Agent",
        task=goal,
        constraints=("no external effects", "preserve evidence", "report uncertainty"),
        authority_scope=("propose_plan",),
    )
    coordinator = build_team(runtime)
    result = await Runner.run(coordinator, goal)
    last_agent_name = result.last_agent.name
    target = next(
        (
            dispatch
            for dispatch in reversed(runtime.dispatches)
            if dispatch.child_agent == last_agent_name
        ),
        root,
    )
    result_receipt = runtime.submit_result(
        dispatch_id=target.receipt_id,
        agent=target.child_agent,
        status="COMPLETED",
        summary=str(result.final_output),
        evidence=("openai-agents-sdk:runner-completed",),
    )

    effect_decision = None
    if "merge" in target.authority_scope:
        if approve_merge:
            runtime.grant_human_approval(
                dispatch_id=target.receipt_id,
                effect="merge",
                approver="cli-human",
                reason="Explicit --approve-merge flag supplied for the demonstration.",
            )
        effect_decision = runtime.authorize_effect(
            dispatch_id=target.receipt_id,
            result_receipt_id=result_receipt.receipt_id,
            effect="merge",
        )

    return {
        "final_agent": last_agent_name,
        "final_output": str(result.final_output),
        "result_receipt": asdict(result_receipt),
        "effect_decision": asdict(effect_decision) if effect_decision else None,
        "ledger_valid": runtime.verify_ledger(),
        "ledger": runtime.ledger,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run without an API call")
    parser.add_argument(
        "--goal",
        default="Design a safe fix for a duplicate payment callback and its regression tests.",
    )
    parser.add_argument(
        "--approve-merge",
        action="store_true",
        help="Record an explicit human approval receipt; never performs a merge.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    payload = dry_run() if args.dry_run else asyncio.run(run_live(args.goal, args.approve_merge))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
