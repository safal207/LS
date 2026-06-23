from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from ..causal import (
    CausalAuditDisabledError,
    CausalAuditReport,
    CausalAuditTimeoutError,
    CausalAuditUnavailableError,
    CausalFinding,
    CausalRecord,
    CausalSeverity,
    MalformedCausalAuditResponseError,
    trail_to_causal_records,
)
from ..contracts import CognitiveTrail


CMLRunner = Callable[[Sequence[CausalRecord], "CMLConfig"], Mapping[str, Any]]


@dataclass(frozen=True)
class CMLConfig:
    enabled: bool = False
    timeout_seconds: float = 3.0
    command: tuple[str, ...] = ("cml", "audit")
    actor: str = "adapter:cml"

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.command:
            raise ValueError("CML command must not be empty")
        if not self.actor:
            raise ValueError("CML actor must not be empty")


class CMLCausalAuditAdapter:
    """Optional subprocess boundary for the independent CML audit engine."""

    def __init__(
        self,
        config: Optional[CMLConfig] = None,
        runner: Optional[CMLRunner] = None,
    ) -> None:
        self.config = config or CMLConfig()
        self._runner = runner

    @property
    def adapter_name(self) -> str:
        return "cml"

    def audit(self, trail: CognitiveTrail) -> CausalAuditReport:
        return self.audit_records(
            trail_to_causal_records(trail),
            task_id=trail.task_id,
            trail_id=trail.trail_id,
            created_at=trail.created_at,
        )

    def audit_records(
        self,
        records: Sequence[CausalRecord],
        *,
        task_id: str,
        trail_id: str,
        created_at: str,
    ) -> CausalAuditReport:
        if not self.config.enabled:
            raise CausalAuditDisabledError(
                "CML causal audit is disabled; enable it explicitly in configuration"
            )
        if not records:
            raise ValueError("CML audit requires records")
        try:
            response = (
                self._runner(records, self.config)
                if self._runner is not None
                else self._subprocess_runner(records)
            )
        except CausalAuditTimeoutError:
            raise
        except subprocess.TimeoutExpired as error:
            raise CausalAuditTimeoutError("CML audit timed out") from error
        except (OSError, FileNotFoundError) as error:
            raise CausalAuditUnavailableError("CML audit command is unavailable") from error
        if not isinstance(response, Mapping):
            raise MalformedCausalAuditResponseError("CML response must be an object")
        return self._report_from_response(
            records,
            response,
            task_id=task_id,
            trail_id=trail_id,
            created_at=created_at,
        )

    def _subprocess_runner(
        self,
        records: Sequence[CausalRecord],
    ) -> Mapping[str, Any]:
        with tempfile.TemporaryDirectory(prefix="ls-cml-") as directory:
            trace_path = Path(directory) / "causal-trace.jsonl"
            trace_path.write_text(
                "".join(
                    json.dumps(record.to_cml_dict(), sort_keys=True) + "\n"
                    for record in records
                ),
                encoding="utf-8",
            )
            command = [*self.config.command, str(trace_path), "--format", "json"]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.config.timeout_seconds,
            )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise CausalAuditUnavailableError(
                f"CML audit exited with code {completed.returncode}: {message}"
            )
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MalformedCausalAuditResponseError(
                "CML audit output is not valid JSON"
            ) from error
        if not isinstance(decoded, Mapping):
            raise MalformedCausalAuditResponseError("CML audit output must be an object")
        return decoded

    def _report_from_response(
        self,
        records: Sequence[CausalRecord],
        response: Mapping[str, Any],
        *,
        task_id: str,
        trail_id: str,
        created_at: str,
    ) -> CausalAuditReport:
        summary = response.get("summary")
        findings_value = response.get("findings")
        if not isinstance(summary, Mapping) or not isinstance(findings_value, list):
            raise MalformedCausalAuditResponseError(
                "CML response requires summary and findings"
            )
        findings: list[CausalFinding] = []
        for item in findings_value:
            if not isinstance(item, Mapping):
                raise MalformedCausalAuditResponseError(
                    "every CML finding must be an object"
                )
            code = item.get("code")
            severity_value = item.get("severity")
            record_id = item.get("record_id")
            message = item.get("message")
            if not all(isinstance(value, str) and value for value in (
                code,
                severity_value,
                record_id,
                message,
            )):
                raise MalformedCausalAuditResponseError(
                    "CML finding requires code, severity, record_id, and message"
                )
            try:
                severity = CausalSeverity(severity_value.upper())
            except ValueError as error:
                raise MalformedCausalAuditResponseError(
                    f"unsupported CML severity: {severity_value}"
                ) from error
            chain_ids_value = item.get("chain_ids", ())
            if isinstance(chain_ids_value, (str, bytes)) or not isinstance(
                chain_ids_value,
                (list, tuple),
            ):
                raise MalformedCausalAuditResponseError(
                    "CML chain_ids must be a sequence"
                )
            findings.append(
                CausalFinding(
                    code=code,
                    severity=severity,
                    record_id=record_id,
                    message=message,
                    blocking=(
                        severity is CausalSeverity.FAIL
                        or code == "CML-AUDIT-R4-AMBIGUOUS_ROOT"
                    ),
                    parent_cause=item.get("parent_cause"),
                    chain_ids=tuple(str(value) for value in chain_ids_value),
                    context=(
                        dict(item.get("context", {}))
                        if isinstance(item.get("context", {}), Mapping)
                        else {}
                    ),
                )
            )
        roots = tuple(
            record.record_id
            for record in records
            if record.parent_cause is None
            and record.permitted_by.startswith("root_event:")
        )
        return CausalAuditReport(
            audit_id=f"cml-audit-{trail_id}",
            task_id=task_id,
            trail_id=trail_id,
            adapter=self.adapter_name,
            actor=self.config.actor,
            created_at=created_at,
            records_checked=len(records),
            root_ids=roots,
            findings=tuple(findings),
            metadata={
                "transport": "subprocess" if self._runner is None else "injected",
                "cml_summary": dict(summary),
                "source_format": "cml-jsonl",
            },
        )
