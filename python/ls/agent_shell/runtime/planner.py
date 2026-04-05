from __future__ import annotations

from ls.agent_shell.schemas.step import Step


class Planner:
    """Transparent step planner (5-8 short and checkable steps)."""

    def build_plan(self, task_id: str, prompt: str, mode: str) -> list[Step]:
        lower = prompt.lower()
        if "pr" in lower or "review" in lower:
            skeleton = [
                ("Fetch PR metadata", "read", "Need source context before analysis."),
                ("Read changed files", "read", "Review must inspect the changed surface area."),
                ("Check docs and contracts", "analyze", "Consistency and API contracts are core review gates."),
                ("Draft verdict", "write", "A review output requires a written verdict artifact."),
                ("Produce review artifact", "artifact", "Task completion requires a shareable result."),
            ]
        else:
            skeleton = [
                ("Read relevant docs", "read", "Ground the response in repository context."),
                ("Extract constraints", "analyze", "Clarify success criteria and boundaries."),
                ("Draft output", "write", "Prepare actionable content from the analysis."),
                ("Create artifact", "artifact", "Persist the output as an openable artifact."),
                ("Finalize summary", "analyze", "Provide concise completion summary and next steps."),
            ]

        steps: list[Step] = []
        for index, (title, step_type, reason) in enumerate(skeleton, start=1):
            needs_approval = step_type in {"write", "git", "browser"} and mode != "read-only"
            steps.append(
                Step(
                    id=f"step-{index}",
                    task_id=task_id,
                    title=title,
                    description=f"{title} for task {task_id}",
                    type=step_type,  # type: ignore[arg-type]
                    reason=reason,
                    needs_approval=needs_approval,
                )
            )
        return steps
